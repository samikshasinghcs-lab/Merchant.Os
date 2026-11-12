#!/usr/bin/env python3
"""Read-only two-tenant RLS isolation smoke test against PostgreSQL.

Requires two existing tenant IDs, each with at least one merchant_orders row.
Runs as the restricted application runtime role, not a superuser/BYPASSRLS role.
"""
from __future__ import annotations
import os
import sys
from sqlalchemy import create_engine, text


def main() -> int:
    url = os.getenv("IDENTITY_DATABASE_URL") or os.getenv("DATABASE_URL")
    tenant_ids = [os.getenv("POSTGRES_RLS_TENANT_A_ID"), os.getenv("POSTGRES_RLS_TENANT_B_ID")]
    if not url or not url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        print("FAIL: PostgreSQL URL is not configured.")
        return 2
    if not all(tenant_ids) or tenant_ids[0] == tenant_ids[1]:
        print("FAIL: configure two distinct existing tenant IDs.")
        return 2
    engine = create_engine(url, pool_pre_ping=True)
    try:
        for tenant_id in tenant_ids:
            with engine.begin() as connection:
                connection.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": tenant_id})
                visible = connection.execute(text("SELECT DISTINCT tenant_id FROM merchant_orders")).scalars().all()
                if not visible:
                    print("FAIL: each test tenant must have at least one merchant_orders row.")
                    return 1
                if set(visible) != {tenant_id}:
                    print("FAIL: RLS exposed rows outside the active tenant context.")
                    return 1
        print("PASS: two-tenant read isolation confirmed for merchant_orders using the configured runtime role.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
