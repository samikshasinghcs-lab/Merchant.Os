"""Tenant-scoped credentials, webhook inbox, invitations and authenticated PACT approvals."""
from alembic import op
from app.auth_sqlalchemy import Base
from app import domain_models, completion_models  # noqa
revision='0003_operational_security'; down_revision='0002_tenant_domain'; branch_labels=None; depends_on=None
TABLES=['merchant_paypal_credentials','paypal_webhook_events','pact_party_approvals','merchant_invitations']
def upgrade():
    bind=op.get_bind(); Base.metadata.create_all(bind=bind,tables=[Base.metadata.tables[n] for n in TABLES])
    if bind.dialect.name=='postgresql':
        for table in TABLES:
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'); op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))")
def downgrade():
    bind=op.get_bind()
    if bind.dialect.name=='postgresql':
        for table in reversed(TABLES):
            op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table}'); op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'); op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
    Base.metadata.drop_all(bind=bind,tables=[Base.metadata.tables[n] for n in reversed(TABLES)])
