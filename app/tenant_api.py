"""Authenticated tenant-scoped PostgreSQL API. These endpoints never query legacy SQLite."""
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from . import auth as identity
from .tenant_db import tenant_session
from .domain_models import TenantOrder, TenantReview, TenantRefund, TenantDispute, TenantEvidence, TenantAuditEvent
from .api_schemas import TenantOrderCreate, TenantReviewCreate

router = APIRouter(prefix='/api/v1/domain', tags=['tenant-domain'])

def principal(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE: raise HTTPException(503, 'Identity dependencies unavailable')
    return p

@router.get('/orders')
def orders(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        return [{'id':x.id,'customer_id':x.customer_id,'customer_name':x.customer_name,'product':x.product,'batch':x.batch,'amount':str(x.amount),'currency':x.currency,'payment_status':x.payment_status,'created_at':x.created_at.isoformat()} for x in s.scalars(select(TenantOrder).where(TenantOrder.tenant_id==p['tenant_id']).order_by(TenantOrder.created_at.desc()).limit(500))]

@router.post('/orders')
def create_order(body: TenantOrderCreate, p=Depends(principal)):
    row=TenantOrder(id=str(uuid.uuid4()),tenant_id=p['tenant_id'],customer_id=body.customer_id,customer_name=body.customer_name,product=body.product,amount=body.amount,currency=body.currency,payment_status='UNPAID')
    with tenant_session(p['tenant_id']) as s: s.add(row)
    return {'id':row.id,'status':'CREATED'}

@router.get('/reviews')
def reviews(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        return [{'id':x.id,'customer_id':x.customer_id,'order_id':x.order_id,'rating':x.rating,'text':x.text,'category':x.category,'severity':x.severity} for x in s.scalars(select(TenantReview).where(TenantReview.tenant_id==p['tenant_id']).order_by(TenantReview.created_at.desc()).limit(1000))]

@router.post('/reviews')
def create_review(body: TenantReviewCreate, p=Depends(principal)):
    if body.order_id:
        with tenant_session(p['tenant_id']) as s:
            order=s.scalar(select(TenantOrder.id).where(TenantOrder.id==body.order_id, TenantOrder.tenant_id==p['tenant_id']))
        if not order:
            raise HTTPException(404,'Order not found in this merchant workspace')
    row=TenantReview(id=str(uuid.uuid4()),tenant_id=p['tenant_id'],customer_id=body.customer_id,customer_name=body.customer_name,order_id=body.order_id,product=body.product,rating=body.rating,text=body.text,category=None,severity=None)
    with tenant_session(p['tenant_id']) as s: s.add(row)
    return {'id':row.id,'status':'CREATED'}

@router.get('/summary')
def summary(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        tables=(TenantOrder,TenantReview,TenantRefund,TenantDispute,TenantEvidence,TenantAuditEvent)
        return {t.__tablename__:len(s.scalars(select(t.id).where(t.tenant_id==p['tenant_id'])).all()) for t in tables}

@router.post('/demo-seed')
def seed_demo_data(p=Depends(principal)):
    """Explicitly seed only the authenticated tenant; never runs during production startup."""
    if p['role'] not in {'OWNER','ADMIN'}:
        raise HTTPException(403, 'Only a workspace owner or admin can seed illustrative demo data')
    from .demo_seed import seed_tenant_demo_data
    with tenant_session(p['tenant_id']) as s:
        result = seed_tenant_demo_data(s, p['tenant_id'], p['user_id'])
    return result


@router.get('/demo-summary')
def demo_summary(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        tables = (TenantOrder, TenantReview, TenantRefund, TenantDispute, TenantEvidence, TenantAuditEvent)
        counts = {
            model.__tablename__: len(s.scalars(
                select(model.id).where(model.tenant_id == p['tenant_id'])
            ).all())
            for model in tables
        }
        from .financial_lifecycle import ResolutionCase, FinancialEvent
        counts['financial_resolution_cases'] = len(s.scalars(
            select(ResolutionCase.id).where(ResolutionCase.tenant_id == p['tenant_id'])
        ).all())
        counts['financial_timeline_events'] = len(s.scalars(
            select(FinancialEvent.id).where(FinancialEvent.tenant_id == p['tenant_id'])
        ).all())
        marker = s.scalar(select(TenantAuditEvent).where(
            TenantAuditEvent.tenant_id == p['tenant_id'],
            TenantAuditEvent.event == 'ILLUSTRATIVE_DEMO_DATA_SEEDED'
        ).order_by(TenantAuditEvent.created_at.desc()).limit(1))
        return {
            'source': 'ILLUSTRATIVE_SYNTHETIC' if marker else 'MERCHANT_DATA_OR_EMPTY',
            'label': 'Illustrative demo records are not real customers, payments or provider cases.' if marker else None,
            'counts': counts,
            'paypal_transactions_created': 0 if marker else None,
            'provider_confirmations_fabricated': 0 if marker else None,
        }


@router.get('/customers')
def tenant_customers(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        orders = s.scalars(select(TenantOrder).where(
            TenantOrder.tenant_id == p['tenant_id']
        ).order_by(TenantOrder.created_at.desc())).all()
        reviews = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == p['tenant_id']
        ).order_by(TenantReview.created_at.desc())).all()
        groups = {}
        for order in orders:
            key = order.customer_id or 'UNKNOWN'
            row = groups.setdefault(key, {
                'customer_id': key, 'customer_name': order.customer_name or 'Unknown',
                'referenced_orders': 0, 'review_count': 0, 'ratings': [],
                'latest_review': None,
            })
            row['referenced_orders'] += 1
        for review in reviews:
            key = review.customer_id or 'UNKNOWN'
            row = groups.setdefault(key, {
                'customer_id': key, 'customer_name': review.customer_name or 'Unknown',
                'referenced_orders': 0, 'review_count': 0, 'ratings': [],
                'latest_review': None,
            })
            row['review_count'] += 1
            if review.rating is not None:
                row['ratings'].append(int(review.rating))
            if review.created_at and (row['latest_review'] is None or review.created_at.isoformat() > row['latest_review']):
                row['latest_review'] = review.created_at.isoformat()
        output = []
        for row in groups.values():
            ratings = row.pop('ratings')
            row['avg_rating'] = round(sum(ratings) / len(ratings), 2) if ratings else None
            row['source'] = 'ILLUSTRATIVE_SYNTHETIC' if row['customer_id'].startswith('CUST-') else 'TENANT_RECORD'
            output.append(row)
        return output


@router.get('/customers/{customer_id}')
def tenant_customer_detail(customer_id: str, p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        orders = s.scalars(select(TenantOrder).where(
            TenantOrder.tenant_id == p['tenant_id'],
            TenantOrder.customer_id == customer_id,
        ).order_by(TenantOrder.created_at.desc())).all()
        reviews = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == p['tenant_id'],
            TenantReview.customer_id == customer_id,
        ).order_by(TenantReview.created_at.desc())).all()
        if not orders and not reviews:
            raise HTTPException(404, 'Customer not found in this merchant workspace')
        customer_name = next((x.customer_name for x in orders if x.customer_name), None) or next((x.customer_name for x in reviews if x.customer_name), None) or 'Unknown'
        customer = {
            'customer_id': customer_id, 'customer_name': customer_name,
            'review_count': len(reviews), 'referenced_orders': len(orders),
            'avg_rating': round(sum(int(x.rating) for x in reviews if x.rating is not None) / len([x for x in reviews if x.rating is not None]), 2) if any(x.rating is not None for x in reviews) else None,
        }
        return {
            'customer': customer,
            'reviews': [{
                'id': x.id, 'order_id': x.order_id, 'product': x.product,
                'rating': x.rating, 'text': x.text, 'category': x.category,
                'severity': x.severity, 'created_at': x.created_at.isoformat(),
            } for x in reviews],
            'orders': [{
                'id': x.id, 'product': x.product, 'amount': str(x.amount),
                'currency': x.currency, 'payment_status': x.payment_status,
                'created_at': x.created_at.isoformat(),
            } for x in orders],
            'source': 'ILLUSTRATIVE_SYNTHETIC' if customer_id.startswith('CUST-') else 'TENANT_RECORD',
        }


@router.get('/transactions')
def tenant_transactions(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        rows = s.scalars(select(TenantOrder).where(
            TenantOrder.tenant_id == p['tenant_id']
        ).order_by(TenantOrder.created_at.desc()).limit(500)).all()
        return [{
            'id': x.id, 'customer_id': x.customer_id, 'customer_name': x.customer_name,
            'product': x.product, 'batch': x.batch, 'amount': str(x.amount),
            'currency': x.currency, 'payment_status': x.payment_status,
            'paypal_order_id': x.paypal_order_id, 'capture_id': x.capture_id,
            'created_at': x.created_at.isoformat(),
            'source': 'ILLUSTRATIVE_SYNTHETIC' if x.id.startswith('demo-') else 'TENANT_RECORD',
        } for x in rows]


@router.get('/transactions/{order_id}')
def tenant_transaction_detail(order_id: str, p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        order = s.scalar(select(TenantOrder).where(
            TenantOrder.id == order_id, TenantOrder.tenant_id == p['tenant_id']
        ))
        if not order:
            raise HTTPException(404, 'Order not found in this merchant workspace')
        reviews = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == p['tenant_id'], TenantReview.order_id == order_id
        )).all()
        refunds = s.scalars(select(TenantRefund).where(
            TenantRefund.tenant_id == p['tenant_id'], TenantRefund.order_id == order_id
        )).all()
        disputes = s.scalars(select(TenantDispute).where(
            TenantDispute.tenant_id == p['tenant_id'], TenantDispute.order_id == order_id
        )).all()
        evidence = s.scalars(select(TenantEvidence).where(
            TenantEvidence.tenant_id == p['tenant_id'], TenantEvidence.order_id == order_id
        )).all()
        item = {
            'id': order.id, 'customer_id': order.customer_id,
            'customer_name': order.customer_name, 'product': order.product,
            'batch': order.batch, 'amount': str(order.amount),
            'currency': order.currency, 'payment_status': order.payment_status,
            'paypal_order_id': order.paypal_order_id, 'capture_id': order.capture_id,
            'created_at': order.created_at.isoformat(),
        }
        return {
            'order': item,
            'reviews': [{'id': x.id, 'rating': x.rating, 'text': x.text, 'category': x.category, 'severity': x.severity} for x in reviews],
            'refunds': [{'id': x.id, 'amount': str(x.amount), 'currency': x.currency, 'status': x.status, 'paypal_refund_id': x.paypal_refund_id, 'paypal_status': x.paypal_status, 'reason': x.reason} for x in refunds],
            'disputes': [{'id': x.id, 'status': x.status, 'reason': x.reason, 'evidence': x.evidence} for x in disputes],
            'evidence': [{'id': x.id, 'evidence_type': x.evidence_type, 'description': x.description, 'integrity_status': x.integrity_status, 'storage_key': x.storage_key} for x in evidence],
            'source': 'ILLUSTRATIVE_SYNTHETIC' if order.id.startswith('demo-') else 'TENANT_RECORD',
        }


@router.get('/refunds')
def tenant_refunds(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        rows = s.scalars(select(TenantRefund).where(
            TenantRefund.tenant_id == p['tenant_id']
        ).order_by(TenantRefund.created_at.desc())).all()
        return [{
            'id': x.id, 'order_id': x.order_id, 'capture_id': x.capture_id,
            'amount': str(x.amount), 'currency': x.currency, 'reason': x.reason,
            'status': x.status, 'paypal_refund_id': x.paypal_refund_id,
            'paypal_status': x.paypal_status, 'created_at': x.created_at.isoformat(),
        } for x in rows]


@router.get('/disputes')
def tenant_disputes(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        rows = s.scalars(select(TenantDispute).where(
            TenantDispute.tenant_id == p['tenant_id']
        ).order_by(TenantDispute.created_at.desc())).all()
        return [{
            'id': x.id, 'order_id': x.order_id, 'reason': x.reason,
            'status': x.status, 'customer_message': x.customer_message,
            'evidence': x.evidence, 'created_at': x.created_at.isoformat(),
        } for x in rows]


@router.get('/evidence')
def tenant_evidence(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        rows = s.scalars(select(TenantEvidence).where(
            TenantEvidence.tenant_id == p['tenant_id']
        ).order_by(TenantEvidence.created_at.desc())).all()
        return [{
            'id': x.id, 'order_id': x.order_id, 'evidence_type': x.evidence_type,
            'description': x.description, 'storage_key': x.storage_key,
            'sha256': x.sha256, 'integrity_status': x.integrity_status,
            'created_at': x.created_at.isoformat(),
        } for x in rows]


@router.get('/audit')
def tenant_audit(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        rows = s.scalars(select(TenantAuditEvent).where(
            TenantAuditEvent.tenant_id == p['tenant_id']
        ).order_by(TenantAuditEvent.created_at.desc()).limit(500)).all()
        return [{
            'id': x.id, 'event': x.event, 'actor': x.actor_user_id or 'SYSTEM',
            'entity_type': x.entity_type, 'entity_id': x.entity_id,
            'detail': x.detail, 'created_at': x.created_at.isoformat(),
        } for x in rows]


@router.get('/root-cause')
def tenant_root_cause(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        reviews = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == p['tenant_id']
        )).all()
        cases = s.scalars(select(TenantDispute).where(
            TenantDispute.tenant_id == p['tenant_id']
        )).all()
        orders = s.scalars(select(TenantOrder).where(
            TenantOrder.tenant_id == p['tenant_id']
        )).all()
        by_batch = {}
        for order in orders:
            row = by_batch.setdefault(order.batch or 'UNASSIGNED', {'orders': 0, 'complaints': 0, 'products': set()})
            row['orders'] += 1
            row['products'].add(order.product or 'UNSPECIFIED')
        complaint_order_ids = {x.order_id for x in reviews if x.rating is not None and x.rating <= 2 and x.order_id}
        complaint_order_ids.update(x.order_id for x in cases if x.order_id)
        for order in orders:
            if order.id in complaint_order_ids:
                by_batch.setdefault(order.batch or 'UNASSIGNED', {'orders': 0, 'complaints': 0, 'products': set()})['complaints'] += 1
        findings = []
        for batch, row in sorted(by_batch.items()):
            if row['complaints']:
                findings.append({
                    'category': 'BATCH_SIGNAL', 'title': f'Complaint concentration: {batch}',
                    'summary': f"{row['complaints']} of {row['orders']} orders in this batch are linked to low-rated reviews or illustrative dispute records.",
                    'batch': batch, 'complaints': row['complaints'],
                    'products': sorted(row['products']),
                    'interpretation': 'Exploratory association only; not proof of a manufacturing cause.',
                })
        return {
            'findings': findings,
            'source': 'TENANT_SCOPED_RECORDS',
            'limitations': 'Signals combine low-rated linked reviews and dispute records. They are descriptive associations, not proof of causation.',
        }

@router.get('/reviews')
def tenant_review_list(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        rows = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == p['tenant_id']
        ).order_by(TenantReview.created_at.desc()).limit(1000)).all()
        return [{
            'id': x.id, 'customer_id': x.customer_id,
            'customer_name': x.customer_name, 'order_id': x.order_id,
            'product': x.product, 'rating': x.rating, 'text': x.text,
            'category': x.category, 'severity': x.severity,
            'cluster_id': x.complaint_cluster_id,
            'created_at': x.created_at.isoformat(),
        } for x in rows]


@router.get('/review-clusters')
def tenant_review_cluster_summary(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        rows = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == p['tenant_id']
        )).all()
        grouped = {}
        for review in rows:
            key = review.complaint_cluster_id or review.category or 'UNCLASSIFIED'
            item = grouped.setdefault(key, {'cluster_id': key, 'count': 0, 'ratings': [], 'analyzed_at': None})
            item['count'] += 1
            if review.rating is not None:
                item['ratings'].append(int(review.rating))
            if review.created_at and (item['analyzed_at'] is None or review.created_at.isoformat() > item['analyzed_at']):
                item['analyzed_at'] = review.created_at.isoformat()
        output = []
        for item in grouped.values():
            ratings = item.pop('ratings')
            item['avg_rating'] = round(sum(ratings) / len(ratings), 2) if ratings else None
            item['avg_sentiment'] = None
            output.append(item)
        return sorted(output, key=lambda x: (-x['count'], x['cluster_id']))


@router.get('/dashboard')
def tenant_dashboard(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        orders = s.scalars(select(TenantOrder).where(TenantOrder.tenant_id == p['tenant_id'])).all()
        reviews = s.scalars(select(TenantReview).where(TenantReview.tenant_id == p['tenant_id'])).all()
        disputes = s.scalars(select(TenantDispute).where(TenantDispute.tenant_id == p['tenant_id'])).all()
        refunds = s.scalars(select(TenantRefund).where(TenantRefund.tenant_id == p['tenant_id'])).all()
        totals = {}
        for order in orders:
            totals.setdefault(order.currency, {'gross': 0.0, 'orders': 0})
            totals[order.currency]['gross'] += float(order.amount)
            totals[order.currency]['orders'] += 1
        refund_totals = {}
        for refund in refunds:
            refund_totals[refund.currency] = refund_totals.get(refund.currency, 0.0) + float(refund.amount)
        return {
            'orders': len(orders), 'gross_totals': totals,
            'reviews': len(reviews),
            'disputes': sum(1 for x in disputes if x.status in {'OPEN', 'ILLUSTRATIVE_OPEN'}),
            'refund_count': len(refunds),
            'refund_totals': refund_totals,
            'refund_total': next(iter(refund_totals.values())) if len(refund_totals) == 1 else None,
            'demo': any(x.id.startswith('demo-') for x in orders),
            'source': 'TENANT_SCOPED_RECORDS',
        }

@router.get('/refunds/{refund_id}')
def tenant_refund_detail(refund_id: str, p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        row = s.scalar(select(TenantRefund).where(
            TenantRefund.id == refund_id, TenantRefund.tenant_id == p['tenant_id']
        ))
        if not row:
            raise HTTPException(404, 'Refund record not found')
        return {
            'id': row.id, 'order_id': row.order_id, 'capture_id': row.capture_id,
            'amount': str(row.amount), 'currency': row.currency,
            'reason': row.reason, 'status': row.status,
            'paypal_refund_id': row.paypal_refund_id,
            'paypal_status': row.paypal_status,
            'created_at': row.created_at.isoformat(),
            'source': 'ILLUSTRATIVE_SYNTHETIC' if row.id.startswith('demo-') else 'TENANT_RECORD',
            'provider_action': 'NONE',
        }


@router.get('/disputes/{dispute_id}')
def tenant_dispute_detail(dispute_id: str, p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        row = s.scalar(select(TenantDispute).where(
            TenantDispute.id == dispute_id, TenantDispute.tenant_id == p['tenant_id']
        ))
        if not row:
            raise HTTPException(404, 'Dispute record not found')
        evidence = s.scalars(select(TenantEvidence).where(
            TenantEvidence.tenant_id == p['tenant_id'],
            TenantEvidence.order_id == row.order_id,
        )).all()
        return {
            'id': row.id, 'order_id': row.order_id, 'reason': row.reason,
            'status': row.status, 'customer_message': row.customer_message,
            'evidence': row.evidence,
            'evidence_records': [{
                'id': x.id, 'evidence_type': x.evidence_type,
                'description': x.description, 'integrity_status': x.integrity_status,
            } for x in evidence],
            'source': 'ILLUSTRATIVE_SYNTHETIC' if row.id.startswith('demo-') else 'TENANT_RECORD',
            'provider_case_id': None,
            'provider_submission': 'NOT_SUBMITTED',
        }

