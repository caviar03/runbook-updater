current_code = """
def process_payment(amount):
    validate_payment(amount)

    if amount > 1000:
        require_manager_approval()

    charge_card(amount)


def refund_payment(transaction_id):
    find_transaction(transaction_id)

    if transaction_is_high_value(transaction_id):
        require_manager_approval()

    issue_refund(transaction_id)
"""