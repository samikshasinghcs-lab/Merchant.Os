#!/usr/bin/env python3
"""Verify PostgreSQL tenant RLS policy presence and runtime-role bypass flags."""
from __future__ import annotations
import os
import sys
from sqlalchemy import create_engine, text

TABLES = (
    'merchant_orders', 'merchant_reviews', 'merchant_refunds', 'merchant_disputes',
    'merchant_evidence', 'merchant_audit_events', 'merchant_paypal_credentials',
    'paypal_webhook_events', 'paypal_webhook_routes', 'event_execution_traces',
    'pact_party_approvals', 'merchant_invitations', 'financial_approval_requests',
    'financial_executions',
)


def main() -> int:
    url = os.getenv('IDENTITY_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not url or not url.startswith(('postgresql://', 'postgresql+psycopg://', 'postgres://')):
        print('FAIL: set IDENTITY_DATABASE_URL or DATABASE_URL to PostgreSQL; no credentials are printed.')
        return 2
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            role = connection.execute(text("""
                SELECT current_user, r.rolsuper, r.rolbypassrls
                FROM pg_roles r WHERE r.rolname = current_user
            """)).mappings().one()
            if role['rolsuper'] or role['rolbypassrls']:
                print('FAIL: runtime role bypasses RLS (superuser or BYPASSRLS).')
                return 1
            rows = connection.execute(text("""
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                       EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid
                               AND p.polname='merchantos_tenant_isolation') AS has_policy
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=current_schema() AND c.relname = ANY(:tables)
            """), {'tables': list(TABLES)}).mappings().all()
            by_name = {row['relname']: row for row in rows}
            failed = []
            for table in TABLES:
                row = by_name.get(table)
                if not row or not row['relrowsecurity'] or not row['relforcerowsecurity'] or not row['has_policy']:
                    failed.append(table)
            if failed:
                print('FAIL: missing or incomplete RLS on: ' + ', '.join(failed))
                return 1
            print(f"PASS: {len(TABLES)} tenant tables have enabled + forced RLS and policy; runtime role '{role['current_user']}' has no RLS bypass privilege.")
            print('NOTE: this is catalog verification only, not a two-tenant isolation or Cloudflare deployment test.')
            return 0
    finally:
        engine.dispose()


if __name__ == '__main__':
    sys.exit(main())
