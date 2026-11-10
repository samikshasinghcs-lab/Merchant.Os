import os
from cryptography.fernet import Fernet
from app.paypal_security import encrypt_secret, decrypt_secret, verify_webhook_signature, CredentialError

def test_credential_encryption_roundtrip(monkeypatch):
    monkeypatch.setenv('MERCHANTOS_CREDENTIALS_KEY',Fernet.generate_key().decode())
    encrypted=encrypt_secret('sandbox-secret')
    assert encrypted!='sandbox-secret'
    assert decrypt_secret(encrypted)=='sandbox-secret'

def test_credential_encryption_fails_closed(monkeypatch):
    monkeypatch.delenv('MERCHANTOS_CREDENTIALS_KEY',raising=False)
    try: encrypt_secret('secret')
    except CredentialError: pass
    else: assert False, 'missing key must fail closed'

def test_webhook_verification_fails_closed_without_headers():
    assert verify_webhook_signature({}, {'id':'evt'}, 'webhook','client','secret','sandbox') is False
