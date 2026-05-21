"""config.load_config() 테스트. monkeypatch로 환경 격리, .env 자동 로드 차단."""

import pytest

from mer_summary.config import Config, load_config


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """각 테스트에서 .env 로드를 막고 필수 변수를 환경에서 제거한다.

    load_dotenv는 기본 usecwd=False라 호출자 파일(config.py) 기준으로
    부모 디렉토리를 검색해 실제 mer-summary/.env를 찾아낸다.
    chdir로는 막을 수 없으므로 함수 자체를 no-op으로 monkeypatch.
    """
    monkeypatch.setattr("mer_summary.config.load_dotenv", lambda *a, **kw: False)
    for name in ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(name, raising=False)


def test_load_config_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    cfg = load_config()

    assert isinstance(cfg, Config)
    assert cfg.anthropic_api_key == "sk-ant-test"
    assert cfg.telegram_bot_token == "1:abc"
    assert cfg.telegram_chat_id == "12345"


def test_load_config_missing_one_variable(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    # ANTHROPIC_API_KEY 누락

    with pytest.raises(RuntimeError) as exc_info:
        load_config()

    assert "ANTHROPIC_API_KEY" in str(exc_info.value)
    assert "TELEGRAM_BOT_TOKEN" not in str(exc_info.value)
    assert "TELEGRAM_CHAT_ID" not in str(exc_info.value)


def test_load_config_missing_all():
    with pytest.raises(RuntimeError) as exc_info:
        load_config()

    msg = str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in msg
    assert "TELEGRAM_BOT_TOKEN" in msg
    assert "TELEGRAM_CHAT_ID" in msg


def test_load_config_empty_string_is_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    with pytest.raises(RuntimeError) as exc_info:
        load_config()

    assert "ANTHROPIC_API_KEY" in str(exc_info.value)


def test_config_is_frozen():
    """Config는 frozen이어서 호출자가 실수로 수정 불가."""
    cfg = Config(anthropic_api_key="a", telegram_bot_token="b", telegram_chat_id="c")
    with pytest.raises(Exception):  # FrozenInstanceError
        cfg.anthropic_api_key = "hacked"  # type: ignore[misc]
