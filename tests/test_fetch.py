"""fetch.py step 2 테스트: is_naver_blog_main, list_posts, filter_today.

네트워크 호출 금지 — httpx.Client를 monkeypatch로 가짜화한다.
"""

from datetime import datetime
from pathlib import Path

import pytest

from mer_summary.services import fetch
from mer_summary.services.fetch import (
    ArticleText,
    PostRef,
    fetch_article,
    fetch_generic,
    fetch_naver_post,
    filter_today,
    is_naver_blog_main,
    list_posts,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ─── is_naver_blog_main ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url, expected",
    [
        # PC 도메인, 카테고리 없음 → (blogId, None)
        ("https://blog.naver.com/ranto28", ("ranto28", None)),
        ("https://blog.naver.com/ranto28/", ("ranto28", None)),
        ("http://blog.naver.com/ranto28", ("ranto28", None)),
        # 모바일 도메인
        ("https://m.blog.naver.com/ranto28", ("ranto28", None)),
        ("https://m.blog.naver.com/ranto28/", ("ranto28", None)),
        # categoryNo 쿼리 추출 (다른 파라미터 있어도 OK)
        ("https://m.blog.naver.com/ranto28?categoryNo=21&tab=1", ("ranto28", "21")),
        ("https://blog.naver.com/ranto28?categoryNo=19", ("ranto28", "19")),
        ("https://m.blog.naver.com/ranto28?tab=1", ("ranto28", None)),
        # 제외 케이스
        ("https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=1", None),
        ("https://blog.naver.com/PostList.naver?blogId=ranto28", None),
        ("https://blog.naver.com/", None),
        ("https://example.com/blog/post1", None),
        ("https://blog.naver.com/ranto28/some-extra/path", None),
        ("ftp://blog.naver.com/ranto28", None),
    ],
)
def test_is_naver_blog_main(url, expected):
    assert is_naver_blog_main(url) == expected


# ─── list_posts ────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    """httpx.Client 대체 — captured URL/headers + 고정 응답 반환."""

    captured_url: str | None = None
    captured_headers: dict | None = None
    response_text: str = ""

    def __init__(self, *args, **kwargs):
        type(self).captured_headers = kwargs.get("headers")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, **kwargs):
        type(self).captured_url = url
        return _FakeResponse(type(self).response_text)


@pytest.fixture
def fake_httpx(monkeypatch):
    """fetch 모듈의 httpx.Client를 가짜 클라이언트로 교체."""
    _FakeClient.captured_url = None
    _FakeClient.captured_headers = None
    _FakeClient.response_text = ""
    monkeypatch.setattr(fetch.httpx, "Client", _FakeClient)
    return _FakeClient


def test_list_posts_parses_json_returns_postrefs(fake_httpx):
    fake_httpx.response_text = (FIXTURES / "naver_list_sample.json").read_text(encoding="utf-8")

    refs = list_posts("ranto28", count=10)

    assert len(refs) == 5
    assert all(isinstance(r, PostRef) for r in refs)

    first = refs[0]
    assert first.log_no == "224291989573"
    assert first.title == "오늘 오전 엔비디아"  # URL-decoded (+ → space)
    assert first.add_date_raw == "4시간 전"
    assert first.url == (
        "https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=224291989573"
    )


def test_list_posts_sends_user_agent_and_blog_id(fake_httpx):
    fake_httpx.response_text = (FIXTURES / "naver_list_sample.json").read_text(encoding="utf-8")

    list_posts("ranto28", count=15)

    assert fake_httpx.captured_url is not None
    assert "blogId=ranto28" in fake_httpx.captured_url
    assert "countPerPage=15" in fake_httpx.captured_url
    # 기본은 카테고리 0 (전체)
    assert "categoryNo=0" in fake_httpx.captured_url
    assert "parentCategoryNo=0" in fake_httpx.captured_url
    assert fake_httpx.captured_headers["User-Agent"].startswith("Mozilla/")


def test_list_posts_passes_category_no(fake_httpx):
    fake_httpx.response_text = (FIXTURES / "naver_list_sample.json").read_text(encoding="utf-8")

    list_posts("ranto28", category_no="21")

    assert "categoryNo=21" in fake_httpx.captured_url
    assert "parentCategoryNo=21" in fake_httpx.captured_url


def test_list_posts_handles_js_style_escape(fake_httpx):
    """네이버 응답의 \\' 비표준 이스케이프가 파싱 단계에서 깨지지 않아야 한다."""
    fake_httpx.response_text = (
        '{"resultCode":"S","resultMessage":"",'
        '"postList":[{"logNo":"1","title":"a","addDate":"4시간 전"}],'
        "\"paginate\":\"<div class=\\'p\\'></div>\"}"
    )
    refs = list_posts("ranto28")
    assert len(refs) == 1


def test_list_posts_raises_when_result_code_not_s(fake_httpx):
    fake_httpx.response_text = '{"resultCode":"E","resultMessage":"err","postList":[]}'
    with pytest.raises(RuntimeError, match="PostTitleListAsync 실패"):
        list_posts("ranto28")


def test_list_posts_raises_when_json_invalid(fake_httpx):
    fake_httpx.response_text = "not a json at all"
    with pytest.raises(RuntimeError, match="JSON 파싱 실패"):
        list_posts("ranto28")


# ─── filter_today ──────────────────────────────────────────────────────


def _ref(log_no: str, add_date: str) -> PostRef:
    return PostRef(
        url=f"https://blog.naver.com/PostView.naver?blogId=x&logNo={log_no}",
        log_no=log_no,
        title=f"title-{log_no}",
        add_date_raw=add_date,
    )


def test_filter_today_relative_dates_always_today():
    refs = [_ref("a", "4시간 전"), _ref("b", "11시간 전"), _ref("c", "30분 전")]
    now = datetime(2026, 5, 21, 10, 0, 0)

    result = filter_today(refs, now)

    assert [r.log_no for r in result] == ["a", "b", "c"]


def test_filter_today_date_text_matches_today_exactly():
    refs = [
        _ref("a", "2026. 5. 21."),   # 오늘
        _ref("b", "2026. 5. 20."),   # 어제
        _ref("c", "2025. 5. 21."),   # 작년 같은 날
    ]
    now = datetime(2026, 5, 21, 10, 0, 0)

    result = filter_today(refs, now)

    assert [r.log_no for r in result] == ["a"]


def test_filter_today_mixed_now_may_20():
    refs = [
        _ref("a", "4시간 전"),       # 상대 — 항상 오늘
        _ref("b", "11시간 전"),      # 상대 — 항상 오늘
        _ref("c", "2026. 5. 20."),   # 절대 — now가 5/20일 때만 오늘
        _ref("d", "2026. 5. 19."),
    ]
    now = datetime(2026, 5, 20, 10, 0, 0)

    result = filter_today(refs, now)

    assert [r.log_no for r in result] == ["a", "b", "c"]


def test_filter_today_unknown_format_is_not_today():
    refs = [_ref("a", "어제"), _ref("b", "3일 전"), _ref("c", "")]
    now = datetime(2026, 5, 21, 10, 0, 0)

    result = filter_today(refs, now)

    assert result == []


# ─── fetch_naver_post ─────────────────────────────────────────────────


def test_fetch_naver_post_extracts_body_and_strips_title_suffix(fake_httpx):
    fake_httpx.response_text = (FIXTURES / "naver_post_sample.html").read_text(encoding="utf-8")
    url = "https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=224291989573"

    article = fetch_naver_post(url)

    assert isinstance(article, ArticleText)
    assert article.url == url
    assert article.title == "오늘 오전 엔비디아 실적 발표는 어땠나?"  # ' : 네이버 블로그' 제거됨
    assert "엔비디아 1분기 실적 발표" in article.body
    assert "데이터센터 매출 752억" in article.body
    assert "광고 영역" not in article.body  # se-main-container 밖은 안 잡힘
    assert "사이트 헤더" not in article.body


def test_fetch_naver_post_raises_when_container_missing(fake_httpx):
    fake_httpx.response_text = "<html><body><p>본문 없음</p></body></html>"
    with pytest.raises(RuntimeError, match="se-main-container not found"):
        fetch_naver_post("https://blog.naver.com/PostView.naver?blogId=x&logNo=1")


# ─── fetch_article 라우팅 ─────────────────────────────────────────────


def test_fetch_article_routes_postview_to_naver(monkeypatch):
    calls = {"naver": 0, "generic": 0}
    monkeypatch.setattr(
        fetch, "fetch_naver_post",
        lambda u: (calls.__setitem__("naver", calls["naver"] + 1),
                   ArticleText(u, "t", "b"))[1],
    )
    monkeypatch.setattr(
        fetch, "fetch_generic",
        lambda u: (calls.__setitem__("generic", calls["generic"] + 1),
                   ArticleText(u, "t", "b"))[1],
    )

    fetch_article("https://blog.naver.com/PostView.naver?blogId=x&logNo=1")

    assert calls == {"naver": 1, "generic": 0}


def test_fetch_article_routes_other_to_generic(monkeypatch):
    calls = {"naver": 0, "generic": 0}
    monkeypatch.setattr(
        fetch, "fetch_naver_post",
        lambda u: (calls.__setitem__("naver", calls["naver"] + 1),
                   ArticleText(u, "t", "b"))[1],
    )
    monkeypatch.setattr(
        fetch, "fetch_generic",
        lambda u: (calls.__setitem__("generic", calls["generic"] + 1),
                   ArticleText(u, "t", "b"))[1],
    )

    fetch_article("https://example.com/post/123")

    assert calls == {"naver": 0, "generic": 1}


# ─── fetch_generic (trafilatura monkeypatch) ──────────────────────────


def test_fetch_generic_success(monkeypatch):
    monkeypatch.setattr(fetch.trafilatura, "fetch_url", lambda u: "<html>...</html>")
    monkeypatch.setattr(
        fetch.trafilatura, "extract",
        lambda src, **kw: "본문 텍스트입니다.\n두 번째 줄.",
    )

    class _Meta:
        title = "예시 제목"
    monkeypatch.setattr(fetch.trafilatura, "extract_metadata", lambda src: _Meta())

    article = fetch_generic("https://example.com/post")

    assert article.url == "https://example.com/post"
    assert article.title == "예시 제목"
    assert "본문 텍스트입니다" in article.body


def test_fetch_generic_raises_when_download_fails(monkeypatch):
    monkeypatch.setattr(fetch.trafilatura, "fetch_url", lambda u: None)
    with pytest.raises(RuntimeError, match="다운로드 실패"):
        fetch_generic("https://example.com/x")


def test_fetch_generic_raises_when_extract_returns_none(monkeypatch):
    monkeypatch.setattr(fetch.trafilatura, "fetch_url", lambda u: "<html></html>")
    monkeypatch.setattr(fetch.trafilatura, "extract", lambda src, **kw: None)
    with pytest.raises(RuntimeError, match="본문 추출 실패"):
        fetch_generic("https://example.com/x")
