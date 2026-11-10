"""SQLAlchemy-backed identity, tenant membership and RBAC foundation.
Domain data in the legacy SQLite modules is not yet tenant-scoped; see SECURITY.md.
"""
import os, uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, String, DateTime, ForeignKey, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, sessionmaker
from .orm_base import Base
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

DATABASE_URL=os.getenv('IDENTITY_DATABASE_URL') or os.getenv('DATABASE_URL') or 'sqlite:///./merchantos_identity.db'
if DATABASE_URL.startswith('postgres://'): DATABASE_URL=DATABASE_URL.replace('postgres://','postgresql+psycopg://',1)
if DATABASE_URL.startswith('postgresql://'): DATABASE_URL=DATABASE_URL.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal=sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
class Tenant(Base):
    __tablename__='tenants'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    name:Mapped[str]=mapped_column(String(160),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    email:Mapped[str]=mapped_column(String(320),unique=True,index=True,nullable=False)
    name:Mapped[str]=mapped_column(String(160),nullable=False)
    password_hash:Mapped[str]=mapped_column(String(255),nullable=False)
    is_active:Mapped[bool]=mapped_column(default=True,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Membership(Base):
    __tablename__='memberships'; __table_args__=(UniqueConstraint('tenant_id','user_id',name='uq_membership_tenant_user'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    tenant_id:Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),index=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    role:Mapped[str]=mapped_column(String(20),default='OWNER',nullable=False)
    tenant:Mapped[Tenant]=relationship(); user:Mapped[User]=relationship()

pwd=CryptContext(schemes=['bcrypt'],deprecated='auto')
SECRET=os.getenv('JWT_SECRET_KEY','local-development-secret-change-this-before-deploying')
if os.getenv('AUTH_REQUIRED','false').lower()=='true' and (len(SECRET)<32 or SECRET in {'local-development-secret-change-this-before-deploying','replace-with-a-long-random-secret-before-deploying'}):
    raise RuntimeError('Set a unique JWT_SECRET_KEY of at least 32 characters before enabling AUTH_REQUIRED')
ALGORITHM='HS256'; TOKEN_MINUTES=max(5,min(int(os.getenv('ACCESS_TOKEN_MINUTES','15')),60))
JWT_ISSUER=os.getenv('JWT_ISSUER','merchantos-api')
JWT_AUDIENCE=os.getenv('JWT_AUDIENCE','merchantos-client')

def init_identity(): Base.metadata.create_all(bind=engine)
def db_session():
    db=SessionLocal()
    try: yield db
    finally: db.close()
def make_token(user:User, membership:Membership):
    now=datetime.now(timezone.utc)
    payload={'sub':user.id,'tenant_id':membership.tenant_id,'iat':now,'nbf':now,'exp':now+timedelta(minutes=TOKEN_MINUTES),'iss':JWT_ISSUER,'aud':JWT_AUDIENCE,'jti':str(uuid.uuid4())}
    return jwt.encode(payload,SECRET,algorithm=ALGORITHM)

def register_user(db,name,email,password,tenant_name):
    email=email.strip().lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,'An account with this email already exists')
    if not name.strip() or not tenant_name.strip(): raise HTTPException(400,'Name and business name are required')
    if len(password)<12: raise HTTPException(400,'Password must contain at least 12 characters')
    if len(password.encode('utf-8'))>72: raise HTTPException(400,'Password must be no more than 72 UTF-8 bytes')
    user=User(name=name.strip()[:160],email=email,password_hash=pwd.hash(password))
    tenant=Tenant(name=tenant_name.strip()[:160])
    db.add_all([user,tenant]); db.flush()
    member=Membership(user_id=user.id,tenant_id=tenant.id,role='OWNER'); db.add(member); db.commit(); db.refresh(user); db.refresh(member)
    return user,member

def login_user(db,email,password):
    user=db.scalar(select(User).where(User.email==email.strip().lower()))
    if not user or not user.is_active or not pwd.verify(password,user.password_hash): raise HTTPException(401,'Invalid email or password')
    member=db.scalar(select(Membership).where(Membership.user_id==user.id).order_by(Membership.id))
    if not member: raise HTTPException(403,'No merchant workspace membership')
    return user,member

bearer=HTTPBearer(auto_error=False)
def current_principal(creds:HTTPAuthorizationCredentials=Depends(bearer),db=Depends(db_session)):
    if not creds: raise HTTPException(401,'Authentication required')
    try: claims=jwt.decode(creds.credentials,SECRET,algorithms=[ALGORITHM],issuer=JWT_ISSUER,audience=JWT_AUDIENCE,options={'require_exp':True,'require_iat':True,'require_nbf':True,'require_sub':True,'require_jti':True})
    except JWTError: raise HTTPException(401,'Invalid or expired access token')
    user=db.get(User,claims.get('sub')); member=db.scalar(select(Membership).where(Membership.user_id==claims.get('sub'),Membership.tenant_id==claims.get('tenant_id')))
    if not user or not user.is_active or not member: raise HTTPException(401,'Account or workspace membership is inactive')
    return {'user_id':user.id,'email':user.email,'name':user.name,'tenant_id':member.tenant_id,'tenant_name':member.tenant.name,'role':member.role}

def require_roles(*roles):
    def dep(principal=Depends(current_principal)):
        if principal['role'] not in roles: raise HTTPException(403,'Insufficient workspace role')
        return principal
    return dep

# Register tenant-scoped business models with the shared metadata for Alembic.
# Import occurs after identity classes and Base are defined.
try:
    from . import domain_models as _domain_models  # noqa: F401
    from . import completion_models as _completion_models  # noqa: F401
except ImportError:
    raise
