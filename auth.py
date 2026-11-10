"""Optional import shim: production installs SQLAlchemy/JWT dependencies; legacy tests can run without them."""
try:
    from .auth_sqlalchemy import *  # noqa: F401,F403
    AUTH_AVAILABLE=True
except ImportError as _dependency_error:
    AUTH_AVAILABLE=False
    from fastapi import HTTPException
    class _Unavailable:
        def __getattr__(self, name): raise HTTPException(503,'Identity service dependencies are not installed. Install requirements.txt.')
    jwt=_Unavailable(); SessionLocal=_Unavailable()
    class _Placeholder: pass
    Tenant=User=Membership=_Placeholder
    SECRET=''; ALGORITHM='HS256'
    def init_identity(): return None
    def db_session(): raise HTTPException(503,'Identity service dependencies are not installed.')
    def current_principal(): raise HTTPException(503,'Identity service dependencies are not installed.')
    def require_roles(*roles):
        def dep(): raise HTTPException(503,'Identity service dependencies are not installed.')
        return dep
    def make_token(*args,**kwargs): raise HTTPException(503,'Identity service dependencies are not installed.')
    def register_user(*args,**kwargs): raise HTTPException(503,'Identity service dependencies are not installed.')
    def login_user(*args,**kwargs): raise HTTPException(503,'Identity service dependencies are not installed.')
