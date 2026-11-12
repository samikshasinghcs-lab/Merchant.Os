"""Authenticated tenant administration and trust-operation endpoints."""
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from . import auth as identity
router=APIRouter(prefix='/api/v1/operations',tags=['tenant-operations'])
def principal(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE: raise HTTPException(503,'Identity dependencies unavailable')
    return p
@router.put('/paypal-credentials')
def paypal_credentials(body:dict,p=Depends(principal)):
    if p['role'] not in {'OWNER','ADMIN'}: raise HTTPException(403,'OWNER or ADMIN required')
    from .tenant_operations import save_paypal_credentials
    try: return save_paypal_credentials(p['tenant_id'],body.get('environment','sandbox'),body.get('client_id',''),body.get('client_secret',''),body.get('webhook_id',''))
    except Exception as e: raise HTTPException(400,str(e))
@router.post('/invitations')
def invite(body:dict,p=Depends(principal)):
    from .tenant_operations import create_invitation
    try: return create_invitation(p,body.get('email',''),body.get('role','OPERATOR'))
    except PermissionError as e: raise HTTPException(403,str(e))
    except Exception as e: raise HTTPException(400,str(e))
@router.post('/invitations/accept')
def accept(body:dict,p=Depends(principal)):
    from .tenant_operations import accept_invitation
    try: return accept_invitation(p['user_id'],body.get('token',''))
    except PermissionError as e: raise HTTPException(403,str(e))
    except Exception as e: raise HTTPException(400,str(e))
@router.post('/agreements/{agreement_id}/approvals')
def approve(agreement_id:str,body:dict,p=Depends(principal)):
    from .tenant_operations import record_pact_approval
    try: return record_pact_approval(p,agreement_id,int(body.get('version',0)),body.get('decision',''),body.get('statement',''))
    except Exception as e: raise HTTPException(400,str(e))
@router.post('/paypal/webhooks/{environment}')
async def authenticated_webhook_test(environment:str,request:Request,p=Depends(principal)):
    """Authenticated diagnostic receiver for a single workspace. PayPal itself should
    use the opaque public endpoint returned by PUT /paypal-credentials."""
    if environment not in {'sandbox','live'}: raise HTTPException(400,'environment must be sandbox or live')
    event=await request.json()
    from .tenant_operations import receive_verified_webhook
    try: return receive_verified_webhook(p['tenant_id'],dict(request.headers),event,environment)
    except PermissionError as e: raise HTTPException(401,str(e))
    except ValueError as e: raise HTTPException(400,str(e))


@router.get('/webhooks/events')
def webhook_events(limit:int=100,p=Depends(principal)):
    from .event_processor import list_webhook_events
    try: return {'items':list_webhook_events(p['tenant_id'],limit=limit)}
    except ValueError as e: raise HTTPException(400,str(e))


@router.post('/webhooks/events/process')
def process_webhook_events(body:dict|None=None,p=Depends(principal)):
    if p['role'] not in {'OWNER','ADMIN','OPERATOR'}: raise HTTPException(403,'Operator role required')
    from .event_processor import process_pending_events
    try: return process_pending_events(p['tenant_id'],limit=int((body or {}).get('limit',10)))
    except ValueError as e: raise HTTPException(400,str(e))


@router.get('/webhooks/events/{event_id}/trace')
def webhook_event_trace(event_id:str,p=Depends(principal)):
    from .event_processor import list_event_trace
    try: return {'items':list_event_trace(p['tenant_id'],event_id)}
    except ValueError as e: raise HTTPException(400,str(e))


@router.post('/webhooks/events/{event_id}/replay')
def replay_webhook_event(event_id:str,p=Depends(principal)):
    if p['role'] not in {'OWNER','ADMIN'}: raise HTTPException(403,'OWNER or ADMIN required for dead-letter replay')
    from .event_processor import replay_dead_letter
    try: return replay_dead_letter(p['tenant_id'],event_id,actor_id=p['user_id'])
    except LookupError as e: raise HTTPException(404,str(e))
    except PermissionError as e: raise HTTPException(403,str(e))
    except ValueError as e: raise HTTPException(409,str(e))

@router.post('/financial/refund-approvals')
def create_refund_approval(body:dict,p=Depends(principal)):
    """Create a pending reconciliation request; caller cannot assert provider facts."""
    import uuid, re
    from decimal import Decimal, InvalidOperation
    from .financial_controls import approval_digest
    from .completion_models import FinancialApprovalRequest
    from .tenant_db import tenant_session
    from sqlalchemy import select
    if p['role'] not in {'OWNER','ADMIN','OPERATOR'}: raise HTTPException(403,'Operator role required')
    capture_id=str(body.get('capture_id') or '').strip()
    currency=str(body.get('currency') or '').upper()
    reason=str(body.get('reason') or '').strip()
    request_key=str(body.get('request_key') or '').strip()
    try:
        raw_amount=Decimal(str(body.get('amount')))
        if not raw_amount.is_finite() or raw_amount != raw_amount.quantize(Decimal('0.01')):
            raise ValueError('fractional cents are not accepted')
        amount=raw_amount.quantize(Decimal('0.01'))
    except (InvalidOperation,ValueError,TypeError): raise HTTPException(400,'amount must be a valid decimal with no fractional cents')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',capture_id): raise HTTPException(400,'capture_id is invalid')
    if not re.fullmatch(r'[A-Z]{3}',currency): raise HTTPException(400,'currency must be a three-letter ISO code')
    if not amount.is_finite() or amount<=0: raise HTTPException(400,'amount must be positive and finite')
    if len(reason)<10 or len(reason)>1000: raise HTTPException(400,'reason must contain 10–1000 characters')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}',request_key): raise HTTPException(400,'request_key must be 8–128 safe characters')
    digest=approval_digest(tenant_id=p['tenant_id'],capture_id=capture_id,amount=f'{amount:.2f}',currency=currency,reason=reason)
    with tenant_session(p['tenant_id']) as s:
        old=s.scalar(select(FinancialApprovalRequest).where(FinancialApprovalRequest.tenant_id==p['tenant_id'],FinancialApprovalRequest.request_key==request_key))
        if old:
            if old.policy_digest != digest: raise HTTPException(409,'request_key already exists with a different financial payload')
            return {'created':False,'duplicate':True,'id':old.id,'status':old.status,'policy_digest':old.policy_digest}
        row=FinancialApprovalRequest(id=str(uuid.uuid4()),tenant_id=p['tenant_id'],request_key=request_key,action='REFUND',capture_id=capture_id,amount=f'{amount:.2f}',currency=currency,reason=reason,policy_digest=digest,requester_id=p['user_id'],status='PENDING_RECONCILIATION')
        s.add(row)
    return {'created':True,'id':row.id,'status':'PENDING_RECONCILIATION','policy_digest':digest,'execution_authorized':False,'note':'Request recorded. A trusted server-side PayPal capture read and deterministic policy evaluation are required before approval. Client-supplied provider status or reconciliation flags are ignored.'}

@router.post('/financial/refund-approvals/{approval_id}/reconcile')
def reconcile_refund_approval_route(approval_id:str,p=Depends(principal)):
    """Trusted server-side PayPal read; request body cannot supply provider facts."""
    if p['role'] not in {'OWNER','ADMIN','OPERATOR'}:
        raise HTTPException(403,'Operator role required')
    from .financial_approval_service import reconcile_refund_approval
    from .paypal_tenant_adapter import TenantPayPalError
    try:
        return reconcile_refund_approval(tenant_id=p['tenant_id'],approval_id=approval_id)
    except LookupError as e:
        raise HTTPException(404,str(e))
    except ValueError as e:
        raise HTTPException(409,str(e))
    except TenantPayPalError as e:
        # A failed provider read never advances the request.
        raise HTTPException(502,'PayPal canonical capture read failed; request remains pending reconciliation')

@router.get('/financial/refund-approvals')
def list_refund_approvals(p=Depends(principal)):
    from .completion_models import FinancialApprovalRequest
    from .tenant_db import tenant_session
    from sqlalchemy import select
    with tenant_session(p['tenant_id']) as s:
        rows=s.scalars(select(FinancialApprovalRequest).where(FinancialApprovalRequest.tenant_id==p['tenant_id']).order_by(FinancialApprovalRequest.created_at.desc()).limit(100)).all()
        return [{'id':x.id,'request_key':x.request_key,'action':x.action,'capture_id':x.capture_id,'amount':x.amount,'currency':x.currency,'reason':x.reason,'status':x.status,'requester_id':x.requester_id,'approver_id':x.approver_id,'created_at':x.created_at.isoformat(),'decided_at':x.decided_at.isoformat() if x.decided_at else None,'policy_digest':x.policy_digest} for x in rows]

@router.post('/financial/refund-approvals/{approval_id}/decision')
def decide_refund_approval(approval_id:str,body:dict,p=Depends(principal)):
    from datetime import datetime,timezone
    from .financial_controls import approval_digest,validate_approver
    from .completion_models import FinancialApprovalRequest
    from .tenant_db import tenant_session
    from sqlalchemy import select
    decision=str(body.get('decision') or '').upper()
    if decision not in {'APPROVE','REJECT'}: raise HTTPException(400,'decision must be APPROVE or REJECT')
    with tenant_session(p['tenant_id']) as s:
        row=s.scalar(select(FinancialApprovalRequest).where(FinancialApprovalRequest.id==approval_id,FinancialApprovalRequest.tenant_id==p['tenant_id']))
        if not row: raise HTTPException(404,'Approval request not found')
        expected=approval_digest(tenant_id=row.tenant_id,capture_id=row.capture_id,amount=row.amount,currency=row.currency,reason=row.reason)
        try: validate_approver(requester_id=row.requester_id,approver_id=p['user_id'],role=p['role'],approval_digest_matches=(expected==row.policy_digest),status=row.status)
        except (ValueError,PermissionError) as e: raise HTTPException(409 if isinstance(e,ValueError) else 403,str(e))
        row.status='APPROVED' if decision=='APPROVE' else 'REJECTED'
        row.approver_id=p['user_id']; row.decision_note=str(body.get('note') or '')[:1000]; row.decided_at=datetime.now(timezone.utc)
        result={'id':row.id,'status':row.status,'approver_id':row.approver_id,'policy_digest':row.policy_digest,'execution_authorized':False}
    return {**result,'note':'Approval decision recorded. Provider execution remains disabled pending the dedicated execution adapter and final preflight.'}

@router.post('/financial/refund-approvals/{approval_id}/execute')
def execute_refund_approval(approval_id:str,p=Depends(principal)):
    """Execute one independently approved refund in PayPal Sandbox only."""
    import os
    from .financial_execution_service import execute_approved_refund
    enabled=os.getenv('PAYPAL_EXECUTION_ENABLED','false').lower()=='true'
    try:
        return execute_approved_refund(tenant_id=p['tenant_id'],approval_id=approval_id,
            actor_id=p['user_id'],environment='sandbox',execution_enabled=enabled)
    except LookupError as e: raise HTTPException(404,str(e))
    except PermissionError as e: raise HTTPException(403,str(e))
    except Exception as e: raise HTTPException(409,str(e))
