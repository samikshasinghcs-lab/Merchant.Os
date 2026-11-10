from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from app.deeptech.models import Transaction

@pytest.fixture
def make_tx():
    def factory(index=0, amount="25.00", **kwargs):
        defaults=dict(transaction_id=f"tx-{index}",merchant_id="merchant-a",amount=Decimal(amount),currency="USD",occurred_at=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(hours=index),customer_id=f"customer-{index%5}",product_id="sku-a",channel="web",country="US")
        defaults.update(kwargs)
        return Transaction(**defaults)
    return factory
