"""identity, tenants and workspace memberships"""
from alembic import op
import sqlalchemy as sa
revision='0001_identity_tenants'; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
 op.create_table('tenants',sa.Column('id',sa.String(36),primary_key=True),sa.Column('name',sa.String(160),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
 op.create_table('users',sa.Column('id',sa.String(36),primary_key=True),sa.Column('email',sa.String(320),nullable=False),sa.Column('name',sa.String(160),nullable=False),sa.Column('password_hash',sa.String(255),nullable=False),sa.Column('is_active',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
 op.create_index('ix_users_email','users',['email'],unique=True)
 op.create_table('memberships',sa.Column('id',sa.String(36),primary_key=True),sa.Column('tenant_id',sa.String(36),sa.ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('role',sa.String(20),nullable=False),sa.UniqueConstraint('tenant_id','user_id',name='uq_membership_tenant_user'))
 op.create_index('ix_memberships_tenant_id','memberships',['tenant_id']);op.create_index('ix_memberships_user_id','memberships',['user_id'])
def downgrade():
 op.drop_index('ix_memberships_user_id',table_name='memberships');op.drop_index('ix_memberships_tenant_id',table_name='memberships');op.drop_table('memberships');op.drop_index('ix_users_email',table_name='users');op.drop_table('users');op.drop_table('tenants')
