"""Tenant-bound credential, webhook inbox, membership and PACT approval services."""
import hashlib, hmac, json, os, uuid, secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from .auth_sqlalchemy import SessionLocal, Membership, User
from .tenant_db import tenant_session
from .completion_models import MerchantPayPalCredential, PayPalWebhookEvent, PayPalWebhookRoute, PactPartyApproval, MerchantInvitation
from .paypal_security import encrypt_secret, decrypt_secret, verify_webhook_signature, CredentialError

ROLES={'ADMIN','OPERATOR','VIEWER'}
def _owner_admin(p):
    if p['role'] not in {'OWNER','ADMIN'}: raise PermissionError('OWNER or ADMIN role required')

def save_paypal_credentials(tenant_id, environment, client_id, client_secret, webhook_id):
    if environment not in {'sandbox','live'}: raise ValueError('environment must be sandbox or live')
    client_id = str(client_id or '').strip()
    webhook_id = str(webhook_id or '').strip()
    if not client_id or not client_secret or not webhook_id:
        raise ValueError('PayPal client ID, secret and webhook ID are required')
    encrypted=encrypt_secret(client_secret)
    # A fresh high-entropy endpoint token is issued on every credential update. Only its
    # SHA-256 digest is persisted; the raw token is returned once for PayPal webhook setup.
    endpoint_token=secrets.token_urlsafe(32)
    endpoint_hash=hashlib.sha256(endpoint_token.encode()).hexdigest()
    with tenant_session(tenant_id) as s:
        row=s.scalar(select(MerchantPayPalCredential).where(MerchantPayPalCredential.tenant_id==tenant_id,MerchantPayPalCredential.environment==environment))
        if row:
            row.client_id=client_id; row.encrypted_client_secret=encrypted; row.webhook_id=webhook_id; row.active=True; row.updated_at=datetime.now(timezone.utc)
        else:
            row=MerchantPayPalCredential(id=str(uuid.uuid4()),tenant_id=tenant_id,environment=environment,client_id=client_id,encrypted_client_secret=encrypted,webhook_id=webhook_id,active=True); s.add(row)
        s.query(PayPalWebhookRoute).filter(PayPalWebhookRoute.tenant_id==tenant_id,PayPalWebhookRoute.environment==environment,PayPalWebhookRoute.active.is_(True)).update({'active':False}, synchronize_session=False)
        s.add(PayPalWebhookRoute(id=str(uuid.uuid4()),tenant_id=tenant_id,environment=environment,token_hash=endpoint_hash,active=True))
    from .config import PUBLIC_APP_URL
    path=f'/api/paypal/webhooks/tenant/{endpoint_token}'
    return {'environment':environment,'configured':True,'webhook_endpoint_path':path,
            'webhook_url':f'{PUBLIC_APP_URL}{path}' if PUBLIC_APP_URL else path,
            'webhook_url_note':'Register this URL in the matching PayPal app. Use a publicly reachable HTTPS PUBLIC_APP_URL; the raw endpoint token is shown only in this response.'}

def get_paypal_credentials(tenant_id, environment):
    with tenant_session(tenant_id) as s:
        row=s.scalar(select(MerchantPayPalCredential).where(MerchantPayPalCredential.tenant_id==tenant_id,MerchantPayPalCredential.environment==environment,MerchantPayPalCredential.active.is_(True)))
        if not row: return None
        return {'client_id':row.client_id,'client_secret':decrypt_secret(row.encrypted_client_secret),'webhook_id':row.webhook_id,'environment':row.environment}

def resolve_paypal_webhook_route(endpoint_token):
    """Resolve an opaque public path token without exposing credential records.

    The routing registry contains only a random-token digest, tenant ID and environment.
    The actual webhook signature is still verified against that tenant's PayPal webhook ID.
    """
    if not endpoint_token or len(endpoint_token) > 128:
        return None
    from .auth_sqlalchemy import SessionLocal
    digest=hashlib.sha256(endpoint_token.encode()).hexdigest()
    with SessionLocal() as s:
        if s.bind.dialect.name == 'postgresql':
            s.execute(text("SELECT set_config('app.webhook_token_hash', :token_hash, true)"), {'token_hash': digest})
        row=s.scalar(select(PayPalWebhookRoute).where(PayPalWebhookRoute.token_hash==digest,PayPalWebhookRoute.active.is_(True)))
        result={'tenant_id':row.tenant_id,'environment':row.environment} if row else None
        s.commit()
        return result


def receive_verified_webhook(tenant_id, headers, event, environment):
    creds=get_paypal_credentials(tenant_id,environment)
    if not creds: raise PermissionError('PayPal credentials are not configured for this merchant')
    if not verify_webhook_signature(headers,event,creds['webhook_id'],creds['client_id'],creds['client_secret'],environment):
        raise PermissionError('PayPal webhook signature verification failed')
    from .workflow_events import sanitize_paypal_event
    safe_event=sanitize_paypal_event(event)
    event_id=safe_event['event_id']; event_type=safe_event['event_type']
    from sqlalchemy.exc import IntegrityError
    try:
        with tenant_session(tenant_id) as s:
            existing=s.scalar(select(PayPalWebhookEvent).where(PayPalWebhookEvent.tenant_id==tenant_id,PayPalWebhookEvent.event_id==event_id))
            if existing: return {'accepted':True,'duplicate':True,'status':existing.status,'event_id':event_id,'workflow_run_id':existing.workflow_run_id}
            s.add(PayPalWebhookEvent(id=str(uuid.uuid4()),tenant_id=tenant_id,event_id=event_id,event_type=event_type,
                payload=safe_event,status='RECEIVED',attempt_count=0))
    except IntegrityError:
        # The unique tenant/event key is the final concurrency guard if PayPal retries
        # arrive simultaneously after both requests perform the initial lookup.
        with tenant_session(tenant_id) as s:
            existing=s.scalar(select(PayPalWebhookEvent).where(PayPalWebhookEvent.tenant_id==tenant_id,PayPalWebhookEvent.event_id==event_id))
            if existing: return {'accepted':True,'duplicate':True,'status':existing.status,'event_id':event_id,'workflow_run_id':existing.workflow_run_id}
        raise
    return {'accepted':True,'duplicate':False,'status':'RECEIVED','event_id':event_id,
            'workflow_dispatch':'PENDING','privacy':'Only allowlisted event metadata is stored; raw payer/contact/shipping data is discarded.'}


def record_webhook_workflow_run(tenant_id, event_id, workflow_run_id):
    with tenant_session(tenant_id) as s:
        row=s.scalar(select(PayPalWebhookEvent).where(PayPalWebhookEvent.tenant_id==tenant_id,PayPalWebhookEvent.event_id==event_id))
        if not row: raise LookupError('Webhook event not found')
        row.workflow_run_id=str(workflow_run_id)[:128]
        return {'event_id':event_id,'workflow_run_id':row.workflow_run_id}

def create_invitation(principal,email,role='OPERATOR',hours=72):
    _owner_admin(principal); email=email.strip().lower()
    if role not in ROLES: raise ValueError('Invited role must be ADMIN, OPERATOR or VIEWER')
    raw=secrets.token_urlsafe(32); digest=hashlib.sha256(raw.encode()).hexdigest()
    with tenant_session(principal['tenant_id']) as s:
        s.add(MerchantInvitation(id=str(uuid.uuid4()),tenant_id=principal['tenant_id'],email=email,role=role,token_hash=digest,expires_at=datetime.now(timezone.utc)+timedelta(hours=hours)))
    return {'email':email,'role':role,'invitation_token':raw,'expires_in_hours':hours}

def accept_invitation(user_id, token):
    digest=hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as s:
        if s.bind.dialect.name == 'postgresql':
            s.execute(text("SELECT set_config('app.invitation_token_hash', :token_hash, true)"), {'token_hash': digest})
        invite=s.scalar(select(MerchantInvitation).where(MerchantInvitation.token_hash==digest))
        if not invite or invite.accepted_at or invite.expires_at < datetime.now(timezone.utc):
            s.rollback()
            raise ValueError('Invitation is invalid, expired or already used')
        user=s.get(User,user_id)
        if not user or user.email.lower()!=invite.email:
            s.rollback()
            raise PermissionError('Invitation email does not match authenticated account')
        if s.bind.dialect.name == 'postgresql':
            # The token lookup reveals exactly one invitation row; only then derive
            # tenant context from that database-owned row for the one-time UPDATE.
            s.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {'tenant_id': invite.tenant_id})
        s.add(Membership(user_id=user.id,tenant_id=invite.tenant_id,role=invite.role)); invite.accepted_at=datetime.now(timezone.utc); s.commit()
        return {'tenant_id':invite.tenant_id,'role':invite.role}

def record_pact_approval(principal, agreement_id, version, decision, statement):
    if decision not in {'APPROVE','REJECT'}: raise ValueError('decision must be APPROVE or REJECT')
    if not statement or len(statement.strip())<10: raise ValueError('A meaningful approval statement is required')
    digest=hashlib.sha256(statement.strip().encode()).hexdigest()
    with tenant_session(principal['tenant_id']) as s:
        existing=s.scalar(select(PactPartyApproval).where(PactPartyApproval.tenant_id==principal['tenant_id'],PactPartyApproval.agreement_id==agreement_id,PactPartyApproval.agreement_version==version,PactPartyApproval.user_id==principal['user_id']))
        if existing: raise ValueError('This user has already approved or rejected this agreement version')
        s.add(PactPartyApproval(id=str(uuid.uuid4()),tenant_id=principal['tenant_id'],agreement_id=agreement_id,agreement_version=version,user_id=principal['user_id'],decision=decision,statement_hash=digest))
    return {'agreement_id':agreement_id,'version':version,'decision':decision,'actor_user_id':principal['user_id'],'statement_sha256':digest,'recorded':True}
