from __future__ import annotations
import os
from typing import Optional, Dict, Any
from core.types import Decision, SignalBundle, OrderPlan, RiskCheckResult, OrderResult
from core.logger import logger, log_exceptions
from core.execution_prefs import load_prefs
from core.errors import classify_exception, RuleViolation, CooldownReject
import time
from core.metrics import inc_order, inc_reject, observe_exec, inc_exc


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


PIPELINE_ENABLED = _bool_env("ORDER_PIPELINE_ENABLED", False)


def _safe_import_executor():
    try:
        from modules.order_executor import OrderExecutor  # type: ignore
        return ("executor", OrderExecutor)
    except Exception:
        pass
    try:
        from modules.order_manager import OrderManager  # type: ignore
        return ("manager", OrderManager)
    except Exception:
        pass
    return (None, None)


def _safe_import_filters():
    try:
        from modules.order_filters import validate_order_plan as vop  # type: ignore
        return vop
    except Exception:
        return None


def _safe_import_mark_executed():
    try:
        from modules.order_filters import mark_executed as me  # type: ignore
        return me
    except Exception:
        return None


def _safe_import_market_state():
    get_state = None
    try:
        from modules.market_state import get_market_state  # type: ignore
        get_state = get_market_state
    except Exception:
        pass
    return get_state


@log_exceptions("build_order_plan_from_signals")
def build_order_plan_from_signals(sig: SignalBundle) -> Optional[OrderPlan]:
    if not sig.regime_on:
        logger.debug("Regime OFF -> WAIT")
        return None

    if sig.buy_score >= 0.6 and sig.buy_score >= sig.sell_score:
        return OrderPlan(
            symbol=sig.symbol,
            side="BUY",
            qty_base=None,
            qty_quote=None,
            reason="score>=0.6 BUY",
            confidence=float(min(1.0, sig.buy_score)),
            tags=["pipeline", "fallback", "spot-only"],
            meta={"volatility": sig.volatility},
        )

    if sig.sell_score >= 0.6 and sig.sell_score > sig.buy_score:
        return OrderPlan(
            symbol=sig.symbol,
            side="SELL",
            reason="score>=0.6 SELL",
            confidence=float(min(1.0, sig.sell_score)),
            tags=["pipeline", "fallback", "spot-only", "exit"],
            meta={"volatility": sig.volatility},
        )

    return None


@log_exceptions("validate_order_plan")
def validate_order_plan(plan: OrderPlan,
                        market_state: Optional[Dict[str, Any]] = None,
                        account_state: Optional[Dict[str, Any]] = None) -> RiskCheckResult:
    vop = _safe_import_filters()
    # Eğer plan tamamen belirsizse (price ve qty yok), basit fallback doğrulamasını kullan
    use_fallback = (plan.entry_price is None and plan.qty_base is None and plan.qty_quote is None)
    if vop and not use_fallback:
        try:
            # Piyasa durumu yoksa ve fiyat da yoksa, opsiyonel sağlayıcıdan dene
            if market_state is None and plan.entry_price is None:
                get_ms = _safe_import_market_state()
                if get_ms:
                    try:
                        market_state = get_ms(plan.symbol)  # type: ignore
                    except Exception:
                        pass
            return vop(plan, market_state, account_state)  # type: ignore
        except Exception as e:
            logger.exception("order_filters.validate_order_plan hata")
            return RiskCheckResult(ok=False, reasons=[f"validator-error: {e}"])

    reasons = []

    if plan.side not in ("BUY", "SELL"):
        reasons.append("invalid side")
    if plan.qty_base is not None and plan.qty_base <= 0:
        reasons.append("qty_base<=0")
    if plan.qty_quote is not None and plan.qty_quote <= 0:
        reasons.append("qty_quote<=0")

    if plan.side == "BUY" and plan.entry_price is not None and plan.sl_price is not None:
        if plan.sl_price >= plan.entry_price:
            reasons.append("SL must be < entry on BUY")
    if plan.side == "SELL" and plan.entry_price is not None and plan.sl_price is not None:
        if plan.sl_price <= plan.entry_price:
            reasons.append("SL must be > entry on SELL")

    ok = len(reasons) == 0
    return RiskCheckResult(ok=ok, reasons=reasons, adjusted_qty=plan.qty_base)


def _apply_adjustments(plan: OrderPlan, rc: RiskCheckResult) -> OrderPlan:
    """RiskCheckResult içindeki ayarlamaları plana uygular (kopya döner)."""
    new_plan = OrderPlan(**{**plan.__dict__})
    if rc.adjusted_entry is not None:
        new_plan.entry_price = rc.adjusted_entry
    if rc.adjusted_qty is not None:
        # qty_base'ı setler, qty_quote'ı sıfırlar
        new_plan.qty_base = rc.adjusted_qty
        new_plan.qty_quote = None
    if rc.adjusted_sl is not None:
        new_plan.sl_price = rc.adjusted_sl
    if rc.adjusted_tp is not None:
        new_plan.tp_price = rc.adjusted_tp
    # Emir tercihlerini uygula
    prefs = load_prefs()
    new_plan.time_in_force = prefs.time_in_force
    if new_plan.meta is None:
        new_plan.meta = {}
    new_plan.meta.update({
        "order_type": prefs.order_type,
        "post_only": prefs.post_only,
        "max_slippage_pct": prefs.max_slippage_pct,
    })
    return new_plan


@log_exceptions("execute_with_filters")
def execute_with_filters(plan: OrderPlan,
                         market_state: Optional[Dict[str, Any]] = None,
                         account_state: Optional[Dict[str, Any]] = None) -> OrderResult:
    """Doğrula -> Ayarları uygula -> Yürüt -> Başarılıysa cooldown işaretle"""
    rc = validate_order_plan(plan, market_state, account_state)
    if not rc.ok:
        # Reddin her nedenini metrikle
        for r in (rc.reasons or []):
            try:
                inc_reject(str(r))
            except Exception:
                pass
        return OrderResult(success=False, status="rejected", error=";".join(rc.reasons) if rc.reasons else "rejected")

    plan2 = _apply_adjustments(plan, rc)
    t0 = time.monotonic()
    res = execute_order_plan(plan2)
    try:
        observe_exec(max(0.0, time.monotonic() - t0))
    except Exception:
        pass
    try:
        inc_order(plan2.symbol, plan2.side, (res.status or ("ok" if res.success else "err")))
    except Exception:
        pass
    if res.success:
        me = _safe_import_mark_executed()
        try:
            if me:
                me(plan.symbol)  # type: ignore
        except Exception:
            logger.exception("mark_executed hata")
    return res


@log_exceptions("execute_order_plan")
def execute_order_plan(plan: OrderPlan) -> OrderResult:
    kind, ExecCls = _safe_import_executor()
    if ExecCls:
        try:
            exec_inst = ExecCls()  # type: ignore
            if hasattr(exec_inst, "place_order"):
                res = exec_inst.place_order(plan)  # type: ignore
            elif hasattr(exec_inst, "execute"):
                res = exec_inst.execute(plan)  # type: ignore
            else:
                return OrderResult(success=False, status="unsupported-executor", error="No place_order/execute")
            # Başarılı yürütme -> cooldown işaretlemesi
            try:
                from modules.order_filters import mark_executed
                mark_executed(plan.symbol)
            except Exception:
                logger.exception("mark_executed failed")
            return OrderResult(success=True, status="ok", raw={"kind": kind, "res": str(res)})
        except Exception as e:
            ce = classify_exception(e)
            try:
                inc_exc(e.__class__.__name__)
            except Exception:
                pass
            return OrderResult(success=False, status=ce.status, error=ce.message)

    logger.info(f"[MOCK] Executing {plan.side} {plan.symbol} | qty_base={plan.qty_base} qty_quote={plan.qty_quote}")
    return OrderResult(success=True, status="mock-ok", order_id="MOCK", filled_qty=plan.qty_base, avg_price=plan.entry_price)
