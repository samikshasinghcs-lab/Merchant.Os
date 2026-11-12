"""Database-level append-only guards for audit event tables."""
from sqlalchemy import text

AUDIT_TABLES = ("merchant_audit_events", "financial_lifecycle_events")


def install_append_only_audit_guards(connection) -> None:
    """Install UPDATE/DELETE blockers on existing audit tables.

    SQLite is used by local/demo deployments; PostgreSQL is the production
    identity/domain database. Other dialects fail closed rather than silently
    claiming append-only enforcement.
    """
    dialect = connection.dialect.name
    if dialect == "sqlite":
        from sqlalchemy import inspect
        inspector = inspect(connection)
        for table in AUDIT_TABLES:
            if not inspector.has_table(table):
                continue
            connection.execute(text(f'''CREATE TRIGGER IF NOT EXISTS {table}_no_update
                BEFORE UPDATE ON "{table}"
                BEGIN SELECT RAISE(ABORT, 'audit records are append-only'); END'''))
            connection.execute(text(f'''CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                BEFORE DELETE ON "{table}"
                BEGIN SELECT RAISE(ABORT, 'audit records are append-only'); END'''))
        return
    if dialect == "postgresql":
        connection.execute(text("""CREATE OR REPLACE FUNCTION merchantos_reject_audit_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'MerchantOS audit records are append-only'; END; $$"""))
        for table in AUDIT_TABLES:
            connection.execute(text(f'DROP TRIGGER IF EXISTS {table}_append_only ON "{table}"'))
            connection.execute(text(f'''CREATE TRIGGER {table}_append_only
                BEFORE UPDATE OR DELETE ON "{table}"
                FOR EACH ROW EXECUTE FUNCTION merchantos_reject_audit_mutation()'''))
        return
    raise RuntimeError(f"Append-only audit guards are unsupported for database dialect: {dialect}")
