"""summarize.summarize() 테스트. Anthropic 클라이언트는 monkeypatch로 가짜화."""

import pytest

from mer_summary.config import Config
from mer_summary.services import summarize as summarize_mod
from mer_summary.services.fetch import ArticleText
from mer_summary.services.summarize import MODEL, Summary, summarize


@pytest.fixture
def cfg():
    return Config(
        anthropic_api_key="sk-ant-test",
        telegram_bot_token="1:abc",
        telegram_chat_id="12345",
    )


@pytest.fixture
def article():
    return ArticleText(
        url="https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=1",
        title="엔비디아 실적",
        body="매출 816억 달러. 데이터센터 +92%.",
    )


class _FakeContentBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeMessage:
    def __init__(self, text: str):
        self.content = [_FakeContentBlock(text)]


class _FakeMessages:
    """client.messages.create 호출을 캡처하고 고정 응답을 돌려준다."""

    last_call: dict | None = None
    response_text: str = ""

    def create(self, **kwargs):
        type(self).last_call = kwargs
        return _FakeMessage(type(self).response_text)


class _FakeAnthropic:
    captured_api_key: str | None = None

    def __init__(self, *, api_key: str):
        type(self).captured_api_key = api_key
        self.messages = _FakeMessages()


@pytest.fixture
def fake_anthropic(monkeypatch):
    _FakeMessages.last_call = None
    _FakeMessages.response_text = ""
    _FakeAnthropic.captured_api_key = None
    monkeypatch.setattr(summarize_mod.anthropic, "Anthropic", _FakeAnthropic)
    return _FakeMessages


# ─── 정상 케이스 ──────────────────────────────────────────────────────


def test_summarize_success(fake_anthropic, article, cfg):
    fake_anthropic.response_text = (
        '{"title":"엔비디아 실적 요약",'
        '"bullets":["매출 816억 달러","데이터센터 752억","전년대비 +85%"]}'
    )

    result = summarize(article, cfg)

    assert isinstance(result, Summary)
    assert result.source_url == article.url
    assert result.title == "엔비디아 실적 요약"
    assert result.bullets == ["매출 816억 달러", "데이터센터 752억", "전년대비 +85%"]


def test_summarize_uses_correct_model_and_caching(fake_anthropic, article, cfg):
    fake_anthropic.response_text = (
        '{"title":"t","bullets":["a","b","c"]}'
    )

    summarize(article, cfg)

    call = fake_anthropic.last_call
    assert call["model"] == MODEL
    # cache_control 적용 확인
    assert isinstance(call["system"], list)
    assert call["system"][0].get("cache_control") == {"type": "ephemeral"}
    # API 키 전달 확인
    assert _FakeAnthropic.captured_api_key == "sk-ant-test"


def test_summarize_passes_title_and_body_in_user_message(fake_anthropic, article, cfg):
    fake_anthropic.response_text = '{"title":"t","bullets":["a","b","c"]}'

    summarize(article, cfg)

    user_msg = fake_anthropic.last_call["messages"][0]["content"]
    assert article.title in user_msg
    assert article.body in user_msg


# ─── 실패 케이스 ──────────────────────────────────────────────────────


def test_summarize_raises_when_response_not_json(fake_anthropic, article, cfg):
    fake_anthropic.response_text = "여기 요약입니다: 매출이 많이 나왔네요."
    with pytest.raises(RuntimeError, match="JSON 아님"):
        summarize(article, cfg)


def test_summarize_raises_when_title_missing(fake_anthropic, article, cfg):
    fake_anthropic.response_text = '{"bullets":["a","b","c"]}'
    with pytest.raises(RuntimeError, match="title"):
        summarize(article, cfg)


def test_summarize_raises_when_bullets_too_few(fake_anthropic, article, cfg):
    fake_anthropic.response_text = '{"title":"t","bullets":["a","b"]}'
    with pytest.raises(RuntimeError, match="bullets"):
        summarize(article, cfg)


def test_summarize_raises_when_bullets_too_many(fake_anthropic, article, cfg):
    fake_anthropic.response_text = (
        '{"title":"t","bullets":["a","b","c","d","e","f"]}'
    )
    with pytest.raises(RuntimeError, match="bullets"):
        summarize(article, cfg)


def test_summarize_raises_when_bullets_not_list(fake_anthropic, article, cfg):
    fake_anthropic.response_text = '{"title":"t","bullets":"a, b, c"}'
    with pytest.raises(RuntimeError, match="bullets"):
        summarize(article, cfg)
