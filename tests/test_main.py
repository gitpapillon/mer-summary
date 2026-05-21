"""__main__ 오케스트레이션 테스트. 모든 services를 monkeypatch."""

from datetime import datetime

import pytest

from mer_summary import __main__ as mainmod
from mer_summary.config import Config
from mer_summary.services.fetch import ArticleText, PostRef
from mer_summary.services.summarize import Summary


_CFG = Config(
    anthropic_api_key="sk-x",
    telegram_bot_token="1:abc",
    telegram_chat_id="12345",
)


@pytest.fixture
def patched(monkeypatch, tmp_path):
    """기본 happy-path: load_config + 모든 외부 서비스 가짜화. 호출 카운트 기록.

    sent_log 파일을 tmp 경로로 격리해 실제 디스크 영향 없음. 빈 상태로 시작.
    list_posts/filter_recent_days는 각 테스트가 명시적으로 다시 monkeypatch한다.
    """
    calls = {"fetch_article": 0, "summarize": 0, "send": 0, "list_posts": 0}

    monkeypatch.setattr(mainmod, "load_config", lambda: _CFG)
    monkeypatch.setattr(mainmod, "DEFAULT_STATE_FILE", tmp_path / "sent.json")

    monkeypatch.setattr(
        mainmod.fetch, "fetch_article",
        lambda url: (calls.__setitem__("fetch_article", calls["fetch_article"] + 1),
                     ArticleText(url, "t", "b"))[1],
    )
    monkeypatch.setattr(
        mainmod.summarize, "summarize",
        lambda article, cfg: (calls.__setitem__("summarize", calls["summarize"] + 1),
                              Summary(article.url, "S", ["a", "b", "c"]))[1],
    )
    monkeypatch.setattr(
        mainmod.telegram, "send",
        lambda summary, cfg: calls.__setitem__("send", calls["send"] + 1),
    )
    monkeypatch.setattr(
        mainmod.fetch, "list_posts",
        lambda blog_id, **kw: (calls.__setitem__("list_posts", calls["list_posts"] + 1),
                               [])[1],
    )
    return calls


def _refs(*log_nos):
    return [
        PostRef(
            url=f"https://blog.naver.com/PostView.naver?blogId=ranto28&logNo={ln}",
            log_no=ln,
            title=f"t-{ln}",
            add_date_raw="1시간 전",
        )
        for ln in log_nos
    ]


# ─── 개별 글 URL 흐름 ─────────────────────────────────────────────────


def test_individual_post_url_flow(patched, tmp_path):
    url = "https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=1"
    rc = mainmod.main([url, "--state-file", str(tmp_path / "s.json")])

    assert rc == 0
    assert patched["fetch_article"] == 1
    assert patched["summarize"] == 1
    assert patched["send"] == 1
    assert patched["list_posts"] == 0


def test_generic_url_flow(patched, tmp_path):
    rc = mainmod.main(["https://example.com/post/1", "--state-file", str(tmp_path / "s.json")])
    assert rc == 0
    assert patched["fetch_article"] == 1
    assert patched["list_posts"] == 0


# ─── 블로그 메인 URL — 어제+오늘 N개 ──────────────────────────────────


def test_blog_main_with_recent_posts(monkeypatch, patched, tmp_path, capsys):
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2", "3", "4", "5"))
    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", lambda refs, now, *, days: refs[:3])

    rc = mainmod.main(["https://blog.naver.com/ranto28", "--state-file", str(tmp_path / "s.json")])

    assert rc == 0
    assert patched["fetch_article"] == 3
    assert patched["send"] == 3
    err = capsys.readouterr().err
    assert "신규 3개 처리" in err


def test_no_recent_posts(monkeypatch, patched, tmp_path, capsys):
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2"))
    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", lambda refs, now, *, days: [])

    rc = mainmod.main(["https://blog.naver.com/ranto28", "--state-file", str(tmp_path / "s.json")])

    assert rc == 0
    assert patched["fetch_article"] == 0
    assert "새로 전송할 글이 없습니다." in capsys.readouterr().err


# ─── dedup ────────────────────────────────────────────────────────────


def test_dedup_skips_already_sent(monkeypatch, patched, tmp_path, capsys):
    state = tmp_path / "s.json"
    # 1과 2를 이미 보낸 상태로 초기화
    from mer_summary.services.dedup import save_sent
    save_sent(state, {"1", "2"})

    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2", "3"))
    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", lambda refs, now, *, days: refs)

    rc = mainmod.main(["https://blog.naver.com/ranto28", "--state-file", str(state)])

    assert rc == 0
    # 신규는 3만 → 1번 처리
    assert patched["fetch_article"] == 1
    assert patched["send"] == 1
    # sent_log 갱신됨 (1, 2, 3 모두 포함)
    from mer_summary.services.dedup import load_sent
    assert load_sent(state) == {"1", "2", "3"}


def test_dedup_all_sent_no_op(monkeypatch, patched, tmp_path, capsys):
    state = tmp_path / "s.json"
    from mer_summary.services.dedup import save_sent
    save_sent(state, {"1", "2", "3"})
    saved_mtime = state.stat().st_mtime

    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2", "3"))
    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", lambda refs, now, *, days: refs)

    rc = mainmod.main(["https://blog.naver.com/ranto28", "--state-file", str(state)])

    assert rc == 0
    assert patched["fetch_article"] == 0
    # sent_log 파일은 변경되지 않음 (no-op)
    assert state.stat().st_mtime == saved_mtime


def test_partial_failure_does_not_pollute_sent_log(monkeypatch, patched, tmp_path):
    state = tmp_path / "s.json"
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2", "3"))
    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", lambda refs, now, *, days: refs)

    # 2번 글에서 summarize 실패
    def flaky(article, cfg):
        if article.url.endswith("logNo=2"):
            raise RuntimeError("API limit")
        return Summary(article.url, "S", ["a", "b", "c"])

    monkeypatch.setattr(mainmod.summarize, "summarize", flaky)

    rc = mainmod.main(["https://blog.naver.com/ranto28", "--state-file", str(state)])

    assert rc == 1
    # 1과 3만 sent_log에 들어감 (2는 실패라서 제외)
    from mer_summary.services.dedup import load_sent
    assert load_sent(state) == {"1", "3"}


# ─── 다중 URL ─────────────────────────────────────────────────────────


def test_multiple_urls_each_listed_separately(monkeypatch, patched, tmp_path):
    calls = []

    def capture_list(blog_id, **kwargs):
        calls.append((blog_id, kwargs.get("category_no")))
        return _refs(f"x-{blog_id}-{kwargs.get('category_no')}")

    monkeypatch.setattr(mainmod.fetch, "list_posts", capture_list)
    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", lambda refs, now, *, days: refs)

    rc = mainmod.main([
        "https://m.blog.naver.com/ranto28?categoryNo=21",
        "https://blog.naver.com/PostList.naver?blogId=ranto28&categoryNo=28",
        "--state-file", str(tmp_path / "s.json"),
    ])

    assert rc == 0
    assert calls == [("ranto28", "21"), ("ranto28", "28")]
    assert patched["fetch_article"] == 2
    assert patched["send"] == 2


# ─── load_config 실패 ─────────────────────────────────────────────────


def test_load_config_failure_returns_2(monkeypatch, tmp_path, capsys):
    def boom():
        raise RuntimeError("env 누락")
    monkeypatch.setattr(mainmod, "load_config", boom)

    rc = mainmod.main(["https://blog.naver.com/ranto28", "--state-file", str(tmp_path / "s.json")])

    assert rc == 2
    assert "env 누락" in capsys.readouterr().err


# ─── --now / --days 인자 ──────────────────────────────────────────────


def test_now_and_days_passed_to_filter(monkeypatch, patched, tmp_path):
    captured = {}
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1"))

    def capture_filter(refs, now, *, days):
        captured["now"] = now
        captured["days"] = days
        return refs

    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", capture_filter)

    mainmod.main([
        "https://blog.naver.com/ranto28",
        "--now", "2026-05-22T10:00:00",
        "--days", "3",
        "--state-file", str(tmp_path / "s.json"),
    ])

    assert captured["now"] == datetime(2026, 5, 22, 10, 0, 0)
    assert captured["days"] == 3


def test_days_default_is_2(monkeypatch, patched, tmp_path):
    captured = {}
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1"))

    def capture_filter(refs, now, *, days):
        captured["days"] = days
        return refs

    monkeypatch.setattr(mainmod.fetch, "filter_recent_days", capture_filter)

    mainmod.main(["https://blog.naver.com/ranto28", "--state-file", str(tmp_path / "s.json")])

    assert captured["days"] == 2
