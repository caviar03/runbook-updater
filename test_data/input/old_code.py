old_code = """
def process_payment(amount):
    validate_payment(amount)
    charge_card(amount)


def refund_payment(transaction_id):
    find_transaction(transaction_id)
    issue_refund(transaction_id)
"""