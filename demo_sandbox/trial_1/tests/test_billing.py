import pytest
from demo_sandbox.trial_1.app.billing import BillingService

def test_calculate_invoice_standard():
    service = BillingService()
    order = {
        "order_id": "ORD-9021",
        "subtotal": 100.0,
        "tax_pct": 0.08
    }

    total = service.calculate_invoice(order)
    assert total == 108.0