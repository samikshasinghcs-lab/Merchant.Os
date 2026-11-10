"""Enforce tenant isolation in PostgreSQL with transaction-local RLS context.

The policy is compatible with PostgreSQL reached directly or through Cloudflare
Hyperdrive. It does not configure a Cloudflare Worker or Hyperdrive binding.
"""
from alembic import op

revision = "20261110_01"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "merchant_orders",
    "merchant_reviews",
    "merchant_refunds",
    "merchant_disputes",
    "merchant_evidence",
    "merchant_audit_events",
    "merchant_paypal_credentials",
    "paypal_webhook_events",
    "paypal_webhook_routes",
    "event_execution_traces",
    "pact_party_approvals",
    "merchant_invitations",
    "financial_approval_requests",
    "financial_executions",
)


def upgrade() -> None:
    # This repository had no prior Alembic revisions. Bootstrap declared tables
    # idempotently so a fresh deployment can migrate before the app starts.
    from app.auth_sqlalchemy import Base  # noqa: PLC0415
    from app import domain_models as _domain_models  # noqa: F401, PLC0415
    from app import completion_models as _completion_models  # noqa: F401, PLC0415
    Base.metadata.create_all(bind=op.get_bind())

    # Fail the migration rather than silently leaving a subset of tables exposed.
    op.execute("""
    DO $$
    DECLARE t text;
    BEGIN
      FOREACH t IN ARRAY ARRAY[
        'merchant_orders','merchant_reviews','merchant_refunds','merchant_disputes',
        'merchant_evidence','merchant_audit_events','merchant_paypal_credentials',
        'paypal_webhook_events','paypal_webhook_routes','event_execution_traces',
        'pact_party_approvals','merchant_invitations','financial_approval_requests',
        'financial_executions'
      ] LOOP
        IF to_regclass(format('%I', t)) IS NULL THEN
          RAISE EXCEPTION 'Required tenant table % is missing; apply schema migrations first', t;
        END IF;
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS merchantos_tenant_isolation ON %I', t);
        EXECUTE format(
          'CREATE POLICY merchantos_tenant_isolation ON %I '
          'USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')) '
          'WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), ''''))', t
        );
        EXECUTE format('COMMENT ON TABLE %I IS %L', t,
          'MerchantOS tenant data: RLS requires transaction-local app.tenant_id context.');
      END LOOP;
    END $$;
    """)
    # Narrow cross-tenant token resolution is required for public PayPal webhook
    # routing and one-time invitation acceptance. These SELECT-only policies expose
    # only the row matching a high-entropy token hash set transaction-locally.
    op.execute('DROP POLICY IF EXISTS merchantos_webhook_route_lookup ON paypal_webhook_routes')
    op.execute("""
      CREATE POLICY merchantos_webhook_route_lookup ON paypal_webhook_routes
        FOR SELECT USING (token_hash = NULLIF(current_setting('app.webhook_token_hash', true), ''))
    """)
    op.execute('DROP POLICY IF EXISTS merchantos_invitation_token_lookup ON merchant_invitations')
    op.execute("""
      CREATE POLICY merchantos_invitation_token_lookup ON merchant_invitations
        FOR SELECT USING (token_hash = NULLIF(current_setting('app.invitation_token_hash', true), ''))
    """)


def downgrade() -> None:
    # Explicitly destructive to the security boundary; require an operator to
    # choose downgrade intentionally and re-apply before reopening multi-tenant use.
    op.execute('DROP POLICY IF EXISTS merchantos_webhook_route_lookup ON paypal_webhook_routes')
    op.execute('DROP POLICY IF EXISTS merchantos_invitation_token_lookup ON merchant_invitations')
    for table in reversed(TENANT_TABLES):
        op.execute(f'DROP POLICY IF EXISTS merchantos_tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
