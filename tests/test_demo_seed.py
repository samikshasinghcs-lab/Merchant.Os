from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.auth_sqlalchemy import Base, Tenant, User
from app.domain_models import TenantOrder, TenantReview, TenantRefund, TenantDispute, TenantEvidence
from app.financial_lifecycle import ResolutionCase, FinancialEvent
from app.demo_seed import seed_tenant_demo_data


def _database():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _identity(session, tenant_id, user_id):
    session.add(Tenant(id=tenant_id, name=f"Tenant {tenant_id}"))
    session.add(User(
        id=user_id, email=f"{user_id}@example.test", name="Demo Owner",
        password_hash="not-a-real-login-hash",
    ))
    session.flush()


def _count(session, model, tenant_id):
    return session.scalar(
        select(func.count(model.id)).where(model.tenant_id == tenant_id)
    )


def test_seed_is_idempotent_and_relationships_are_coherent():
    engine = _database()
    with Session(engine) as session:
        with session.begin():
            _identity(session, "tenant-a", "owner-a")
            first = seed_tenant_demo_data(session, "tenant-a", "owner-a")
        with session.begin():
            second = seed_tenant_demo_data(session, "tenant-a", "owner-a")

        assert first["inserted"]["orders"] == 30
        assert first["inserted"]["reviews"] == 12
        assert first["inserted"]["refund_proposals"] == 6
        assert first["inserted"]["disputes"] == 4
        assert first["inserted"]["evidence_metadata"] == 8
        assert first["inserted"]["financial_cases"] == 10
        assert second["status"] == "ALREADY_PRESENT"
        assert all(value == 0 for value in second["inserted"].values())

        orders = session.scalars(select(TenantOrder).where(TenantOrder.tenant_id == "tenant-a")).all()
        order_ids = {row.id for row in orders}
        assert len(order_ids) == 30
        assert all(row.payment_status == "UNPAID" for row in orders)
        assert all(row.paypal_order_id is None and row.capture_id is None for row in orders)

        reviews = session.scalars(select(TenantReview).where(TenantReview.tenant_id == "tenant-a")).all()
        assert len(reviews) == 12
        assert all(row.order_id in order_ids for row in reviews)

        refunds = session.scalars(select(TenantRefund).where(TenantRefund.tenant_id == "tenant-a")).all()
        assert len(refunds) == 6
        assert all(row.order_id in order_ids for row in refunds)
        assert all(row.paypal_refund_id is None and row.paypal_status is None and row.capture_id is None for row in refunds)

        disputes = session.scalars(select(TenantDispute).where(TenantDispute.tenant_id == "tenant-a")).all()
        evidence = session.scalars(select(TenantEvidence).where(TenantEvidence.tenant_id == "tenant-a")).all()
        cases = session.scalars(select(ResolutionCase).where(ResolutionCase.tenant_id == "tenant-a")).all()
        events = session.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id == "tenant-a")).all()
        assert all(row.order_id in order_ids for row in disputes)
        assert all(row.order_id in order_ids for row in evidence)
        assert all(row.order_id in order_ids for row in cases)
        assert len(events) == len(cases)
        assert all(row.realized_loss is None for row in cases)
        assert all(row.storage_key is None and row.sha256 is None for row in evidence)
    engine.dispose()


def test_seed_data_isolated_between_tenants():
    engine = _database()
    with Session(engine) as session:
        with session.begin():
            _identity(session, "tenant-a", "owner-a")
            _identity(session, "tenant-b", "owner-b")
            seed_tenant_demo_data(session, "tenant-a", "owner-a")
            seed_tenant_demo_data(session, "tenant-b", "owner-b")

        assert _count(session, TenantOrder, "tenant-a") == 30
        assert _count(session, TenantOrder, "tenant-b") == 30
        a_ids = set(session.scalars(select(TenantOrder.id).where(TenantOrder.tenant_id == "tenant-a")).all())
        b_ids = set(session.scalars(select(TenantOrder.id).where(TenantOrder.tenant_id == "tenant-b")).all())
        assert a_ids.isdisjoint(b_ids)
    engine.dispose()
