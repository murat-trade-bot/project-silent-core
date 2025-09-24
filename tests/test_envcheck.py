from core.envcheck import load_runtime_config, Mode


def test_load_runtime_config_defaults_sim(monkeypatch):
    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    monkeypatch.delenv("TESTNET_MODE", raising=False)
    monkeypatch.delenv("NOTIFIER_ENABLED", raising=False)
    cfg = load_runtime_config()
    assert cfg.mode == Mode.SIM
    assert cfg.testnet is False
    assert cfg.notifier_enabled is False
