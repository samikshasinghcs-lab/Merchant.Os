"""Add tenant-isolated idempotent financial execution ledger."""
from alembic import op
from app.auth_sqlalchemy import Base
from app import completion_models  # noqa: F401
revision='0005_financial_execution'; down_revision='0004_financial_approvals'; branch_labels=None; depends_on=None
TABLES=['financial_executions']
def upgrade():
    bind=op.get_bind()
    Base.metadata.create_all(bind=bind,tables=[Base.metadata.tables[n] for n in TABLES])
    if bind.dialect.name=='postgresql':
        for table in TABLES:
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
            op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))")
def downgrade():
    bind=op.get_bind()
    if bind.dialect.name=='postgresql':
        for table in reversed(TABLES):
            op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table}')
            op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
    Base.metadata.drop_all(bind=bind,tables=[Base.metadata.tables[n] for n in reversed(TABLES)])
