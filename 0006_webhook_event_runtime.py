"""Durable tenant webhook processing, routing and execution trace."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from app.auth_sqlalchemy import Base
from app import completion_models  # noqa: F401

revision = '0006_webhook_event_runtime'
down_revision = '0005_financial_execution'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('paypal_webhook_events') as batch:
        batch.add_column(sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('workflow_run_id', sa.String(128), nullable=True))
        batch.add_column(sa.Column('work_item', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('dead_lettered_at', sa.DateTime(timezone=True), nullable=True))
        batch.alter_column('attempt_count', server_default=None)

    bind = op.get_bind()
    tables = [Base.metadata.tables['paypal_webhook_routes'], Base.metadata.tables['event_execution_traces']]
    Base.metadata.create_all(bind=bind, tables=tables)
    if bind.dialect.name == 'postgresql':
        trace = 'event_execution_traces'
        op.execute(text(f'ALTER TABLE {trace} ENABLE ROW LEVEL SECURITY'))
        op.execute(text(f'ALTER TABLE {trace} FORCE ROW LEVEL SECURITY'))
        op.execute(text(f"""CREATE POLICY tenant_isolation ON {trace}
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))"""))
        # Webhook routes are a minimal opaque-token routing index. Tokens are high-entropy
        # random values stored only as SHA-256 hashes; all event and credential data remain RLS-scoped.


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(text('DROP POLICY IF EXISTS tenant_isolation ON event_execution_traces'))
        op.execute(text('ALTER TABLE event_execution_traces NO FORCE ROW LEVEL SECURITY'))
        op.execute(text('ALTER TABLE event_execution_traces DISABLE ROW LEVEL SECURITY'))
    Base.metadata.drop_all(bind=bind, tables=[Base.metadata.tables['event_execution_traces'], Base.metadata.tables['paypal_webhook_routes']])
    with op.batch_alter_table('paypal_webhook_events') as batch:
        batch.drop_column('dead_lettered_at')
        batch.drop_column('work_item')
        batch.drop_column('workflow_run_id')
        batch.drop_column('locked_until')
        batch.drop_column('next_attempt_at')
        batch.drop_column('attempt_count')
