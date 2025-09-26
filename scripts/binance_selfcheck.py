#!/usr/bin/env python
"""Binance Spot Testnet Self-Check

Amaç: Test modunda spot-only uyumluluk ve temel sağlık sinyallerini doğrulamak.
Çalıştır:
  python scripts/binance_selfcheck.py
İsteğe bağlı resmi connector için:
  pip install binance-connector
  USE_CONNECTOR=1 USE_PYBIN=0 python scripts/binance_selfcheck.py
"""
from __future__ import annotations
import os, time, sys
from datetime import datetime, timezone


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")


SYMS = [s for s in os.getenv("SELFTEST_SYMBOLS", "SOLUSDT,ADAUSDT").replace(" ", "").split(",") if s]
USE_PYBIN = _bool_env("USE_PYBIN", True)
USE_CONNECTOR = _bool_env("USE_CONNECTOR", False)

print("== Binance Spot Self-Check (Testnet) ==")
print(f"symbols={SYMS}")

# --- A) python-binance (community) ---
if USE_PYBIN:
    try:
        from binance.client import Client as PyBinClient  # type: ignore
    except Exception as e:
        print(f"[py-binance] import failed: {e}")
        PyBinClient = None  # type: ignore
    if PyBinClient is not None:
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_sec = os.getenv("BINANCE_API_SECRET", "")
        client = PyBinClient(api_key, api_sec, testnet=True)
        base_url = getattr(client, "API_URL", "")
        ver = None
        try:
            import binance as _b  # type: ignore
            ver = getattr(_b, "__version__", "?")
        except Exception:
            pass
        print(f"[py-binance] version={ver} base_url={base_url}")

        # Ping & server time drift
        try:
            t_srv = client.get_server_time()["serverTime"]  # ms
            drift_ms = abs(int(time.time() * 1000) - int(t_srv))
            print(f"server_time_drift_ms={drift_ms}")
            if drift_ms > 2000:
                print("[WARN] Drift > 2000ms. NTP veya client.TIME_OFFSET ayarla, recvWindow arttırmayı düşün.")
        except Exception as e:
            print(f"[ERR] server time: {e}")

        # Exchange Info
        try:
            info = client.get_exchange_info()
            fmap = {s["symbol"]: s for s in info.get("symbols", [])}
            for sym in SYMS:
                sdef = fmap.get(sym)
                if not sdef:
                    print(f"[WARN] {sym} exchangeInfo'da yok")
                    continue
                f = {f["filterType"]: f for f in sdef.get("filters", [])}
                def _flt(name: str):
                    return f.get(name, {})
                tick = float(_flt("PRICE_FILTER").get("tickSize", 0) or 0)
                step = float(_flt("LOT_SIZE").get("stepSize", 0) or 0)
                min_notional = float(_flt("NOTIONAL").get("minNotional", 0) or _flt("MIN_NOTIONAL").get("minNotional", 0) or 0)
                print(f"{sym}: tick={tick} step={step} minNotional={min_notional}")
        except Exception as e:
            print(f"[ERR] exchangeInfo: {e}")

        # Last prices
        for sym in SYMS:
            try:
                p = float(client.get_symbol_ticker(symbol=sym)["price"])
                print(f"last_price[{sym}]={p}")
            except Exception as e:
                print(f"[ERR] ticker {sym}: {e}")

# --- B) Official binance-connector ---
if USE_CONNECTOR:
    try:
        from binance.spot import Spot as ConnectorClient  # type: ignore
    except Exception as e:
        print(f"[connector] import failed: {e}")
        ConnectorClient = None  # type: ignore
    if ConnectorClient is not None:
        c = ConnectorClient(base_url="https://testnet.binance.vision")
        ver = None
        try:
            import binance_connector  # type: ignore
            ver = getattr(binance_connector, "__version__", "?")
        except Exception:
            pass
        print(f"[connector] version={ver} base_url=https://testnet.binance.vision/api")
        try:
            c.ping()
            st = c.time()["serverTime"]
            drift_ms = abs(int(time.time() * 1000) - int(st))
            print(f"server_time_drift_ms={drift_ms}")
        except Exception as e:
            print(f"[ERR] connector ping/time: {e}")
        try:
            ex = c.exchange_info()
            fmap = {s["symbol"]: s for s in ex.get("symbols", [])}
            for sym in SYMS:
                sdef = fmap.get(sym)
                if not sdef:
                    print(f"[WARN] {sym} exchangeInfo yok")
                    continue
                f = {f["filterType"]: f for f in sdef.get("filters", [])}
                def _flt(name: str):
                    return f.get(name, {})
                tick = float(_flt("PRICE_FILTER").get("tickSize", 0) or 0)
                step = float(_flt("LOT_SIZE").get("stepSize", 0) or 0)
                min_notional = float(_flt("NOTIONAL").get("minNotional", 0) or _flt("MIN_NOTIONAL").get("minNotional", 0) or 0)
                print(f"{sym}: tick={tick} step={step} minNotional={min_notional}")
        except Exception as e:
            print(f"[ERR] connector exchangeInfo: {e}")

print("== Self-check complete ==")
