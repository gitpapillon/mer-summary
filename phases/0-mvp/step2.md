# Step 2: naver-list

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/ARCHITECTURE.md`
- `/docs/ARD.md` (ARD-005, ARD-007, ARD-008 — 특히 날짜 파싱 규칙)
- `/docs/PRD.md` (핵심 기능 #1)
- `/src/mer_summary/config.py` (이전 step 산출물)

## 작업

`src/mer_summary/services/fetch.py` 를 만든다. **이 step은 글 목록 + 당일 필터까지만** 다룬다. 본문 추출은 step 3에서.

### 타입 정의 (같은 파일에)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class PostRef:
    url: str          # 완성된 PostView.naver URL
    log_no: str       # logNo 문자열
    title: str        # URL-디코드된 제목
    add_date_raw: str # "X시간 전" / "YYYY. M. D." 원문
```

### 함수 시그니처

```python
def is_naver_blog_main(url: str) -> str | None:
    """블로그 메인 URL 패턴이면 blogId 반환, 아니면 None.

    매칭 패턴 (https/http, 끝 슬래시 허용):
      - https://blog.naver.com/{blogId}
      - https://blog.naver.com/{blogId}/
    NOT 매칭:
      - PostView.naver?... (개별 글)
      - blog.naver.com (blogId 없음)
      - 다른 도메인
    """
    ...

def list_posts(blog_id: str, *, count: int = 30) -> list[PostRef]:
    """네이버 PostTitleListAsync.naver JSON을 호출해 PostRef 리스트 반환.

    엔드포인트: https://blog.naver.com/PostTitleListAsync.naver
      쿼리: blogId, currentPage=1, countPerPage={count}, categoryNo=0, parentCategoryNo=0
    User-Agent 헤더 필수. 응답 JSON의 postList[]에서 logNo, title(URL-decode), addDate 추출.
    """
    ...

def filter_today(refs: list[PostRef], now: datetime) -> list[PostRef]:
    """add_date_raw가 '오늘'에 해당하는 항목만 골라낸다.

    당일 판정 규칙 (ARD-008):
      - r"\d+분 전"     → 당일
      - r"\d+시간 전"   → 당일
      - r"YYYY. M. D." → now.date()와 정확히 일치하면 당일
      - 그 외 ("어제", "X일 전", 정체불명 포맷) → 당일 아님 (보수적)
    """
    ...
```

### 핵심 규칙

- HTTP 요청은 `httpx.Client`를 짧게 with-블록으로 열어서 사용 (커넥션 누수 방지).
- User-Agent는 모듈 상수 (`USER_AGENT = "Mozilla/5.0 (compatible; mer-summary/0.1)"`).
- 타임아웃: 10초.
- 제목 URL-decode: `urllib.parse.unquote_plus(title_raw)`.
- `PostView` URL 조립: `f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"`.
- `list_posts`가 네트워크/JSON 파싱 실패 시 `RuntimeError`(원본 응답 일부 포함)를 raise.

### 테스트 (`tests/test_fetch.py`)

네트워크 호출 금지 — `httpx.Client.get` 또는 모듈 함수를 monkeypatch.

#### 픽스처 데이터

`tests/fixtures/naver_list_sample.json` 생성 (실제 응답 축약, **사용자 시스템과 동일 포맷**):

```json
{
  "resultCode": "S",
  "resultMessage": "",
  "postList": [
    {"logNo":"224291989573","title":"%EC%98%A4%EB%8A%98+%EC%98%A4%EC%A0%84+%EC%97%94%EB%B9%84%EB%94%94%EC%95%84","addDate":"4시간 전"},
    {"logNo":"224291577587","title":"%EC%9D%BC%EB%B3%B8%EC%9D%80%ED%96%89","addDate":"11시간 전"},
    {"logNo":"224290900863","title":"%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90","addDate":"2026. 5. 20."},
    {"logNo":"224289976939","title":"%EC%97%AD%EB%85%B8%ED%99%94","addDate":"2026. 5. 20."},
    {"logNo":"224289833145","title":"%ED%8A%B8%EB%9F%BC%ED%94%84","addDate":"2026. 5. 19."}
  ]
}
```

#### 테스트 케이스

1. `is_naver_blog_main`:
   - `"https://blog.naver.com/ranto28"` → `"ranto28"`
   - `"https://blog.naver.com/ranto28/"` → `"ranto28"`
   - `"https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=1"` → `None`
   - `"https://example.com/blog/post1"` → `None`
2. `list_posts` (monkeypatch로 httpx 가짜 응답):
   - JSON에서 5개 PostRef 반환 검증.
   - `title`이 URL-decoded됐는지 (`"오늘 오전 엔비디아"` 같은 한글).
   - `url`이 정확한 PostView URL인지.
3. `filter_today` (다양한 `now` 주입):
   - `now=datetime(2026, 5, 21, 10, 0, 0)`: "4시간 전", "11시간 전" → 당일. "2026. 5. 20." → 아님.
   - `now=datetime(2026, 5, 20, 10, 0, 0)`: "4시간 전", "11시간 전", "2026. 5. 20." 3개 → 당일.
   - "어제" / "3일 전" 같은 보지 못한 포맷 → 당일 아님.

## Acceptance Criteria

```bash
uv run pytest tests/test_fetch.py -q
uv run ruff check src/mer_summary/services/fetch.py tests/test_fetch.py
```

- 위 케이스 모두 통과, ruff 통과.

## 검증 절차

1. AC 실행.
2. 체크리스트:
   - `fetch.py` 안에 실제 외부 호출이 일어나는 부분은 `httpx.Client` 하나뿐인가?
   - `services/__init__.py`에서 `fetch` 모듈을 임포트 가능한가? (`from mer_summary.services import fetch`)
   - `os.environ`/`os.getenv`를 사용하지 않는가? (config는 호출자가 주입)
3. step 2 상태 업데이트:
   - 성공 → `"summary": "fetch.py에 is_naver_blog_main/list_posts/filter_today + PostRef 추가, 테스트 통과"`

## 금지사항

- 본문 추출 함수(`fetch_naver_post`, `fetch_generic`) 작성 금지. 이유: step 3 책임.
- 테스트에서 실제 `blog.naver.com` 호출 금지. 이유: 네트워크 의존성 + 속도. monkeypatch만.
- `time.sleep`, 재시도 로직 추가 금지. 이유: MVP scope 밖. 실패는 즉시 raise.
- 글로벌 `httpx.Client` 또는 모듈 레벨 캐시 금지. 이유: 테스트 격리.
