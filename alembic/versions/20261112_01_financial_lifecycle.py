"""Create tenant-scoped financial lifecycle tables and force PostgreSQL RLS."""
from alembic import op
revision="20261112_01"
down_revision="20261110_01"
branch_labels=None
depends_on=None
TABLES=("financial_order_costs","financial_resolution_cases","financial_inventory_dispositions","financial_journal_entries","financial_lifecycle_events")
def upgrade():
    from app.auth_sqlalchemy import Base
    from app import financial_lifecycle  # noqa
    from sqlalchemy import inspect
    bind=op.get_bind()
    # Additive review-cluster linkage; safe for existing tenant review tables.
    if bind.dialect.has_table(bind, "merchant_reviews") and "complaint_cluster_id" not in {c["name"] for c in inspect(bind).get_columns("merchant_reviews")}:
        op.add_column("merchant_reviews", __import__("sqlalchemy").Column("complaint_cluster_id", __import__("sqlalchemy").String(100), nullable=True))
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name!="postgresql": return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS merchantos_tenant_isolation ON "{table}"')
        op.execute(f"""CREATE POLICY merchantos_tenant_isolation ON "{table}"
          USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))""")
def downgrade():
    bind=op.get_bind()
    from sqlalchemy import inspect
    if bind.dialect.has_table(bind, "merchant_reviews") and "complaint_cluster_id" in {c["name"] for c in inspect(bind).get_columns("merchant_reviews")}:
        op.drop_column("merchant_reviews", "complaint_cluster_id")
    if bind.dialect.name!="postgresql": return
    for table in reversed(TABLES):
        op.execute(f'DROP POLICY IF EXISTS merchantos_tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
