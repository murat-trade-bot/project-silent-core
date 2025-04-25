""" Module: period_manager.py Handles automatic determination of current trading period and updates settings accordingly. """ from datetime import datetime from config import settings

def get_current_period(): """ Returns the period dict from settings.PERIODS corresponding to today's date. """ today = datetime.utcnow().date() for period in settings.PERIODS: start = datetime.fromisoformat(period["start"]).date() end = datetime.fromisoformat(period["end"]).date() if start <= today <= end: return period return None

def update_settings_for_period(): """ Updates global settings based on the current period definition. Raises RuntimeError if outside defined periods. """ period = get_current_period() if not period: raise RuntimeError("No active trading period found for today's date.")

# Handle initial balance: if None, use previous period's target
idx = settings.PERIODS.index(period)
if period.get("initial_balance") is None and idx > 0:
    prev = settings.PERIODS[idx - 1]
    settings.INITIAL_BALANCE = prev["target_balance"]
else:
    settings.INITIAL_BALANCE = period["initial_balance"]

# Update other settings
settings.TARGET_USDT    = period["target_balance"]
settings.CURRENT_PERIOD = period["name"]
settings.WITHDRAW_AMOUNT = period["withdraw_amount"]
settings.KEEP_BALANCE    = period["keep_balance"]
settings.GROWTH_FACTOR   = period["growth_factor"]

return period

def perform_period_withdrawal(client, wallet_address): """ Performs a withdrawal of the configured amount at period end. Requires a Binance client instance and a predefined wallet address. """ amount = settings.WITHDRAW_AMOUNT if not amount or amount <= 0: return None

# Example: spot transfer to an external wallet
try:
    result = client.withdraw(
        coin='USDT',
        address=wallet_address,
        amount=amount,
        network='TRC20'
    )
    return result
except Exception as e:
    raise RuntimeError(f"Withdrawal failed: {e}")

