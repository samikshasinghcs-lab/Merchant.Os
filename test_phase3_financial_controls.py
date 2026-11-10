import pytest
from app.financial_controls import evaluate_refund, approval_digest, validate_approver


def evaluate(**overrides):
    args=dict(capture_id='CAPTURE_123',amount='25.00',currency='USD',capture_amount='100.00',
              capture_currency='USD',already_refunded='10.00',daily_total='100.00',
              max_refund='2000.00',daily_cap='10000.00',provider_status='COMPLETED',
              reconciliation_verified=True)
    args.update(overrides)
    return evaluate_refund(**args)


def test_valid_refund_is_allowed_after_canonical_reconciliation():
    result=evaluate()
    assert result.allowed
    assert result.remaining_capture_balance=='90.00'

@pytest.mark.parametrize('overrides,reason',[
    ({'reconciliation_verified':False},'CANONICAL_PAYPAL_RECONCILIATION_REQUIRED'),
    ({'currency':'EUR'},'CURRENCY_MISMATCH'),
    ({'amount':'95.00'},'REFUND_EXCEEDS_REMAINING_CAPTURE_BALANCE'),
    ({'amount':'2001.00'},'PER_REFUND_LIMIT_EXCEEDED'),
    ({'daily_total':'9990.00','amount':'20.00'},'DAILY_REFUND_LIMIT_EXCEEDED'),
    ({'provider_status':'PENDING'},'CAPTURE_NOT_REFUNDABLE_STATUS'),
])
def test_policy_blocks_unsafe_refund(overrides,reason):
    result=evaluate(**overrides)
    assert not result.allowed
    assert reason in result.reasons


def test_approval_digest_binds_amount_and_reason():
    base=dict(tenant_id='t1',capture_id='CAPTURE_123',amount='10',currency='USD',reason='Customer returned item')
    digest=approval_digest(**base)
    assert digest==approval_digest(**base)
    assert digest!=approval_digest(**{**base,'amount':'11'})
    assert digest!=approval_digest(**{**base,'reason':'Different reason'})
    assert digest!=approval_digest(**{**base,'tenant_id':'t2'})


def test_maker_cannot_approve_own_request():
    with pytest.raises(PermissionError):
        validate_approver(requester_id='u1',approver_id='u1',role='OWNER',approval_digest_matches=True,status='PENDING_APPROVAL')


def test_only_owner_admin_can_approve_and_digest_must_match():
    with pytest.raises(PermissionError):
        validate_approver(requester_id='u1',approver_id='u2',role='OPERATOR',approval_digest_matches=True,status='PENDING_APPROVAL')
    with pytest.raises(ValueError):
        validate_approver(requester_id='u1',approver_id='u2',role='OWNER',approval_digest_matches=False,status='PENDING_APPROVAL')
    with pytest.raises(ValueError):
        validate_approver(requester_id='u1',approver_id='u2',role='OWNER',approval_digest_matches=True,status='APPROVED')


def test_phase4_execution_is_disabled_by_default():
    from app.financial_execution_service import execute_approved_refund
    with pytest.raises(PermissionError, match='disabled'):
        execute_approved_refund(tenant_id='tenant-a', approval_id='approval-a',
                                actor_id='approver-a', execution_enabled=False)


def test_phase4_live_execution_is_rejected_even_when_flag_enabled():
    from app.financial_execution_service import execute_approved_refund
    with pytest.raises(PermissionError, match='sandbox'):
        execute_approved_refund(tenant_id='tenant-a', approval_id='approval-a',
                                actor_id='approver-a', environment='live', execution_enabled=True)
