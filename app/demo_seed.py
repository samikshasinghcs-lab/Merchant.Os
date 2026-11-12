"""Explicit, idempotent tenant-scoped illustrative demo dataset.

This module never creates PayPal identifiers, captures, refunds, provider disputes,
or successful payment states. It only seeds local synthetic merchant records.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from .domain_models import (
    TenantOrder, TenantReview, TenantRefund, TenantDispute,
    TenantEvidence, TenantAuditEvent,
)
from .financial_lifecycle import (
    ResolutionCase, FinancialEvent, OrderCost,
)


def _id(tenant_id: str, kind: str, key: str) -> str:
    return f"demo-{uuid5(NAMESPACE_URL, f'merchantos:{tenant_id}:{kind}:{key}').hex}"


def seed_tenant_demo_data(session, tenant_id: str, actor_user_id: str) -> dict:
    """Insert a coherent 30-order story once per tenant; safe to call repeatedly."""
    now = datetime.now(timezone.utc)
    customers = [
        ("CUST-001", "Aarav Mehta"), ("CUST-002", "Diya Nair"),
        ("CUST-003", "Kabir Shah"), ("CUST-004", "Anaya Rao"),
        ("CUST-005", "Ishaan Das"), ("CUST-006", "Mira Iyer"),
        ("CUST-007", "Reyansh Gupta"), ("CUST-008", "Sana Khan"),
        ("CUST-009", "Vivaan Joshi"), ("CUST-010", "Tara Menon"),
    ]
    products = [
        ("Aurora Wireless Earbuds", "BATCH-AUR-06", Decimal("2499.00")),
        ("Terra Insulated Bottle", "BATCH-TER-04", Decimal("899.00")),
        ("Lumen Desk Lamp", "BATCH-LUM-03", Decimal("1799.00")),
    ]
    orders = []
    for i in range(30):
        customer_id, customer_name = customers[i % len(customers)]
        product, batch, base_amount = products[(i * 7 + i // 3) % len(products)]
        order_id = _id(tenant_id, "order", f"{i + 1:02d}")
        orders.append({
            "id": order_id, "customer_id": customer_id,
            "customer_name": customer_name, "product": product,
            "batch": batch, "amount": base_amount + Decimal((i % 4) * 100),
            "currency": "INR", "payment_status": "UNPAID",
            "created_at": now - timedelta(days=30 - i),
            "shipped_at": now - timedelta(days=max(1, 28 - i)) if i % 3 else None,
            "delivered_at": now - timedelta(days=max(1, 25 - i)) if i % 4 else None,
            "hygiene_item": False,
        })

    counts = {
        "orders": 0, "reviews": 0, "refund_proposals": 0,
        "disputes": 0, "evidence_metadata": 0, "financial_cases": 0,
        "order_costs": 0, "timeline_events": 0,
    }
    order_by_index = {i + 1: row for i, row in enumerate(orders)}
    existing_orders = set(session.scalars(select(TenantOrder.id).where(
        TenantOrder.tenant_id == tenant_id
    )).all())

    for row in orders:
        if row["id"] in existing_orders:
            continue
        session.add(TenantOrder(tenant_id=tenant_id, **row))
        counts["orders"] += 1

    # Twelve reviews are linked to real seeded order IDs and matching customers.
    review_specs = [
        (1, 5, "Arrived quickly and works exactly as described.", "POSITIVE", "LOW"),
        (2, 2, "The bottle lid started leaking after two days.", "LEAKAGE", "MEDIUM"),
        (4, 1, "One earbud stopped charging after a week.", "CHARGING", "HIGH"),
        (5, 4, "Good product; packaging was slightly damaged.", "PACKAGING", "LOW"),
        (7, 2, "Desk lamp flickers intermittently.", "ELECTRICAL", "HIGH"),
        (9, 3, "Delivery took longer than expected.", "DELIVERY", "MEDIUM"),
        (11, 1, "The left earbud has no sound.", "AUDIO", "HIGH"),
        (13, 5, "Excellent quality for the price.", "POSITIVE", "LOW"),
        (16, 2, "Bottle cap does not seal properly.", "LEAKAGE", "MEDIUM"),
        (19, 1, "Lamp switch became unresponsive.", "ELECTRICAL", "HIGH"),
        (23, 4, "Comfortable fit and clear sound.", "POSITIVE", "LOW"),
        (27, 2, "The parcel box was crushed on arrival.", "PACKAGING", "MEDIUM"),
    ]
    existing_reviews = set(session.scalars(select(TenantReview.id).where(
        TenantReview.tenant_id == tenant_id
    )).all())
    for index, (order_no, rating, text, category, severity) in enumerate(review_specs, 1):
        order = order_by_index[order_no]
        review_id = _id(tenant_id, "review", f"{index:02d}")
        if review_id in existing_reviews:
            continue
        session.add(TenantReview(
            id=review_id, tenant_id=tenant_id,
            customer_id=order["customer_id"], customer_name=order["customer_name"],
            order_id=order["id"], product=order["product"], rating=rating,
            text=text, category=category, severity=severity,
            complaint_cluster_id=category,
            created_at=order["created_at"] + timedelta(days=2),
        ))
        counts["reviews"] += 1

    # Local proposals only. Provider references intentionally remain NULL.
    refund_specs = [
        (2, Decimal("899.00"), "Bottle lid leakage reported"),
        (4, Decimal("2499.00"), "Earbud charging failure reported"),
        (7, Decimal("1799.00"), "Intermittent lamp flicker reported"),
        (11, Decimal("2499.00"), "Left earbud audio failure reported"),
        (16, Decimal("899.00"), "Bottle seal failure reported"),
        (19, Decimal("1799.00"), "Lamp switch failure reported"),
    ]
    existing_refunds = set(session.scalars(select(TenantRefund.id).where(
        TenantRefund.tenant_id == tenant_id
    )).all())
    for index, (order_no, amount, reason) in enumerate(refund_specs, 1):
        order = order_by_index[order_no]
        rid = _id(tenant_id, "refund", f"{index:02d}")
        if rid in existing_refunds:
            continue
        session.add(TenantRefund(
            id=rid, tenant_id=tenant_id, order_id=order["id"],
            capture_id=None, amount=amount, currency="INR", reason=reason,
            status="PROPOSED_DEMO", idempotency_key=_id(tenant_id, "refund-key", f"{index:02d}"),
            paypal_refund_id=None, paypal_status=None,
            created_at=now - timedelta(days=5 - index),
        ))
        counts["refund_proposals"] += 1

    dispute_specs = [
        (4, "Product reported defective; merchant review required."),
        (7, "Customer reports intermittent electrical fault."),
        (11, "Audio defect reported; evidence review pending."),
        (27, "Delivery packaging damage reported."),
    ]
    existing_disputes = set(session.scalars(select(TenantDispute.id).where(
        TenantDispute.tenant_id == tenant_id
    )).all())
    for index, (order_no, reason) in enumerate(dispute_specs, 1):
        order = order_by_index[order_no]
        did = _id(tenant_id, "dispute", f"{index:02d}")
        if did in existing_disputes:
            continue
        session.add(TenantDispute(
            id=did, tenant_id=tenant_id, order_id=order["id"],
            reason=reason, status="ILLUSTRATIVE_OPEN",
            customer_message=reason,
            evidence={"source": "ILLUSTRATIVE_SYNTHETIC", "provider_case_id": None},
            created_at=now - timedelta(days=4 - index),
        ))
        counts["disputes"] += 1

    evidence_specs = [
        (4, "PRODUCT_PHOTO", "Illustrative product-condition photo metadata; no file attached."),
        (4, "CUSTOMER_COMMUNICATION", "Illustrative customer communication metadata; no file attached."),
        (7, "TEST_RESULT", "Illustrative inspection note; not a certified test result."),
        (11, "PRODUCT_PHOTO", "Illustrative product-condition photo metadata; no file attached."),
        (27, "DELIVERY_CONFIRMATION", "Illustrative delivery record metadata; no carrier verification."),
        (2, "CUSTOMER_COMMUNICATION", "Illustrative customer communication metadata; no file attached."),
        (16, "PRODUCT_PHOTO", "Illustrative product-condition photo metadata; no file attached."),
        (19, "TEST_RESULT", "Illustrative inspection note; not a certified test result."),
    ]
    existing_evidence = set(session.scalars(select(TenantEvidence.id).where(
        TenantEvidence.tenant_id == tenant_id
    )).all())
    for index, (order_no, kind, description) in enumerate(evidence_specs, 1):
        order = order_by_index[order_no]
        eid = _id(tenant_id, "evidence", f"{index:02d}")
        if eid in existing_evidence:
            continue
        session.add(TenantEvidence(
            id=eid, tenant_id=tenant_id, order_id=order["id"],
            evidence_type=kind, description="ILLUSTRATIVE METADATA ONLY — " + description,
            storage_key=None, sha256=None, integrity_status="ILLUSTRATIVE_METADATA_ONLY",
            created_at=now - timedelta(days=3),
        ))
        counts["evidence_metadata"] += 1

    # Financial lifecycle cases and timeline entries are local records only.
    case_specs = [
        (2, "RETURN", "LEAKAGE", Decimal("899.00"), Decimal("520.00")),
        (4, "REFUND", "CHARGING", Decimal("2499.00"), Decimal("1650.00")),
        (7, "RETURN", "ELECTRICAL", Decimal("1799.00"), Decimal("1100.00")),
        (11, "REFUND", "AUDIO", Decimal("2499.00"), Decimal("1650.00")),
        (16, "RETURN", "LEAKAGE", Decimal("899.00"), Decimal("520.00")),
        (19, "REFUND", "ELECTRICAL", Decimal("1799.00"), Decimal("1100.00")),
        (27, "RETURN", "PACKAGING", Decimal("1799.00"), Decimal("900.00")),
        (5, "EXCHANGE", "PACKAGING", Decimal("0.00"), Decimal("150.00")),
        (13, "REFUND", "CUSTOMER_REQUEST", Decimal("1799.00"), Decimal("700.00")),
        (23, "EXCHANGE", "CUSTOMER_REQUEST", Decimal("0.00"), Decimal("120.00")),
    ]
    existing_cases = set(session.scalars(select(ResolutionCase.id).where(
        ResolutionCase.tenant_id == tenant_id
    )).all())
    existing_costs = set(session.scalars(select(OrderCost.order_id).where(
        OrderCost.tenant_id == tenant_id
    )).all())
    for index, (order_no, case_type, reason_code, requested, loss) in enumerate(case_specs, 1):
        order = order_by_index[order_no]
        case_id = _id(tenant_id, "financial-case", f"{index:02d}")
        if case_id not in existing_cases:
            case = ResolutionCase(
                id=case_id, tenant_id=tenant_id, order_id=order["id"],
                case_type=case_type, status="OPEN",
                reason=f"Illustrative {reason_code.lower().replace('_', ' ')} case linked to {order['id']}.",
                complaint_cluster_id=reason_code, requested_amount=requested,
                estimated_loss=loss, realized_loss=None,
                recoverable_inventory_estimate=Decimal("0.00"),
                recovered_inventory_actual=None, return_reason_code=reason_code,
                created_by=actor_user_id,
                created_at=now - timedelta(days=8 - (index % 6)),
                updated_at=now - timedelta(days=8 - (index % 6)),
            )
            session.add(case)
            session.add(FinancialEvent(
                id=_id(tenant_id, "financial-event", f"{index:02d}"),
                tenant_id=tenant_id, case_id=case_id,
                event_type="ILLUSTRATIVE_CASE_CREATED", actor_id=actor_user_id,
                payload={"source": "ILLUSTRATIVE_SYNTHETIC", "order_id": order["id"],
                         "payment_action": "NONE", "provider_execution": False},
                created_at=case.created_at,
            ))
            counts["financial_cases"] += 1
            counts["timeline_events"] += 1

        if order["id"] not in existing_costs:
            session.add(OrderCost(
                id=_id(tenant_id, "order-cost", str(order_no)),
                tenant_id=tenant_id, order_id=order["id"],
                cogs=(order["amount"] * Decimal("0.42")).quantize(Decimal("0.01")),
                shipping_out=Decimal("65.00"), payment_fee=Decimal("0.00"),
                packaging=Decimal("25.00"), other_cost=Decimal("0.00"),
                updated_by=actor_user_id, updated_at=now,
            ))
            counts["order_costs"] += 1

    # One tenant-scoped audit marker makes the synthetic origin explicit.
    marker_id = _id(tenant_id, "audit", "unified-demo-seed-v1")
    marker = session.scalar(select(TenantAuditEvent.id).where(
        TenantAuditEvent.tenant_id == tenant_id, TenantAuditEvent.id == marker_id
    ))
    if not marker:
        session.add(TenantAuditEvent(
            id=marker_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
            event="ILLUSTRATIVE_DEMO_DATA_SEEDED", entity_type="DEMO_DATASET",
            entity_id="merchantos-demo-v1",
            detail={
                "source": "ILLUSTRATIVE_SYNTHETIC",
                "label": "Demo data — not real customers, orders, payments or provider cases",
                "counts": {**counts, "orders_total": 30},
                "paypal_transactions_created": 0,
                "paypal_refunds_created": 0,
                "provider_confirmations_fabricated": 0,
            },
            created_at=now,
        ))

    session.flush()
    totals = {
        "orders": session.scalar(select(__import__("sqlalchemy").func.count(TenantOrder.id)).where(TenantOrder.tenant_id == tenant_id)) or 0,
        "reviews": session.scalar(select(__import__("sqlalchemy").func.count(TenantReview.id)).where(TenantReview.tenant_id == tenant_id)) or 0,
        "refund_proposals": session.scalar(select(__import__("sqlalchemy").func.count(TenantRefund.id)).where(TenantRefund.tenant_id == tenant_id)) or 0,
        "disputes": session.scalar(select(__import__("sqlalchemy").func.count(TenantDispute.id)).where(TenantDispute.tenant_id == tenant_id)) or 0,
        "evidence_metadata": session.scalar(select(__import__("sqlalchemy").func.count(TenantEvidence.id)).where(TenantEvidence.tenant_id == tenant_id)) or 0,
        "financial_cases": session.scalar(select(__import__("sqlalchemy").func.count(ResolutionCase.id)).where(ResolutionCase.tenant_id == tenant_id)) or 0,
        "timeline_events": session.scalar(select(__import__("sqlalchemy").func.count(FinancialEvent.id)).where(FinancialEvent.tenant_id == tenant_id)) or 0,
    }
    return {
        "status": "SEEDED" if any(counts.values()) else "ALREADY_PRESENT",
        "tenant_id": tenant_id,
        "source": "ILLUSTRATIVE_SYNTHETIC",
        "inserted": counts,
        "totals": totals,
        "paypal_transactions_created": 0,
        "provider_confirmations_fabricated": 0,
        "idempotent": True,
    }
