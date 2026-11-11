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


_WEBHOOK_COLUMNS = (
    sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('workflow_run_id', sa.String(128), nullable=True),
    sa.Column('work_item', sa.JSON(), nullable=True),
    sa.Column('dead_lettered_at', sa.DateTime(timezone=True), nullable=True),
)


def upgrade():
    bind = op.get_bind()

    # Earlier releases may have created some of these fields before Alembic
    # recorded revision 0006. Inspect the live schema and add only missing
    # fields so this migration safely resumes after a partially applied run.
    existing = {column['name'] for column in sa.inspect(bind).get_columns('paypal_webhook_events')}
    for column in _WEBHOOK_COLUMNS:
        if column.name not in existing:
            op.add_column('paypal_webhook_events', column)

    tables = [
        Base.metadata.tables['paypal_webhook_routes'],
        Base.metadata.tables['event_execution_traces'],
    ]
    Base.metadata.create_all(bind=bind, tables=tables)

    if bind.dialect.name == 'postgresql':
        trace = 'event_execution_traces'
        op.execute(text(f'ALTER TABLE {trace} ENABLE ROW LEVEL SECURITY'))
        op.execute(text(f'ALTER TABLE {trace} FORCE ROW LEVEL SECURITY'))
        op.execute(text(f"""CREATE POLICY tenant_isolation ON {trace}
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))"""))
        # Webhook routes are a minimal opaque-token routing index. Tokens are
        # high-entropy random values stored only as SHA-256 hashes; all event
        # and credential data remain RLS-scoped.


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(text('DROP POLICY IF EXISTS tenant_isolation ON event_execution_traces'))
        op.execute(text('ALTER TABLE event_execution_traces NO FORCE ROW LEVEL SECURITY'))
        op.execute(text('ALTER TABLE event_execution_traces DISABLE ROW LEVEL SECURITY'))

    Base.metadata.drop_all(
        bind=bind,
        tables=[
            Base.metadata.tables['event_execution_traces'],
            Base.metadata.tables['paypal_webhook_routes'],
        ],
    )

    existing = {column['name'] for column in sa.inspect(bind).get_columns('paypal_webhook_events')}
    for column in reversed(_WEBHOOK_COLUMNS):
        if column.name in existing:
            op.drop_column('paypal_webhook_events', column.name)
