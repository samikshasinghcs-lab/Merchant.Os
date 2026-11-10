"""PayPal webhook signature verification and encrypted credential primitives."""
import os, base64
from cryptography.fernet import Fernet, InvalidToken
import requests

class CredentialError(ValueError): pass

def _fernet():
    key=os.getenv('MERCHANTOS_CREDENTIALS_KEY','')
    if not key: raise CredentialError('MERCHANTOS_CREDENTIALS_KEY is not configured')
    try: return Fernet(key.encode())
    except Exception as e: raise CredentialError('MERCHANTOS_CREDENTIALS_KEY must be a valid Fernet key') from e

def encrypt_secret(value: str) -> str:
    if not value: raise CredentialError('Secret cannot be empty')
    return _fernet().encrypt(value.encode()).decode()

def decrypt_secret(value: str) -> str:
    try: return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as e: raise CredentialError('Credential cannot be decrypted with the configured key') from e

def verify_webhook_signature(headers: dict, event: dict, webhook_id: str, client_id: str, client_secret: str, mode='sandbox') -> bool:
    """Ask PayPal's authoritative verification endpoint; fail closed on any error."""
    required=['PAYPAL-AUTH-ALGO','PAYPAL-CERT-URL','PAYPAL-TRANSMISSION-ID','PAYPAL-TRANSMISSION-SIG','PAYPAL-TRANSMISSION-TIME']
    normalized={str(k).upper():v for k,v in headers.items()}
    if not webhook_id or any(not normalized.get(k) for k in required): return False
    base='https://api-m.sandbox.paypal.com' if mode=='sandbox' else 'https://api-m.paypal.com' if mode=='live' else None
    if not base: return False
    try:
        token_response=requests.post(base+'/v1/oauth2/token',auth=(client_id,client_secret),data={'grant_type':'client_credentials'},timeout=15)
        token_response.raise_for_status(); token=token_response.json()['access_token']
        payload={'auth_algo':normalized['PAYPAL-AUTH-ALGO'],'cert_url':normalized['PAYPAL-CERT-URL'],'transmission_id':normalized['PAYPAL-TRANSMISSION-ID'],'transmission_sig':normalized['PAYPAL-TRANSMISSION-SIG'],'transmission_time':normalized['PAYPAL-TRANSMISSION-TIME'],'webhook_id':webhook_id,'webhook_event':event}
        response=requests.post(base+'/v1/notifications/verify-webhook-signature',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},json=payload,timeout=15)
        response.raise_for_status()
        return response.json().get('verification_status')=='SUCCESS'
    except (requests.RequestException,ValueError,KeyError): return False
