"""telegram.send / format_message 테스트. httpx.Client.post를 monkeypatch."""

import pytest

from mer_summary.config import Config
from mer_summary.services import telegram as tg_mod
from mer_summary.services.summarize import Summary
from mer_summary.services.telegram import (
    TELEGRAM_MAX_LENGTH,
    format_message,
    send,
)


@pytest.fixture
def cfg():
    return Config(
        anthropic_api_key="sk-x",
        telegram_bot_token="1:abc",
        telegram_chat_id="12345",
    )


@pytest.fixture
def summary():
    return Summary(
        source_url="https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=1",
        title="엔비디아 실적 요약",
        bullets=[
            "매출 816억 달러로 예상치 상회",
            "데이터센터 매출 752억 달러",
            "전년대비 매출 +85%",
            "자사주 매입 한도 1185억으로 확대",
            "2분기 가이던스 891-928억 달러",
        ],
    )


# ─── format_message ─────────────────────────────────────────────────────


def test_format_message_contains_all_parts(summary):
    text = format_message(summary)

    assert text.startswith(f"📌 {summary.title}")
    for b in summary.bullets:
        assert f"• {b}" in text
    assert text.endswith(f"🔗 {summary.source_url}")


def test_format_message_truncates_when_too_long():
    huge = Summary(
        source_url="https://example.com",
        title="A" * 100,
        bullets=["x" * 2000, "y" * 2000, "z" * 2000],  # 명백히 4096 초과
    )

    text = format_message(huge)

    assert len(text) <= TELEGRAM_MAX_LENGTH
    assert text.endswith("…")


def test_format_message_no_truncation_when_within_limit(summary):
    text = format_message(summary)
    assert len(text) <= TELEGRAM_MAX_LENGTH
    assert not text.endswith("…")


# ─── send — 가짜 httpx ─────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict, text: str = ""):
        self.status_code = status_code
        self._json = json_body
        self.text = text or str(json_body)

    def json(self):
        return self._json


class _FakeClient:
    captured_url: str | None = None
    captured_payload: dict | None = None
    response: _FakeResponse | None = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, *, json):
        type(self).captured_url = url
        type(self).captured_payload = json
        return type(self).response


@pytest.fixture
def fake_httpx(monkeypatch):
    _FakeClient.captured_url = None
    _FakeClient.captured_payload = None
    _FakeClient.response = None
    monkeypatch.setattr(tg_mod.httpx, "Client", _FakeClient)
    return _FakeClient


def test_send_success(fake_httpx, summary, cfg):
    fake_httpx.response = _FakeResponse(200, {"ok": True, "result": {"message_id": 42}})

    send(summary, cfg)  # 예외 없어야 함

    assert fake_httpx.captured_url == "https://api.telegram.org/bot1:abc/sendMessage"
    assert fake_httpx.captured_payload["chat_id"] == "12345"
    assert summary.title in fake_httpx.captured_payload["text"]
    # parse_mode 사용 금지
    assert "parse_mode" not in fake_httpx.captured_payload


def test_send_raises_on_http_error(fake_httpx, summary, cfg):
    fake_httpx.response = _FakeResponse(
        400, {"ok": False, "description": "bad request"}, text="bad request body"
    )
    with pytest.raises(RuntimeError, match="HTTP 400"):
        send(summary, cfg)


def test_send_raises_when_ok_false(fake_httpx, summary, cfg):
    fake_httpx.response = _FakeResponse(
        200, {"ok": False, "description": "chat not found"}
    )
    with pytest.raises(RuntimeError, match="chat not found"):
        send(summary, cfg)
