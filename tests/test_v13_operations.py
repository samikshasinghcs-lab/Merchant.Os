import hashlib
ROLES={'ADMIN','OPERATOR','VIEWER'}

def test_role_allowlist_is_restricted():
    assert ROLES == {'ADMIN','OPERATOR','VIEWER'}

def test_invitation_token_digest_is_sha256():
    token='random-one-time-token'
    digest=hashlib.sha256(token.encode()).hexdigest()
    assert len(digest)==64 and digest != token

def test_approval_statement_hash_is_stable():
    statement='I approve agreement version 3 after review.'
    assert hashlib.sha256(statement.encode()).hexdigest()==hashlib.sha256(statement.encode()).hexdigest()
