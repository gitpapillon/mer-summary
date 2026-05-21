# Step 3: naver-body

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/ARCHITECTURE.md` (타입 섹션)
- `/docs/ARD.md` (ARD-002, ARD-007)
- `/src/mer_summary/services/fetch.py` (이전 step 산출물 — `PostRef`, `is_naver_blog_main` 패턴 활용)

## 작업

`src/mer_summary/services/fetch.py` 에 본문 추출 함수를 **추가**한다 (새 파일 만들지 말고 step 2 파일에 추가).

### 타입 추가

```python
@dataclass(frozen=True)
class ArticleText:
    url: str
    title: str
    body: str   # 정제된 본문 텍스트 (HTML 태그 없음)
```

### 함수 시그니처

```python
def fetch_naver_post(url: str) -> ArticleText:
    """PostView.naver URL 에서 본문 추출.

    1. httpx GET (User-Agent 헤더 필수, 타임아웃 10초)
    2. BeautifulSoup으로 'div.se-main-container' 선택
    3. .get_text(separator='\\n', strip=True) 로 본문
    4. <title> 태그에서 제목 추출 (": 네이버 블로그" 접미사 제거)

    실패 시 RuntimeError raise (HTTP 에러, 셀렉터 미발견 등).
    """
    ...

def fetch_generic(url: str) -> ArticleText:
    """일반 사이트 (네이버 아닌 곳) 본문 추출.

    trafilatura.fetch_url + trafilatura.extract 사용.
    output_format='txt', favor_recall=True 권장.
    제목은 trafilatura의 metadata.title 또는 페이지 <title>.
    실패 시 RuntimeError.
    """
    ...

def fetch_article(url: str) -> ArticleText:
    """URL 라우터.

    PostView.naver 패턴이면 fetch_naver_post, 아니면 fetch_generic.
    """
    ...
```

### 핵심 규칙

- `fetch_naver_post`는 BS4의 `select_one("div.se-main-container")` 결과가 None이면 `RuntimeError("se-main-container not found: <url>")` raise.
- `<title>`이 `"제목 : 네이버 블로그"` 형태면 `" : 네이버 블로그"` 접미사 제거 (정확히 일치할 때만).
- 본문 텍스트는 strip 후 연속 줄바꿈 3개 이상은 2개로 정규화 (선택 — 가독성 목적, 강제 아님).
- `fetch_generic`은 trafilatura가 None 반환 시 RuntimeError.
- 두 함수 모두 동일한 User-Agent 헤더 사용 (모듈 상수 재사용).

### 테스트 (`tests/test_fetch.py` 에 추가)

#### 픽스처

`tests/fixtures/naver_post_sample.html` 생성 — 진짜 PostView 응답의 핵심 부분 축약:

```html
<html>
<head><title>오늘 오전 엔비디아 실적 발표는 어땠나? : 네이버 블로그</title></head>
<body>
  <div class="se-main-container">
    <p>2026년 5월 21일, 오전 5시 20분에 엔비디아 1분기 실적 발표가 있었다.</p>
    <p>매출은 예상(791억 달러)보다 높은 816억 달러가 나왔고...</p>
  </div>
  <div class="footer">광고 영역 — 본문 아님</div>
</body>
</html>
```

#### 테스트 케이스

1. `fetch_naver_post` (monkeypatch로 httpx 가짜 응답에 위 픽스처 주입):
   - `ArticleText.title == "오늘 오전 엔비디아 실적 발표는 어땠나?"` (접미사 제거됨)
   - `body`에 "엔비디아 1분기 실적 발표" 포함.
   - `body`에 "광고 영역" 미포함 (다른 div는 안 잡힘).
2. `fetch_naver_post` 실패: se-main-container 없는 HTML 주입 → `RuntimeError`.
3. `fetch_article` 라우팅:
   - URL이 `PostView.naver` 포함 → `fetch_naver_post` 호출 (monkeypatch로 가짜 호출 카운트 확인).
   - URL이 일반 사이트 → `fetch_generic` 호출.
4. `fetch_generic` (monkeypatch로 `trafilatura.fetch_url`/`extract` 가짜화):
   - extract가 정상 텍스트 반환 → `ArticleText` 반환.
   - extract가 None 반환 → `RuntimeError`.

## Acceptance Criteria

```bash
uv run pytest tests/test_fetch.py -q
uv run ruff check src/mer_summary/services/fetch.py tests/test_fetch.py
```

- step 2의 기존 테스트(`is_naver_blog_main`, `list_posts`, `filter_today`)도 그대로 통과해야 한다.
- 새 케이스 모두 통과.

## 검증 절차

1. AC 실행.
2. 체크리스트:
   - `fetch.py`에 함수가 6개 (`is_naver_blog_main`, `list_posts`, `filter_today`, `fetch_naver_post`, `fetch_generic`, `fetch_article`) + 타입 2개(`PostRef`, `ArticleText`) 정의돼 있는가?
   - 외부 라이브러리 import는 `httpx`, `bs4`(BeautifulSoup), `trafilatura`, `urllib.parse`만인가?
3. step 3 상태 업데이트.

## 금지사항

- 요약/전송 모듈 작성 금지. 이유: scope 분리.
- step 2 함수 시그니처/동작 변경 금지. 기존 테스트가 깨지면 안 됨. 이유: 회귀 방지.
- BS4 외의 HTML 파서(lxml 직접, regex 등)로 본문 추출 금지. 이유: ARD-007 명시.
- `requests` 라이브러리 추가 금지 — `httpx`만. 이유: 의존성 최소화 + 동일 클라이언트.
