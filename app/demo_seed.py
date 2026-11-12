"""Idempotent, tenant-isolated synthetic commerce dataset for MerchantOS demos.

No PayPal IDs, captures, webhook events, provider transactions, or completed money
movements are created. Every inserted record is explicitly labelled synthetic.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from . import auth as identity
from .tenant_db import tenant_session
from .domain_models import (
    TenantOrder, TenantReview, TenantRefund, TenantDispute, TenantEvidence,
    TenantAuditEvent, DemoCustomerProfile, DemoProductBatchInsight,
)
from .financial_lifecycle import (
    OrderCost, ResolutionCase, InventoryDisposition, FinancialEvent,
)

router = APIRouter(prefix="/api/v1/demo", tags=["demo-data"])
DEMO_LABEL = "SYNTHETIC_DEMO"
SEED_VERSION = "unified-commerce-v1"
SYSTEM_ACTOR = "MERCHANTOS_DEMO_SEED"


def _id(tenant_id: str, kind: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"merchantos:{tenant_id}:{SEED_VERSION}:{kind}:{key}"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seed_tenant_demo_data(tenant_id: str, actor_user_id: str | None = None) -> dict:
    """Insert the same connected demo story once per tenant; never overwrites merchant data."""
    if not tenant_id:
        raise ValueError("tenant_id is required")

    tenant_prefix = uuid.uuid5(uuid.NAMESPACE_URL, f"merchantos-tenant:{tenant_id}").hex[:8].upper()
    names = [
        ("Aarav Mehta", "Bengaluru", "RETURNING"),
        ("Mira Shah", "Mysuru", "LOYAL"),
        ("Kabir Rao", "Pune", "RETURNING"),
        ("Anaya Iyer", "Chennai", "NEW"),
        ("Ishaan Nair", "Kochi", "LOYAL"),
        ("Riya Das", "Kolkata", "RETURNING"),
        ("Dev Malhotra", "Delhi", "NEW"),
        ("Tara Kapoor", "Mumbai", "LOYAL"),
        ("Arjun Sen", "Hyderabad", "RETURNING"),
        ("Nisha Roy", "Bengaluru", "NEW"),
        ("Vihaan Joshi", "Pune", "LOYAL"),
        ("Sana Khan", "Mysuru", "RETURNING"),
        ("Reyansh Bose", "Kolkata", "NEW"),
        ("Ira Menon", "Chennai", "LOYAL"),
        ("Aditya Kulkarni", "Mumbai", "RETURNING"),
    ]
    products = [
        {"key": "hydrating-serum", "name": "Hydrating Serum", "sku": "SER-HYD-30", "batch": "BATCH-A", "price": Decimal("499.00")},
        {"key": "vitamin-c-serum", "name": "Vitamin C Serum", "sku": "SER-VTC-30", "batch": "BATCH-B", "price": Decimal("599.00")},
        {"key": "daily-moisturizer", "name": "Daily Moisturizer", "sku": "CRM-DLY-50", "batch": "BATCH-C", "price": Decimal("399.00")},
    ]
    complaint_texts = [
        ("PACKAGING_DAMAGE", "HIGH", 1, "The bottle arrived damaged and the outer packaging was crushed."),
        ("LEAKAGE", "HIGH", 2, "The product leaked inside the parcel during delivery."),
        ("DELIVERY_DELAY", "LOW", 4, "Delivery arrived later than the estimated date."),
        ("PUMP_FAILURE", "MEDIUM", 2, "The dispenser pump did not work on first use."),
        ("WRONG_ITEM", "MEDIUM", 3, "The parcel contained a different item from the order."),
    ]
    now = _now()
    orders_data = []
    for index in range(30):
        customer_index = index // 2
        product = products[index % 3]
        # The first batch intentionally carries a repeated packaging/leakage signal.
        if product["key"] == "hydrating-serum":
            issue = complaint_texts[0 if index % 2 == 0 else 1]
        else:
            issue = complaint_texts[(index + 1) % len(complaint_texts)]
        created = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc) + timedelta(hours=index * 7)
        orders_data.append({
            "key": f"order-{index + 1:03d}", "customer_index": customer_index,
            "product": product, "issue": issue, "created": created,
        })

    inserted = {key: 0 for key in (
        "customers", "orders", "reviews", "refund_proposals", "disputes",
        "evidence", "financial_cases", "case_events", "audit_events",
        "order_costs", "inventory_instructions", "product_batch_insights",
    )}
    with tenant_session(tenant_id) as session:
        # Customer profiles are synthetic aggregates derived only from this fixed demo set.
        for i, (name, city, segment) in enumerate(names):
            customer_id = f"DEMO-CUST-{i + 1:03d}"
            customer_orders = [x for x in orders_data if x["customer_index"] == i]
            lifetime = sum((x["product"]["price"] for x in customer_orders), Decimal("0.00"))
            row_id = _id(tenant_id, "customer", customer_id)
            if session.get(DemoCustomerProfile, row_id) is None:
                session.add(DemoCustomerProfile(
                    id=row_id, tenant_id=tenant_id, customer_id=customer_id,
                    display_name=name, email=f"customer{i + 1:02d}@example.invalid",
                    city=city, segment=segment, order_count=len(customer_orders),
                    lifetime_value=lifetime,
                    first_order_at=customer_orders[0]["created"],
                    last_order_at=customer_orders[-1]["created"], source_label=DEMO_LABEL,
                ))
                inserted["customers"] += 1

        order_ids = []
        review_ids = []
        order_issue_map = {}
        for index, item in enumerate(orders_data):
            order_key = item["key"]
            order_id = f"DEMO-{tenant_prefix}-{order_key.upper()}"
            order_ids.append(order_id)
            customer_index = item["customer_index"]
            customer_name, _, _ = names[customer_index]
            customer_id = f"DEMO-CUST-{customer_index + 1:03d}"
            product = item["product"]
            issue_category, severity, rating, review_text = item["issue"]
            order_issue_map[order_id] = (issue_category, severity, rating, review_text, product)
            if session.get(TenantOrder, order_id) is None:
                session.add(TenantOrder(
                    id=order_id, tenant_id=tenant_id, customer_id=customer_id,
                    customer_name=customer_name, product=product["name"],
                    batch=product["batch"], amount=product["price"], currency="INR",
                    payment_status="DEMO_ONLY", paypal_order_id=None, capture_id=None,
                    created_at=item["created"], shipped_at=item["created"] + timedelta(days=1),
                    delivered_at=item["created"] + timedelta(days=3), hygiene_item=False,
                ))
                inserted["orders"] += 1
            review_id = f"DEMO-{tenant_prefix}-REV-{index + 1:03d}"
            review_ids.append(review_id)
            cluster = (
                "DEMO-CLUSTER-PACKAGING-BATCH-A" if issue_category in {"PACKAGING_DAMAGE", "LEAKAGE"} and product["batch"] == "BATCH-A"
                else f"DEMO-CLUSTER-{issue_category}"
            )
            if session.get(TenantReview, review_id) is None:
                session.add(TenantReview(
                    id=review_id, tenant_id=tenant_id, customer_id=customer_id,
                    customer_name=customer_name, order_id=order_id,
                    product=product["name"], rating=rating, text=review_text,
                    category=issue_category, severity=severity,
                    complaint_cluster_id=cluster,
                    created_at=item["created"] + timedelta(hours=4),
                ))
                inserted["reviews"] += 1

            cost_id = _id(tenant_id, "order-cost", order_id)
            if session.get(OrderCost, cost_id) is None:
                session.add(OrderCost(
                    id=cost_id, tenant_id=tenant_id, order_id=order_id,
                    cogs=(product["price"] * Decimal("0.38")).quantize(Decimal("0.01")),
                    shipping_out=Decimal("42.00"), payment_fee=Decimal("0.00"),
                    packaging=Decimal("18.00"), other_cost=Decimal("0.00"),
                    updated_by=SYSTEM_ACTOR,
                ))
                inserted["order_costs"] += 1

        # Product/batch signals are deterministic counts from the synthetic reviews above.
        for product in products:
            matching = [x for x in orders_data if x["product"]["key"] == product["key"]]
            issues = [x for x in matching if x["issue"][0] in {"PACKAGING_DAMAGE", "LEAKAGE"}]
            ratings = [x["issue"][2] for x in matching]
            insight_id = _id(tenant_id, "product-batch", product["key"] + ":" + product["batch"])
            if session.get(DemoProductBatchInsight, insight_id) is None:
                session.add(DemoProductBatchInsight(
                    id=insight_id, tenant_id=tenant_id, product_key=product["key"],
                    product_name=product["name"], sku=product["sku"], batch=product["batch"],
                    units_sold=len(matching), complaint_count=len(issues),
                    damage_count=sum(1 for x in issues if x["issue"][0] == "PACKAGING_DAMAGE"),
                    leak_count=sum(1 for x in issues if x["issue"][0] == "LEAKAGE"),
                    average_rating=Decimal(sum(ratings)) / Decimal(len(ratings)),
                    risk_level="ELEVATED" if len(issues) >= 5 else "MODERATE",
                    signals={
                        "source": DEMO_LABEL,
                        "basis": "synthetic seeded reviews; not a live quality-control finding",
                        "complaint_categories": sorted({x["issue"][0] for x in issues}),
                        "recommended_action": "Inspect packaging and handling records; do not quarantine inventory automatically.",
                    },
                    source_label=DEMO_LABEL,
                ))
                inserted["product_batch_insights"] += 1

        # Six proposals are records for human review only; no provider references or captures.
        proposal_indexes = [0, 1, 3, 6, 9, 12]
        for n, order_index in enumerate(proposal_indexes, start=1):
            order_id = order_ids[order_index]
            issue = order_issue_map[order_id]
            refund_id = f"DEMO-{tenant_prefix}-REFUND-{n:03d}"
            idem = f"{SEED_VERSION}:{tenant_id}:refund:{n:03d}"
            if session.get(TenantRefund, refund_id) is None:
                session.add(TenantRefund(
                    id=refund_id, tenant_id=tenant_id, order_id=order_id,
                    capture_id=None, amount=issue[4]["price"], currency="INR",
                    reason=f"Synthetic proposal: {issue[0].replace('_', ' ').lower()}",
                    status="PROPOSED", idempotency_key=idem,
                    paypal_refund_id=None, paypal_status=None,
                ))
                inserted["refund_proposals"] += 1

        # Three illustrative dispute records. They are not PayPal disputes.
        dispute_indexes = [0, 7, 13]
        for n, order_index in enumerate(dispute_indexes, start=1):
            order_id = order_ids[order_index]
            dispute_id = f"DEMO-{tenant_prefix}-DISPUTE-{n:03d}"
            if session.get(TenantDispute, dispute_id) is None:
                session.add(TenantDispute(
                    id=dispute_id, tenant_id=tenant_id, order_id=order_id,
                    reason="Synthetic customer delivery/condition dispute for workflow demonstration.",
                    status="OPEN", customer_message="Illustrative customer statement; not a real customer communication.",
                    evidence={"source": DEMO_LABEL, "provider_dispute": False, "payment_action": "NONE"},
                ))
                inserted["disputes"] += 1
            evidence_id = f"DEMO-{tenant_prefix}-EVIDENCE-DISPUTE-{n:03d}"
            if session.get(TenantEvidence, evidence_id) is None:
                session.add(TenantEvidence(
                    id=evidence_id, tenant_id=tenant_id, order_id=order_id,
                    evidence_type="DELIVERY_PHOTO_REFERENCE",
                    description="Synthetic evidence placeholder. No file is attached or claimed to be verified.",
                    storage_key=None, sha256=None, integrity_status="DEMO_NOT_VERIFIED",
                ))
                inserted["evidence"] += 1

        # Six linked resolution cases; each timeline is auditable and explicitly synthetic.
        case_indexes = [0, 1, 3, 6, 9, 12]
        case_ids = []
        for n, order_index in enumerate(case_indexes, start=1):
            order_id = order_ids[order_index]
            issue = order_issue_map[order_id]
            case_id = _id(tenant_id, "resolution-case", f"case-{n:03d}")
            case_ids.append(case_id)
            case_type = "REFUND" if n % 2 else "RETURN"
            amount = issue[4]["price"]
            if session.get(ResolutionCase, case_id) is None:
                session.add(ResolutionCase(
                    id=case_id, tenant_id=tenant_id, order_id=order_id,
                    case_type=case_type, status="OPEN",
                    reason=f"Synthetic case: {issue[3]}",
                    complaint_cluster_id=(
                        "DEMO-CLUSTER-PACKAGING-BATCH-A"
                        if issue[0] in {"PACKAGING_DAMAGE", "LEAKAGE"} and issue[4]["batch"] == "BATCH-A"
                        else f"DEMO-CLUSTER-{issue[0]}"
                    ),
                    requested_amount=amount, estimated_loss=(amount * Decimal("0.22")).quantize(Decimal("0.01")),
                    realized_loss=None, recoverable_inventory_estimate=Decimal("0.00"),
                    recovered_inventory_actual=None, return_reason_code=issue[0],
                    created_by=actor_user_id or SYSTEM_ACTOR,
                ))
                inserted["financial_cases"] += 1

            for event_no, event_type in enumerate(("CASE_CREATED", "EVIDENCE_REVIEW_PENDING", "HUMAN_DECISION_REQUIRED"), start=1):
                event_id = _id(tenant_id, "case-event", f"{case_id}:{event_no}")
                if session.get(FinancialEvent, event_id) is None:
                    session.add(FinancialEvent(
                        id=event_id, tenant_id=tenant_id, case_id=case_id,
                        event_type=event_type, actor_id=SYSTEM_ACTOR,
                        payload={
                            "source": DEMO_LABEL,
                            "note": "Illustrative workflow event; no provider or inventory action occurred.",
                            "sequence": event_no,
                        },
                        created_at=now - timedelta(minutes=(4 - event_no) * 5),
                    ))
                    inserted["case_events"] += 1

            evidence_id = f"DEMO-{tenant_prefix}-EVIDENCE-CASE-{n:03d}"
            if session.get(TenantEvidence, evidence_id) is None:
                session.add(TenantEvidence(
                    id=evidence_id, tenant_id=tenant_id, order_id=order_id,
                    evidence_type="CASE_ATTACHMENT_PLACEHOLDER",
                    description="Synthetic case evidence placeholder; upload a real document before any decision.",
                    storage_key=None, sha256=None, integrity_status="DEMO_NOT_VERIFIED",
                ))
                inserted["evidence"] += 1

            disposition_id = _id(tenant_id, "inventory-instruction", case_id)
            if session.get(InventoryDisposition, disposition_id) is None:
                session.add(InventoryDisposition(
                    id=disposition_id, tenant_id=tenant_id, case_id=case_id,
                    sku=issue[4]["sku"], quantity=1, disposition="INSPECT",
                    estimated_recovery=Decimal("0.00"), realized_recovery=None,
                    warehouse_reference=None,
                    note="Illustrative inspection instruction only; inventory was not changed.",
                    created_by=actor_user_id or SYSTEM_ACTOR,
                ))
                inserted["inventory_instructions"] += 1

        # Tenant audit trail uses a null actor for the automated synthetic seed.
        audit_specs = [
            ("DEMO_DATA_SEEDED", "DEMO_DATASET", SEED_VERSION),
            ("SYNTHETIC_ORDERS_CREATED", "ORDER_SET", "30-orders"),
            ("SYNTHETIC_REVIEWS_LINKED", "REVIEW_SET", "30-reviews"),
            ("SYNTHETIC_CASES_CREATED", "FINANCIAL_CASE_SET", "6-cases"),
        ]
        for event, entity_type, entity_id in audit_specs:
            audit_id = _id(tenant_id, "audit", event)
            if session.get(TenantAuditEvent, audit_id) is None:
                session.add(TenantAuditEvent(
                    id=audit_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
                    event=event, entity_type=entity_type, entity_id=entity_id,
                    detail={
                        "source": DEMO_LABEL, "seed_version": SEED_VERSION,
                        "paypal_transactions_created": 0, "payment_confirmations_created": 0,
                    },
                ))
                inserted["audit_events"] += 1

    return {
        "status": "seeded" if any(inserted.values()) else "already_seeded",
        "tenant_scope": "authenticated_tenant_only",
        "source": DEMO_LABEL,
        "seed_version": SEED_VERSION,
        "inserted": inserted,
        "safety": {
            "paypal_transactions_created": 0,
            "paypal_capture_ids_created": 0,
            "provider_refunds_executed": 0,
            "provider_disputes_created": 0,
            "inventory_mutations": 0,
            "existing_merchant_records_overwritten": 0,
        },
    }


@router.get("/graph")
def demo_customer_order_graph(p=Depends(identity.current_principal)):
    """Return a tenant-filtered connected view of demo customers and order lifecycle records."""
    if not identity.AUTH_AVAILABLE:
        raise HTTPException(503, "Identity dependencies unavailable")
    tenant_id = p["tenant_id"]
    with tenant_session(tenant_id) as session:
        customers = session.scalars(select(DemoCustomerProfile).where(
            DemoCustomerProfile.tenant_id == tenant_id
        ).order_by(DemoCustomerProfile.display_name)).all()
        orders = session.scalars(select(TenantOrder).where(
            TenantOrder.tenant_id == tenant_id
        ).order_by(TenantOrder.created_at)).all()
        reviews = session.scalars(select(TenantReview).where(
            TenantReview.tenant_id == tenant_id
        )).all()
        refunds = session.scalars(select(TenantRefund).where(
            TenantRefund.tenant_id == tenant_id
        )).all()
        disputes = session.scalars(select(TenantDispute).where(
            TenantDispute.tenant_id == tenant_id
        )).all()
        evidence = session.scalars(select(TenantEvidence).where(
            TenantEvidence.tenant_id == tenant_id
        )).all()
        cases = session.scalars(select(ResolutionCase).where(
            ResolutionCase.tenant_id == tenant_id
        )).all()

        reviews_by_order = {}
        for row in reviews:
            reviews_by_order.setdefault(row.order_id, []).append({
                "id": row.id, "rating": row.rating, "category": row.category,
                "severity": row.severity, "text": row.text,
                "complaint_cluster_id": row.complaint_cluster_id,
            })
        refunds_by_order = {}
        for row in refunds:
            refunds_by_order.setdefault(row.order_id, []).append({
                "id": row.id, "status": row.status, "amount": str(row.amount),
                "currency": row.currency, "provider_action": "NONE",
            })
        disputes_by_order = {}
        for row in disputes:
            disputes_by_order.setdefault(row.order_id, []).append({
                "id": row.id, "status": row.status, "reason": row.reason,
                "provider_dispute": False,
            })
        evidence_by_order = {}
        for row in evidence:
            evidence_by_order.setdefault(row.order_id, []).append({
                "id": row.id, "type": row.evidence_type,
                "integrity_status": row.integrity_status,
            })
        cases_by_order = {}
        for row in cases:
            cases_by_order.setdefault(row.order_id, []).append({
                "id": row.id, "case_type": row.case_type, "status": row.status,
                "requested_amount": str(row.requested_amount),
                "complaint_cluster_id": row.complaint_cluster_id,
            })
        orders_by_customer = {}
        for row in orders:
            orders_by_customer.setdefault(row.customer_id, []).append({
                "id": row.id, "product": row.product, "batch": row.batch,
                "amount": str(row.amount), "currency": row.currency,
                "payment_status": row.payment_status,
                "created_at": row.created_at.isoformat(),
                "reviews": reviews_by_order.get(row.id, []),
                "refund_proposals": refunds_by_order.get(row.id, []),
                "disputes": disputes_by_order.get(row.id, []),
                "evidence": evidence_by_order.get(row.id, []),
                "financial_cases": cases_by_order.get(row.id, []),
            })
        return {
            "source": DEMO_LABEL,
            "tenant_scope": "authenticated_tenant_only",
            "customers": [{
                "customer_id": row.customer_id, "name": row.display_name,
                "city": row.city, "segment": row.segment,
                "order_count": row.order_count,
                "lifetime_value": str(row.lifetime_value),
                "currency": "INR",
                "orders": orders_by_customer.get(row.customer_id, []),
            } for row in customers],
        }


@router.get("/product-batches")
def demo_product_batch_insights(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE:
        raise HTTPException(503, "Identity dependencies unavailable")
    tenant_id = p["tenant_id"]
    with tenant_session(tenant_id) as session:
        rows = session.scalars(select(DemoProductBatchInsight).where(
            DemoProductBatchInsight.tenant_id == tenant_id
        ).order_by(DemoProductBatchInsight.product_name)).all()
        return [{
            "product": row.product_name, "sku": row.sku, "batch": row.batch,
            "units_sold": row.units_sold, "complaint_count": row.complaint_count,
            "damage_count": row.damage_count, "leak_count": row.leak_count,
            "average_rating": str(row.average_rating), "risk_level": row.risk_level,
            "signals": row.signals, "source": row.source_label,
        } for row in rows]


def _principal(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE:
        raise HTTPException(503, "Identity dependencies unavailable")
    return p


@router.post("/seed")
def seed_demo_endpoint(p=Depends(_principal)):
    if os.getenv("MERCHANTOS_DEMO_SEED_ENABLED", "false").strip().lower() not in {"1", "true", "yes"}:
        raise HTTPException(404, "Demo seeding is disabled for this deployment")
    if p.get("role") != "OWNER":
        raise HTTPException(403, "Only the workspace OWNER can seed illustrative demo data")
    return seed_tenant_demo_data(p["tenant_id"], p["user_id"])
