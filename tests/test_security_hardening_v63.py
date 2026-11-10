from types import SimpleNamespace
import pytest
jose = pytest.importorskip("jose")
from jose import jwt, JWTError
from app import auth_sqlalchemy as auth


def test_access_tokens_are_audience_and_issuer_bound():
    user = SimpleNamespace(id='user-1', email='merchant@example.test')
    membership = SimpleNamespace(tenant_id='tenant-1', role='OWNER')
    token = auth.make_token(user, membership)
    claims = jwt.decode(token, auth.SECRET, algorithms=[auth.ALGORITHM],
                        issuer=auth.JWT_ISSUER, audience=auth.JWT_AUDIENCE)
    assert claims['sub'] == 'user-1'
    assert claims['tenant_id'] == 'tenant-1'
    assert claims['iss'] == auth.JWT_ISSUER
    assert claims['aud'] == auth.JWT_AUDIENCE
    assert claims['jti']
    assert 'role' not in claims  # role is loaded from the current DB membership


def test_access_tokens_reject_wrong_audience():
    user = SimpleNamespace(id='user-2', email='merchant@example.test')
    membership = SimpleNamespace(tenant_id='tenant-2', role='OWNER')
    token = auth.make_token(user, membership)
    try:
        jwt.decode(token, auth.SECRET, algorithms=[auth.ALGORITHM],
                   issuer=auth.JWT_ISSUER, audience='untrusted-client')
    except JWTError:
        pass
    else:
        raise AssertionError('Token with wrong audience must be rejected')
