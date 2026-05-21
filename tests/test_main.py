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
def patched(monkeypatch):
    """기본 happy-path 더미: load_config + services 통째로 가짜화. 호출 카운트 기록."""
    calls = {"fetch_article": 0, "summarize": 0, "send": 0, "list_posts": 0}

    monkeypatch.setattr(mainmod, "load_config", lambda: _CFG)
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
        lambda blog_id, **kwargs: (calls.__setitem__("list_posts", calls["list_posts"] + 1),
                                   [])[1],
    )
    return calls


# ─── 개별 글 URL 흐름 ─────────────────────────────────────────────────


def test_individual_post_url_flow(patched, capsys):
    url = "https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=1"
    rc = mainmod.main([url])

    assert rc == 0
    assert patched["fetch_article"] == 1
    assert patched["summarize"] == 1
    assert patched["send"] == 1
    assert patched["list_posts"] == 0  # 메인 URL 아니므로 list 호출 안 함


def test_generic_url_flow(patched):
    rc = mainmod.main(["https://example.com/post/1"])
    assert rc == 0
    assert patched["fetch_article"] == 1
    assert patched["list_posts"] == 0


# ─── 블로그 메인 URL — 당일 N개 ───────────────────────────────────────


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


def test_blog_main_with_today_posts(monkeypatch, patched, capsys):
    # 5개 글 중 3개를 당일로 반환하도록 monkeypatch
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2", "3", "4", "5"))
    monkeypatch.setattr(mainmod.fetch, "filter_today", lambda refs, now: refs[:3])

    rc = mainmod.main(["https://blog.naver.com/ranto28"])

    assert rc == 0
    assert patched["fetch_article"] == 3
    assert patched["summarize"] == 3
    assert patched["send"] == 3
    err = capsys.readouterr().err
    assert "당일 글 3개" in err


def test_blog_main_with_no_today_posts(monkeypatch, patched, capsys):
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2"))
    monkeypatch.setattr(mainmod.fetch, "filter_today", lambda refs, now: [])

    rc = mainmod.main(["https://blog.naver.com/ranto28"])

    assert rc == 0
    assert patched["fetch_article"] == 0
    assert "당일 작성된 글이 없습니다." in capsys.readouterr().err


# ─── 부분 실패 ─────────────────────────────────────────────────────────


def test_partial_failure_skips_and_returns_1(monkeypatch, patched, capsys):
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1", "2", "3"))
    monkeypatch.setattr(mainmod.fetch, "filter_today", lambda refs, now: refs)

    # 2번째 글에서 summarize가 RuntimeError 발생
    def flaky_summarize(article, cfg):
        if article.url.endswith("logNo=2"):
            raise RuntimeError("API limit")
        return Summary(article.url, "S", ["a", "b", "c"])

    monkeypatch.setattr(mainmod.summarize, "summarize", flaky_summarize)

    rc = mainmod.main(["https://blog.naver.com/ranto28"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "[skip]" in err
    assert "API limit" in err


# ─── load_config 실패 ─────────────────────────────────────────────────


def test_load_config_failure_returns_2(monkeypatch, capsys):
    def boom():
        raise RuntimeError("env 누락")
    monkeypatch.setattr(mainmod, "load_config", boom)

    rc = mainmod.main(["https://blog.naver.com/ranto28"])

    assert rc == 2
    assert "env 누락" in capsys.readouterr().err


# ─── --now 주입 ────────────────────────────────────────────────────────


def test_now_argument_passed_to_filter_today(monkeypatch, patched):
    captured = {}
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("1"))

    def capture_filter(refs, now):
        captured["now"] = now
        return refs

    monkeypatch.setattr(mainmod.fetch, "filter_today", capture_filter)

    mainmod.main(["https://blog.naver.com/ranto28", "--now", "2026-05-21T10:00:00"])

    assert captured["now"] == datetime(2026, 5, 21, 10, 0, 0)


# ─── list_posts 실패 ──────────────────────────────────────────────────


def test_list_posts_failure_returns_1(monkeypatch, patched, capsys):
    monkeypatch.setattr(
        mainmod.fetch, "list_posts",
        lambda blog_id, **kw: (_ for _ in ()).throw(RuntimeError("net down")),
    )

    rc = mainmod.main(["https://blog.naver.com/ranto28"])

    assert rc == 1
    assert "net down" in capsys.readouterr().err


# ─── categoryNo 전달 ──────────────────────────────────────────────────


def test_category_no_passed_to_list_posts(monkeypatch, patched):
    captured = {}

    def capture_list(blog_id, **kwargs):
        captured["blog_id"] = blog_id
        captured["category_no"] = kwargs.get("category_no")
        return []

    monkeypatch.setattr(mainmod.fetch, "list_posts", capture_list)

    mainmod.main(["https://m.blog.naver.com/ranto28?categoryNo=21&tab=1"])

    assert captured["blog_id"] == "ranto28"
    assert captured["category_no"] == "21"


def test_category_no_is_none_when_url_has_no_query(monkeypatch, patched):
    captured = {}

    def capture_list(blog_id, **kwargs):
        captured["category_no"] = kwargs.get("category_no")
        return []

    monkeypatch.setattr(mainmod.fetch, "list_posts", capture_list)

    mainmod.main(["https://blog.naver.com/ranto28"])

    assert captured["category_no"] is None


# ─── 다중 URL ──────────────────────────────────────────────────────────


def test_multiple_urls_each_listed_separately(monkeypatch, patched, capsys):
    calls = []

    def capture_list(blog_id, **kwargs):
        calls.append((blog_id, kwargs.get("category_no")))
        return _refs(f"x-{blog_id}-{kwargs.get('category_no')}")

    monkeypatch.setattr(mainmod.fetch, "list_posts", capture_list)
    monkeypatch.setattr(mainmod.fetch, "filter_today", lambda refs, now: refs)

    rc = mainmod.main([
        "https://m.blog.naver.com/ranto28?categoryNo=21",
        "https://blog.naver.com/PostList.naver?blogId=ranto28&categoryNo=28",
    ])

    assert rc == 0
    assert calls == [("ranto28", "21"), ("ranto28", "28")]
    # 두 URL 각각 1개씩 = 총 2개 글 처리
    assert patched["fetch_article"] == 2
    assert patched["send"] == 2


def test_multiple_urls_partial_failure_returns_1(monkeypatch, patched, capsys):
    def list_first_ok_second_fails(blog_id, **kwargs):
        if kwargs.get("category_no") == "28":
            raise RuntimeError("temp net error")
        return _refs("a")

    monkeypatch.setattr(mainmod.fetch, "list_posts", list_first_ok_second_fails)
    monkeypatch.setattr(mainmod.fetch, "filter_today", lambda refs, now: refs)

    rc = mainmod.main([
        "https://m.blog.naver.com/ranto28?categoryNo=21",
        "https://blog.naver.com/PostList.naver?blogId=ranto28&categoryNo=28",
    ])

    assert rc == 1
    err = capsys.readouterr().err
    assert "temp net error" in err
    # 첫 URL은 정상 처리됨
    assert patched["fetch_article"] == 1


def test_multiple_urls_all_no_today_posts(monkeypatch, patched, capsys):
    monkeypatch.setattr(mainmod.fetch, "list_posts", lambda blog_id, **kw: _refs("a"))
    monkeypatch.setattr(mainmod.fetch, "filter_today", lambda refs, now: [])

    rc = mainmod.main([
        "https://m.blog.naver.com/ranto28?categoryNo=21",
        "https://blog.naver.com/PostList.naver?blogId=ranto28&categoryNo=28",
    ])

    assert rc == 0
    assert patched["fetch_article"] == 0
    err = capsys.readouterr().err
    assert "모든 URL에 당일 작성된 글이 없습니다." in err
