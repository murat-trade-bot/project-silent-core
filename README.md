### Development & CI

Dev kurulumu:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install
```

Yerel kalite kontrolleri:

```bash
make fmt      # otomatik düzeltme (isort + black + ruff --fix)
make lint     # sadece kontrol
make test     # pytest
```

CI: GitHub Actions workflow `.github/workflows/ci.yml` push/PR'da ruff, black --check, isort --check-only, pytest çalıştırır.

# Project Silent Core (Spot-only, No Leverage)

Silent Core, **sadece spot** piyasalarda çalışan (kaldıraç YOK) bir al-sat botudur.
Amaç: güvenli, iz bırakmayan, algoritmalara yakalanmayacak şekilde insan benzeri işlem dağılımı.

## Kurulum
```bash
python -m venv .venv
# Windows:
.\\.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env  # değerleri düzenle
```

## Çalıştırma
```bash
python main.py
```

## Testler
```bash
pytest -q
```

## Güvenlik
- `.env` repoya girmez.
- Sadece spot, kaldıraç yok.
- API anahtarlarını sınırlı yetkilerle kullanın.

---

### Logging
- Varsayılan dosya: `logs/bot.log` (otomatik oluşturulur, max ~2MB, 5 yedek dosya rotasyonu)
- Ortam değişkenleri:
	- `LOG_LEVEL` (varsayılan: `INFO`)
	- `LOG_DIR` (varsayılan: `logs`)
- Kullanım:
```python
from core.logger import logger, set_level, log_exceptions

logger.info("Başlatılıyor...")

@log_exceptions("örnek")
def critical_section():
		# ...
		pass
```

### Order Pipeline (opsiyonel)
- Ortak karar modeli: `Decision`, plan şeması: `OrderPlan`.
- ENV bayrakları:
	- `ORDER_PIPELINE_ENABLED=false`
	- `ORDER_PIPELINE_LOG=true`
- Entegrasyon örneği:
```python
from core.pipeline import build_order_plan_from_signals, validate_order_plan, execute_order_plan
from core.types import SignalBundle
sb = SignalBundle(symbol="BTCUSDT", buy_score=0.72, sell_score=0.18, regime_on=True)
plan = build_order_plan_from_signals(sb)
if plan:
		rc = validate_order_plan(plan)
		if rc.ok:
				res = execute_order_plan(plan)
```


### Risk & Order Filters
- `modules/order_filters.validate_order_plan(plan, market_state, account_state)` tek doğrulama noktasıdır.
- Kurallar:
	- `tickSize`/`stepSize` yuvarlama (bkz. `core/num.py`)
	- `minNotional` kontrolü (bkz. `core/exchange_rules.py`)
	- cooldown / overtrade guard (bkz. `core/cooldown.py`)
- ENV:
	- `USE_EXCHANGE_INFO=false` (opsiyonel gerçek kural besleme)
	- `DEFAULT_TICK_SIZE`, `DEFAULT_STEP_SIZE`, `DEFAULT_MIN_NOTIONAL_USDT`
	- `MIN_TRADE_SPACING_SEC`, `MAX_TRADES_PER_DAY`

### Runtime Profilleri & Metrics
- Çalışma modları (`core/envcheck.py`):
	- `EXECUTION_MODE=SIM|LIVE` (varsayılan: `SIM`)
	- `TESTNET_MODE` ve `NOTIFIER_ENABLED` bayrakları
	- `LIVE` modda `BINANCE_API_KEY` ve `BINANCE_API_SECRET` zorunlu; eksikse uygulama başlatılmaz.
- Prometheus metrikleri (`core/metrics.py`):
	- Ortam değişkenleri:
		- `METRICS_ENABLED=false`
		- `METRICS_PORT=9108`
	- Sayaçlar ve histogramlar:
		- `orders_total{symbol,side,status}`
		- `order_rejections_total{reason}`
		- `exceptions_total{type}`
		- `order_execution_seconds` (Histogram)
	- `main.py` başlangıcında otomatik başlatılır; `METRICS_ENABLED=true` ise HTTP endpoint ayağa kalkar.


