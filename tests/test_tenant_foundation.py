import pytest
from app import domain_models
from app.tenant_db import require_tenant

def test_all_domain_tables_have_tenant_id():
    names=['merchant_orders','merchant_reviews','merchant_refunds','merchant_disputes','merchant_evidence','merchant_audit_events']
    for name in names:
        table=domain_models.Base.metadata.tables[name]
        assert 'tenant_id' in table.c
        assert table.c.tenant_id.nullable is False

def test_unscoped_session_is_rejected():
    class FakeSession: info={}
    with pytest.raises(PermissionError): require_tenant(FakeSession())

def test_refund_idempotency_is_unique_per_tenant():
    constraints=[c for c in domain_models.TenantRefund.__table__.constraints if getattr(c,'name',None)=='uq_refund_tenant_idem']
    assert len(constraints)==1
    assert {col.name for col in constraints[0].columns}=={'tenant_id','idempotency_key'}


def test_postgres_rls_migration_covers_every_tenant_table_and_forces_rls():
    from pathlib import Path
    migration = Path(__file__).parents[1] / 'alembic' / 'versions' / '20261110_01_tenant_rls.py'
    source = migration.read_text()
    expected = [
        'merchant_orders', 'merchant_reviews', 'merchant_refunds', 'merchant_disputes',
        'merchant_evidence', 'merchant_audit_events', 'merchant_paypal_credentials',
        'paypal_webhook_events', 'paypal_webhook_routes', 'event_execution_traces',
        'pact_party_approvals', 'merchant_invitations', 'financial_approval_requests',
        'financial_executions',
    ]
    for table in expected:
        assert f"'{table}'" in source
    assert 'ENABLE ROW LEVEL SECURITY' in source
    assert 'FORCE ROW LEVEL SECURITY' in source
    assert "current_setting(''app.tenant_id'', true)" in source
    assert 'WITH CHECK' in source
    assert 'NULLIF' in source


def test_tenant_session_sets_transaction_local_context_with_bound_parameter(monkeypatch):
    from contextlib import contextmanager
    from app import tenant_db

    calls = []
    class FakeSession:
        info = {}
        def execute(self, statement, params):
            calls.append((str(statement), params))
        def commit(self): calls.append(('commit', {}))
        def rollback(self): calls.append(('rollback', {}))
        def close(self): calls.append(('close', {}))

    from types import SimpleNamespace
    import sys
    fake_auth = SimpleNamespace(engine=type('Engine', (), {'dialect': type('Dialect', (), {'name': 'postgresql'})()})(), SessionLocal=FakeSession)
    monkeypatch.setitem(sys.modules, 'app.auth_sqlalchemy', fake_auth)
    with tenant_db.tenant_session('tenant-safe-id') as session:
        assert tenant_db.require_tenant(session) == 'tenant-safe-id'
    sql, params = calls[0]
    assert "set_config('app.tenant_id', :tenant_id, true)" in sql
    assert params == {'tenant_id': 'tenant-safe-id'}


def test_rls_token_lookup_exceptions_are_narrow_and_select_only():
    from pathlib import Path
    source = (Path(__file__).parents[1] / 'alembic' / 'versions' / '20261110_01_tenant_rls.py').read_text()
    assert 'merchantos_webhook_route_lookup' in source
    assert 'merchantos_invitation_token_lookup' in source
    assert "current_setting('app.webhook_token_hash', true)" in source
    assert "current_setting('app.invitation_token_hash', true)" in source
    assert 'FOR SELECT USING' in source
