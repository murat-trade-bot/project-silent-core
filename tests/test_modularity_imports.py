def test_import_main_and_initialize():
    import main
    assert hasattr(main, 'initialize_client')
    assert hasattr(main, 'main')

def test_import_engine_and_run_signature():
    from core.engine import BotEngine
    assert hasattr(BotEngine, 'run')
    assert callable(BotEngine.run)

def test_import_csv_logger_callable():
    from core.csv_logger import log_trade_csv
    assert callable(log_trade_csv)

def test_import_metrics_printer():
    from core.metrics import MetricsPrinter
    assert hasattr(MetricsPrinter, 'heartbeat')
    assert hasattr(MetricsPrinter, 'record')
