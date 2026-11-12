from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import auth_sqlalchemy
from app.auth_sqlalchemy import Tenant
from app.demo_seed import seed_tenant_demo_data
from app.domain_models import (
    DemoCustomerProfile, DemoProductBatchInsight, TenantAuditEvent,
    TenantDispute, TenantEvidence, TenantOrder, TenantRefund, TenantReview,
)
from app.financial_lifecycle import (
    FinancialEvent, InventoryDisposition, OrderCost, ResolutionCase,
)
from app.orm_base import Base


def test_unified_demo_seed_is_idempotent_and_tenant_isolated(monkeypatch, tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'demo-seed-test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(auth_sqlalchemy, "engine", engine)
    monkeypatch.setattr(auth_sqlalchemy, "SessionLocal", test_sessions)

    tenant_a = "tenant-demo-a"
    tenant_b = "tenant-demo-b"
    with test_sessions() as session:
        session.add_all([
            Tenant(id=tenant_a, name="Demo A"),
            Tenant(id=tenant_b, name="Demo B"),
        ])
        session.commit()

    first = seed_tenant_demo_data(tenant_a)
    second = seed_tenant_demo_data(tenant_a)
    other_tenant = seed_tenant_demo_data(tenant_b)

    assert first["status"] == "seeded"
    assert first["inserted"]["orders"] == 30
    assert first["inserted"]["reviews"] == 30
    assert first["inserted"]["financial_cases"] == 6
    assert first["inserted"]["refund_proposals"] == 6
    assert second["status"] == "already_seeded"
    assert not any(second["inserted"].values())
    assert other_tenant["status"] == "seeded"

    tenant_models = [
        (DemoCustomerProfile, 15),
        (DemoProductBatchInsight, 3),
        (TenantOrder, 30),
        (TenantReview, 30),
        (TenantRefund, 6),
        (TenantDispute, 3),
        (TenantEvidence, 9),
        (TenantAuditEvent, 4),
        (OrderCost, 30),
        (ResolutionCase, 6),
        (FinancialEvent, 18),
        (InventoryDisposition, 6),
    ]
    with test_sessions() as session:
        for model, expected in tenant_models:
            count = session.scalar(
                select(func.count()).select_from(model).where(model.tenant_id == tenant_a)
            )
            assert count == expected, (model.__name__, count, expected)

        ids_a = set(session.scalars(select(TenantOrder.id).where(TenantOrder.tenant_id == tenant_a)))
        ids_b = set(session.scalars(select(TenantOrder.id).where(TenantOrder.tenant_id == tenant_b)))
        assert len(ids_a) == 30
        assert len(ids_b) == 30
        assert ids_a.isdisjoint(ids_b)

        demo_orders = session.scalars(select(TenantOrder).where(TenantOrder.tenant_id == tenant_a)).all()
        assert all(order.payment_status == "DEMO_ONLY" for order in demo_orders)
        assert all(order.paypal_order_id is None and order.capture_id is None for order in demo_orders)
