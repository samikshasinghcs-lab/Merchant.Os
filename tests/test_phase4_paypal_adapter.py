from unittest.mock import Mock
import pytest
from app import paypal_tenant_adapter as adapter_module
from app.paypal_tenant_adapter import TenantPayPalAdapter, TenantPayPalError


def test_adapter_uses_tenant_credentials_and_sandbox(monkeypatch):
    monkeypatch.setattr(adapter_module, 'get_paypal_credentials', lambda tenant, env: {
        'client_id':'tenant-client','client_secret':'tenant-secret','environment':env})
    calls=[]
    def fake_post(url, **kwargs):
        calls.append((url,kwargs))
        response=Mock(ok=True)
        response.json.return_value={'access_token':'sandbox-token'}
        return response
    monkeypatch.setattr(adapter_module.requests, 'post', fake_post)
    def fake_request(method,url,**kwargs):
        calls.append((method,url,kwargs))
        response=Mock(ok=True,content=b'{"id":"REFUND_1","status":"COMPLETED"}')
        response.json.return_value={'id':'REFUND_1','status':'COMPLETED'}
        return response
    monkeypatch.setattr(adapter_module.requests, 'request', fake_request)
    client=TenantPayPalAdapter('tenant-123','sandbox')
    result=client.refund_capture('CAPTURE_1','10.00','USD','stable-request-id')
    assert result['id']=='REFUND_1'
    assert calls[0][0]=='https://api-m.sandbox.paypal.com/v1/oauth2/token'
    method,url,kwargs=calls[1]
    assert method=='POST' and url.endswith('/v2/payments/captures/CAPTURE_1/refund')
    assert kwargs['headers']['PayPal-Request-Id']=='stable-request-id'
    assert kwargs['json']['amount']=={'value':'10.00','currency_code':'USD'}


def test_adapter_fails_closed_without_tenant_credentials(monkeypatch):
    monkeypatch.setattr(adapter_module, 'get_paypal_credentials', lambda tenant, env: None)
    with pytest.raises(TenantPayPalError, match='No active PayPal'):
        TenantPayPalAdapter('tenant-123','sandbox')


def test_adapter_rejects_invalid_environment():
    with pytest.raises(ValueError):
        TenantPayPalAdapter('tenant-123','production')
