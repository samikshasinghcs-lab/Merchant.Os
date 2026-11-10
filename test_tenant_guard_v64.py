from app.tenant_guard import legacy_route_blocked


def test_legacy_routes_remain_available_in_single_tenant_mode():
    assert not legacy_route_blocked('/api/customers', False)
    assert not legacy_route_blocked('/api/refunds', False)


def test_legacy_business_routes_fail_closed_in_multi_tenant_mode():
    for path in ('/api/customers', '/api/orders', '/api/refunds', '/api/dashboard', '/api/reviews/import/generic_csv'):
        assert legacy_route_blocked(path, True), path


def test_tenant_scoped_domain_and_event_routes_remain_available():
    for path in ('/api/v1/domain/orders', '/api/v1/domain/refunds', '/api/paypal/webhooks/tenant/abc'):
        assert not legacy_route_blocked(path, True), path


def test_auth_and_signed_event_paths_are_not_blocked_by_tenant_guard():
    for path in ('/api/auth/login', '/api/auth/register', '/api/auth/me', '/api/paypal/webhooks/receive', '/api/paypal/webhooks/verify', '/api/internal/paypal-events', '/api/internal/tenant-paypal-events/process'):
        assert not legacy_route_blocked(path, True), path


def test_non_api_routes_are_never_blocked():
    assert not legacy_route_blocked('/health', True)
    assert not legacy_route_blocked('/workspace', True)
