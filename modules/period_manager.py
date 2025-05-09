"""
Module: period_manager.py
Handles automatic determination of current trading period and updates settings accordingly.
Also manages period state and computes daily shortfall for dynamic trade sizing.
"""

import os
import json
from datetime import datetime, timedelta

from config import settings
from core.executor import ExecutorManager

# File to persist period state
STATE_FILE = "period_state.json"

def get_current_period():
    """
    Returns the period dict from settings.PERIODS corresponding to the current period index.
    """
    idx = getattr(settings, 'CURRENT_PERIOD', None)
    if idx is None or idx < 1 or idx > len(settings.PERIODS):
        return None
    return settings.PERIODS[idx - 1]

def update_settings_for_period():
    """
    Updates global settings based on the current period definition.
    Raises RuntimeError if no valid period is set.
    Also computes dynamic take-profit ratio for the period.
    """
    period = get_current_period()
    if not period:
        raise RuntimeError("No active trading period found (CURRENT_PERIOD out of range).")

    # Debug output: which period is active and its target
    print(f"[PERIOD-DEBUG] Active period: {settings.CURRENT_PERIOD} -> target {period['target_balance']:.2f} USDT")

    # Set initial balance if not already set
    if not hasattr(settings, 'INITIAL_BALANCE') or settings.INITIAL_BALANCE is None:
        settings.INITIAL_BALANCE = period.get('initial_balance') or getattr(settings, 'INITIAL_BALANCE', None)

    # Update settings
    settings.TARGET_USDT     = period['target_balance']
    settings.GROWTH_FACTOR   = period.get('growth_factor', settings.GROWTH_FACTOR)
    settings.WITHDRAW_AMOUNT = period.get('withdraw_amount', getattr(settings, 'WITHDRAW_AMOUNT', 0))
    settings.KEEP_BALANCE    = period.get('keep_balance', getattr(settings, 'KEEP_BALANCE', 0))

    # Compute dynamic take-profit ratio: (target / initial) - 1
    try:
        base = settings.INITIAL_BALANCE or 1
        settings.TAKE_PROFIT_RATIO = (settings.TARGET_USDT / base) - 1
    except Exception:
        pass

    return period

def perform_period_withdrawal(client, wallet_address):
    """
    Performs a withdrawal of the configured amount at period end.
    Requires a Binance client instance and a predefined wallet address.
    """
    amount = getattr(settings, 'WITHDRAW_AMOUNT', 0)
    if not amount or amount <= 0:
        return None

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

def start_period(client):
    """
    Initializes and saves the state for the current trading period.
    Captures start_balance, target_balance, start_time, and end_time.
    """
    executor = ExecutorManager(client)
    # Capture USDT balance at period start
    start_balance = executor.get_balance('USDT')

    period = get_current_period()
    if not period:
        raise RuntimeError("Cannot start period: no valid CURRENT_PERIOD.")

    target_balance = period['target_balance']
    duration_days  = period.get('duration_days', getattr(settings, 'PERIOD_DAYS', 0))
    start_time     = datetime.utcnow()
    end_time       = start_time + timedelta(days=duration_days)

    state = {
        'period': settings.CURRENT_PERIOD,
        'start_balance': start_balance,
        'target_balance': target_balance,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat()
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
    return state

def load_period_state():
    """
    Loads the persisted state for the current trading period.
    Returns None if no state file exists.
    """
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE) as f:
        state = json.load(f)
    # Convert ISO strings back to datetime
    state['start_time'] = datetime.fromisoformat(state['start_time'])
    state['end_time']   = datetime.fromisoformat(state['end_time'])
    return state

def compute_daily_shortfall(client):
    """
    Calculates the per-day USDT shortfall needed to reach the period target.
    Divides remaining shortfall by remaining days.
    """
    state = load_period_state()
    if not state:
        return 0.0

    executor = ExecutorManager(client)
    current_balance = executor.get_balance('USDT')
    shortfall = state['target_balance'] - current_balance

    now = datetime.utcnow()
    remaining_secs = (state['end_time'] - now).total_seconds()
    remaining_days = max(remaining_secs / 86400, 1)

    # If behind schedule, return positive extra; otherwise 0
    return max(shortfall / remaining_days, 0.0)
