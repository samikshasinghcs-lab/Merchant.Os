"""Tenant-scoped SQLAlchemy session helpers. Fail closed without a tenant ID."""
from contextlib import contextmanager
from sqlalchemy import text

def require_tenant(session):
    tenant_id=session.info.get('tenant_id')
    if not tenant_id: raise PermissionError('Tenant context missing; refusing unscoped domain query')
    return tenant_id

@contextmanager
def tenant_session(tenant_id: str):
    if not tenant_id or not isinstance(tenant_id, str):
        raise ValueError('A verified tenant_id is required')
    from .auth_sqlalchemy import engine, SessionLocal
    session=SessionLocal()
    try:
        if engine.dialect.name == 'postgresql':
            session.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {'tenant_id':tenant_id})
        session.info['tenant_id']=tenant_id
        yield session
        session.commit()
    except Exception:
        session.rollback(); raise
    finally:
        session.close()
