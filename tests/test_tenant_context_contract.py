from types import SimpleNamespace
import sys

import pytest


def test_tenant_session_sets_transaction_local_context(monkeypatch):
    calls = []

    class FakeSession:
        info = {}
        def execute(self, statement, params):
            calls.append((str(statement), params))
        def commit(self):
            calls.append(("COMMIT", None))
        def rollback(self):
            calls.append(("ROLLBACK", None))
        def close(self):
            calls.append(("CLOSE", None))

    fake = FakeSession()
    module = SimpleNamespace(
        engine=SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        SessionLocal=lambda: fake,
    )
    monkeypatch.setitem(sys.modules, "app.auth_sqlalchemy", module)
    from app.tenant_db import tenant_session

    with tenant_session("tenant-a") as session:
        assert session.info["tenant_id"] == "tenant-a"
    assert calls[0][1] == {"tenant_id": "tenant-a"}
    assert "set_config('app.tenant_id', :tenant_id, true)" in calls[0][0]
    assert calls[-2][0] == "COMMIT"
    assert calls[-1][0] == "CLOSE"


def test_tenant_session_fails_closed_without_tenant():
    from app.tenant_db import tenant_session
    with pytest.raises(ValueError):
        with tenant_session(""):
            pass
