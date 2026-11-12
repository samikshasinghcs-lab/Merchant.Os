"""Add fulfilment facts used by the deterministic policy engine (additive, nullable)."""
from alembic import op
import sqlalchemy as sa
revision="20261112_02"
down_revision="20261112_01"
branch_labels=None
depends_on=None
COLS=(("delivered_at",sa.DateTime(timezone=True)),("shipped_at",sa.DateTime(timezone=True)),("hygiene_item",sa.Boolean()))
def upgrade():
    bind=op.get_bind()
    have={c["name"] for c in sa.inspect(bind).get_columns("merchant_orders")}
    for name,typ in COLS:
        if name not in have: op.add_column("merchant_orders",sa.Column(name,typ,nullable=True))
def downgrade():
    for name,_ in COLS: op.drop_column("merchant_orders",name)
