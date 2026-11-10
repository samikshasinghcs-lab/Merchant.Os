from types import SimpleNamespace
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.orm_base import Base
from app.completion_models import FinancialApprovalRequest
from app.financial_controls import approval_digest
from app.financial_approval_service import reconcile_refund_approval


@pytest.fixture
def tenant_db(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    from sqlalchemy import Table, Column, String
    if 'tenants' not in Base.metadata.tables:
        Table('tenants', Base.metadata, Column('id', String(36), primary_key=True), Column('name', String(160), nullable=False))
    if 'users' not in Base.metadata.tables:
        Table('users', Base.metadata, Column('id', String(36), primary_key=True), Column('email', String(320), nullable=False), Column('name', String(160), nullable=False), Column('password_hash', String(255), nullable=False))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setitem(sys.modules, 'app.auth_sqlalchemy', SimpleNamespace(engine=engine, SessionLocal=factory))
    with factory() as session:
        session.execute(Base.metadata.tables['tenants'].insert().values(id='tenant-1', name='Test Merchant'))
        session.execute(Base.metadata.tables['users'].insert().values(id='maker-1', email='maker@example.test', name='Maker', password_hash='x'))
        digest = approval_digest(tenant_id='tenant-1', capture_id='CAPTURE_123',
                                 amount='25.00', currency='USD', reason='Customer returned item')
        session.add(FinancialApprovalRequest(
            id='approval-1', tenant_id='tenant-1', request_key='request-1234', action='REFUND',
            capture_id='CAPTURE_123', amount='25.00', currency='USD',
            reason='Customer returned item', policy_digest=digest, requester_id='maker-1',
            status='PENDING_RECONCILIATION'))
        session.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


class FakePayPal:
    def __init__(self, capture):
        self.capture = capture
        self.requested_capture_ids = []

    def get_capture(self, capture_id):
        self.requested_capture_ids.append(capture_id)
        return self.capture


def test_reconciliation_uses_server_fetched_completed_capture(tenant_db):
    paypal = FakePayPal({'id': 'CAPTURE_123', 'status': 'COMPLETED',
                         'amount': {'value': '100.00', 'currency_code': 'USD'}})
    result = reconcile_refund_approval(tenant_id='tenant-1', approval_id='approval-1', adapter=paypal)
    assert paypal.requested_capture_ids == ['CAPTURE_123']
    assert result['status'] == 'PENDING_APPROVAL'
    with tenant_db() as session:
        row = session.get(FinancialApprovalRequest, 'approval-1')
        assert row.status == 'PENDING_APPROVAL'
        assert 'Canonical PayPal capture read reconciled' in row.decision_note


def test_partial_refund_capture_fails_closed_instead_of_guessing_balance(tenant_db):
    paypal = FakePayPal({'id': 'CAPTURE_123', 'status': 'PARTIALLY_REFUNDED',
                         'amount': {'value': '100.00', 'currency_code': 'USD'}})
    result = reconcile_refund_approval(tenant_id='tenant-1', approval_id='approval-1', adapter=paypal)
    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'REFUND_HISTORY_NOT_AUTHORITATIVELY_AVAILABLE'
    with tenant_db() as session:
        assert session.get(FinancialApprovalRequest, 'approval-1').status == 'BLOCKED'


def test_provider_failure_does_not_advance_approval(tenant_db):
    class BrokenPayPal:
        def get_capture(self, capture_id):
            raise RuntimeError('network unavailable')
    with pytest.raises(RuntimeError):
        reconcile_refund_approval(tenant_id='tenant-1', approval_id='approval-1', adapter=BrokenPayPal())
    with tenant_db() as session:
        assert session.get(FinancialApprovalRequest, 'approval-1').status == 'PENDING_RECONCILIATION'
