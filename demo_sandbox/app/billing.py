class BillingService:
    def calculate_invoice(self, order_data: dict) -> float:
        subtotal = order_data.get("subtotal", 0.0)

        # BUG: accessing 'tax_rate' directly instead of the correct key
        # Real payload provides 'tax_pct' as a float (e.g. 0.08)
        tax_rate = order_data["tax_rate"]

        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount
        return round(total, 2)