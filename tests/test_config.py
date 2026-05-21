"""config.load_config() 테스트. monkeypatch로 환경 격리, .env 자동 로드 차단."""

import pytest

from mer_summary.config import Config, load_config


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """각 테스트는 작업 디렉토리를 tmp_path로 이동해 우연한 .env 로드를 막는다.
    그리고 3개 필수 변수를 모두 삭제해 깨끗한 상태에서 시작.
    """
    monkeypatch.chdir(tmp_path)
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
