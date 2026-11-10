"""Add tenant-scoped merchant domain tables and PostgreSQL RLS.

Existing SQLite business data is NOT copied automatically. A controlled export,
per-tenant mapping, reconciliation, and cutover is required before route switch.
"""
from alembic import op
from sqlalchemy import text
from app.auth_sqlalchemy import Base  # registers tenants/users foreign-key targets
from app import domain_models  # noqa: F401 - register tables on Base.metadata

revision='0002_tenant_domain'; down_revision='0001_identity_tenants'; branch_labels=None; depends_on=None
TABLES=['merchant_orders','merchant_reviews','merchant_refunds','merchant_disputes','merchant_evidence','merchant_audit_events']

def upgrade():
    bind=op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[n] for n in TABLES])
    if bind.dialect.name == 'postgresql':
        for table in TABLES:
            op.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
            op.execute(text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
            op.execute(text(f'''CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '') )
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '') )'''))

def downgrade():
    bind=op.get_bind()
    if bind.dialect.name == 'postgresql':
        for table in reversed(TABLES):
            op.execute(text(f'DROP POLICY IF EXISTS tenant_isolation ON {table}'))
            op.execute(text(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY'))
            op.execute(text(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'))
    Base.metadata.drop_all(bind=bind, tables=[Base.metadata.tables[n] for n in reversed(TABLES)])
