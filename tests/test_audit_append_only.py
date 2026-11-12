import pytest
from sqlalchemy import create_engine, text
from app.audit_guards import install_append_only_audit_guards


def test_sqlite_audit_tables_reject_update_and_delete():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE merchant_audit_events (id TEXT PRIMARY KEY, event TEXT)"))
        conn.execute(text("CREATE TABLE financial_lifecycle_events (id TEXT PRIMARY KEY, event_type TEXT)"))
        conn.execute(text("INSERT INTO merchant_audit_events VALUES ('a', 'created')"))
        conn.execute(text("INSERT INTO financial_lifecycle_events VALUES ('b', 'created')"))
        install_append_only_audit_guards(conn)
        with pytest.raises(Exception, match="append-only"):
            conn.execute(text("UPDATE merchant_audit_events SET event='changed' WHERE id='a'"))
        with pytest.raises(Exception, match="append-only"):
            conn.execute(text("DELETE FROM financial_lifecycle_events WHERE id='b'"))
        # Inserts remain allowed: append-only means immutable after creation.
        conn.execute(text("INSERT INTO merchant_audit_events VALUES ('c', 'new')"))
    engine.dispose()
