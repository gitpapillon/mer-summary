"""URL → 본문/메타 추출. 네이버 블로그는 전용 어댑터(BS4), 그 외는 trafilatura."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qs, unquote_plus, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; mer-summary/0.1)"
_TIMEOUT = 10.0

_NAVER_HOSTS = {"blog.naver.com", "m.blog.naver.com"}
_BLOG_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_DATE_TEXT_RE = re.compile(r"^(\d{4})\. ?(\d{1,2})\. ?(\d{1,2})\.$")
_RELATIVE_RE = re.compile(r"^\d+(분|시간) 전$")


@dataclass(frozen=True)
class PostRef:
    url: str           # 완성된 PostView.naver URL
    log_no: str
    title: str         # URL-decoded
    add_date_raw: str  # "X시간 전" / "2026. 5. 21." 등 원문


@dataclass(frozen=True)
class ArticleText:
    url: str
    title: str
    body: str   # 정제된 본문 (HTML 태그 없음)


_NAVER_TITLE_SUFFIX = " : 네이버 블로그"


def is_naver_blog_main(url: str) -> tuple[str, str | None] | None:
    """블로그 메인 URL이면 (blogId, categoryNo) 반환, 아니면 None.

    매칭:
      - `https://blog.naver.com/{blogId}` (PC, 끝 슬래시 허용)
      - `https://m.blog.naver.com/{blogId}` (모바일)
      - `https://blog.naver.com/PostList.naver?blogId={id}` (글 목록 페이지, query-based)
      - 위 모두 + `?categoryNo={N}` 쿼리 추출
    제외: PostView.naver(개별 글) / blogId 없는 형태 / 다른 도메인.
    categoryNo가 없거나 비어있으면 두 번째 값은 None.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.hostname not in _NAVER_HOSTS:
        return None
    qs = parse_qs(parsed.query)
    cat = (qs.get("categoryNo") or [None])[0]
    cat = cat if cat else None

    path = parsed.path.strip("/")

    # 패턴 1: blog.naver.com/{blogId} — path가 곧 blogId
    if path and "/" not in path and _BLOG_ID_RE.match(path):
        return (path, cat)

    # 패턴 2: blog.naver.com/PostList.naver?blogId={id} — query에서 blogId 추출
    if path == "PostList.naver":
        blog_id = (qs.get("blogId") or [None])[0]
        if blog_id and _BLOG_ID_RE.match(blog_id):
            return (blog_id, cat)

    return None


def list_posts(
    blog_id: str, *, count: int = 30, category_no: str | None = None
) -> list[PostRef]:
    """PostTitleListAsync.naver JSON 호출 → PostRef 리스트.

    category_no가 주어지면 해당 카테고리 글만 조회. None이면 전체(=0).
    네이버 응답은 JS-style 이스케이프(\\')를 포함하므로 치환 후 JSON 파싱.
    User-Agent 헤더 필수.
    """
    cat = category_no or "0"
    url = (
        "https://blog.naver.com/PostTitleListAsync.naver"
        f"?blogId={blog_id}&currentPage=1&countPerPage={count}"
        f"&categoryNo={cat}&parentCategoryNo={cat}"
    )
    with httpx.Client(timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        r = client.get(url)
        r.raise_for_status()
        raw = r.text
    try:
        data = json.loads(raw.replace("\\'", "'"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"PostTitleListAsync 응답 JSON 파싱 실패: {e}; head={raw[:200]!r}") from e

    if data.get("resultCode") != "S":
        raise RuntimeError(f"PostTitleListAsync 실패: {data}")

    refs: list[PostRef] = []
    for item in data.get("postList", []):
        log_no = item["logNo"]
        refs.append(
            PostRef(
                url=f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}",
                log_no=log_no,
                title=unquote_plus(item.get("title", "")),
                add_date_raw=item.get("addDate", ""),
            )
        )
    return refs


def fetch_naver_post(url: str) -> ArticleText:
    """PostView.naver URL에서 본문 추출.

    1) httpx GET (UA 헤더, 타임아웃)
    2) BeautifulSoup으로 div.se-main-container 선택
    3) get_text(separator='\\n', strip=True) + zero-width space/연속 공백 정규화
    4) <title>에서 ' : 네이버 블로그' 접미사 제거
    """
    with httpx.Client(timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        r = client.get(url)
        r.raise_for_status()
        html_src = r.text

    soup = BeautifulSoup(html_src, "html.parser")
    container = soup.select_one("div.se-main-container")
    if container is None:
        raise RuntimeError(f"se-main-container not found: {url}")

    body = container.get_text(separator="\n", strip=True)
    body = body.replace("​", "")              # zero-width space 제거
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if title.endswith(_NAVER_TITLE_SUFFIX):
        title = title[: -len(_NAVER_TITLE_SUFFIX)]

    return ArticleText(url=url, title=title, body=body)


def fetch_generic(url: str) -> ArticleText:
    """일반 사이트 본문 추출 (trafilatura).

    HTML fetch는 trafilatura.fetch_url 사용 (내부적으로 자체 UA 적용).
    extract가 None이면 RuntimeError.
    """
    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise RuntimeError(f"fetch_generic: 페이지 다운로드 실패: {url}")
    body = trafilatura.extract(downloaded, output_format="txt", favor_recall=True)
    if not body:
        raise RuntimeError(f"fetch_generic: 본문 추출 실패: {url}")

    # 제목: trafilatura metadata 우선, 폴백으로 페이지 <title>
    meta = trafilatura.extract_metadata(downloaded)
    title = (meta.title if meta and meta.title else "") or ""
    if not title:
        soup = BeautifulSoup(downloaded, "html.parser")
        t = soup.find("title")
        title = t.get_text(strip=True) if t else ""

    return ArticleText(url=url, title=title, body=body.strip())


def fetch_article(url: str) -> ArticleText:
    """URL 라우터 — PostView.naver 패턴이면 네이버 어댑터, 아니면 generic."""
    if "PostView.naver" in url and "blog.naver.com" in url:
        return fetch_naver_post(url)
    return fetch_generic(url)


def filter_today(refs: list[PostRef], now: datetime) -> list[PostRef]:
    """add_date_raw가 '오늘'인 PostRef만 반환.

    규칙 (ARD-008):
      - r'\\d+분 전' / r'\\d+시간 전' → 당일
      - r'YYYY. M. D.' → now.date()와 정확히 일치 시 당일
      - 그 외 → 당일 아님 (보수적)
    """
    return filter_recent_days(refs, now, days=1)


def filter_recent_days(refs: list[PostRef], now: datetime, *, days: int) -> list[PostRef]:
    """최근 N일(오늘 포함) 안에 작성된 PostRef만 반환.

    예: days=2 → 오늘 + 어제. days=1 → 오늘만(== filter_today).
    규칙:
      - r'\\d+분 전' / r'\\d+시간 전' → 항상 포함 (오늘 작성으로 간주).
      - r'YYYY. M. D.' → now.date() - (days-1) 이상이면 포함.
      - 그 외 (정체불명 포맷) → 제외 (보수적).
    """
    if days < 1:
        raise ValueError(f"days는 1 이상이어야 함: {days}")
    cutoff = now.date() - timedelta(days=days - 1)
    out: list[PostRef] = []
    for r in refs:
        raw = r.add_date_raw.strip()
        if _RELATIVE_RE.match(raw):
            out.append(r)
            continue
        m = _DATE_TEXT_RE.match(raw)
        if m:
            y, mo, d = (int(x) for x in m.groups())
            try:
                post_date = datetime(y, mo, d).date()
            except ValueError:
                continue
            if post_date >= cutoff:
                out.append(r)
    return out
