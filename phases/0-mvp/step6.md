# Step 6: cli-orchestration

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/PRD.md` (핵심 기능 #1 — URL 분기)
- `/docs/ARCHITECTURE.md` (데이터 흐름)
- `/docs/ARD.md` (특히 ARD-005, ARD-008)
- `/src/mer_summary/__main__.py` (현재 placeholder)
- `/src/mer_summary/config.py`
- `/src/mer_summary/services/fetch.py`
- `/src/mer_summary/services/summarize.py`
- `/src/mer_summary/services/telegram.py`

## 작업

`src/mer_summary/__main__.py` 를 재작성한다. 이 step은 **앞 step들이 만든 모듈을 조합만** 한다 — 새 비즈니스 로직 없음.

### 시그니처

```python
import argparse
import sys
from datetime import datetime

from mer_summary.config import load_config
from mer_summary.services import fetch, summarize, telegram


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """argparse: 위치 인자 url 1개. --now ISO8601 (테스트용, 기본은 datetime.now())."""
    ...


def process_one(url: str, cfg, *, log) -> bool:
    """URL 1개를 처리. 성공이면 True, 실패면 stderr 로그 후 False."""
    article = fetch.fetch_article(url)
    summary = summarize.summarize(article, cfg)
    telegram.send(summary, cfg)
    return True
    # 위 라인들을 try/except로 감싸 RuntimeError 만 잡고 stderr 로그 후 False.


def main(argv: list[str] | None = None) -> int:
    """엔트리포인트.

    1. parse_args
    2. load_config (실패 시 stderr + return 2)
    3. is_naver_blog_main(url) 검사:
       - blogId면: list_posts → filter_today(now) → 결과 0개면 안내 후 return 0,
         아니면 각 PostRef.url을 process_one에 넘김.
       - None이면: process_one(url, cfg)만.
    4. 종료 코드:
       - 모든 process_one이 True 또는 빈 목록 → 0
       - 어느 하나라도 False → 1
       - 설정 오류 → 2
    """
    ...


if __name__ == "__main__":
    sys.exit(main())
```

### 핵심 규칙

- `process_one`은 `RuntimeError`만 catch (예상 가능한 실패). 그 외 예외는 그대로 propagate (버그라는 신호).
- stderr 로그 포맷: `f"[skip] {url}: {error}"` — 짧고 grep-able.
- 당일 글 0개 안내: `print("당일 작성된 글이 없습니다.", file=sys.stderr)` 후 return 0.
- 처리 시작 안내(선택): `print(f"[info] 당일 글 {N}개 처리 시작", file=sys.stderr)` — 진행 가시성.
- `--now` 인자는 ISO8601 (`2026-05-21T10:00:00`) 만 받음. 파싱 실패 시 argparse가 알아서 에러.
- argparse 도움말 (`-h`)에 사용 예시 2개:
  ```
  mer-summary https://blog.naver.com/ranto28
  mer-summary https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=224291989573
  ```

### 테스트 (`tests/test_main.py`)

모든 외부 호출(fetch/summarize/telegram)을 monkeypatch로 가짜화. `Config`도 더미 값으로 주입.

#### 테스트 케이스

1. **개별 글 URL 흐름**:
   - URL: `https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=1`
   - `fetch.fetch_article` 가 1회 호출, `summarize`, `telegram.send` 각 1회 호출.
   - `fetch.list_posts` 는 호출되지 않음.
   - 종료 코드 0.
2. **블로그 메인 URL — 당일 3개**:
   - URL: `https://blog.naver.com/ranto28`
   - `list_posts` 가 5개 반환, `filter_today` 가 3개 반환되도록 monkeypatch.
   - `fetch_article`/`summarize`/`telegram.send`가 각각 3번 호출.
   - 종료 코드 0.
3. **블로그 메인 — 당일 0개**:
   - `filter_today`가 빈 리스트 → process_one 호출 0회, 종료 코드 0, stderr에 "당일 작성된 글이 없습니다." 포함.
4. **부분 실패**:
   - 3개 글 중 2번째가 RuntimeError → 1, 3번째는 정상 처리됨, stderr에 `[skip]` 포함, 종료 코드 1.
5. **load_config 실패**:
   - monkeypatch로 `load_config`가 RuntimeError → stderr에 메시지, 종료 코드 2.
6. **`--now` 주입**:
   - `--now 2026-05-21T10:00:00` 가 `filter_today`에 전달되는지 검증 (monkeypatch에서 인자 캡처).

## Acceptance Criteria

```bash
uv run pytest -q                  # 전체 테스트 통과 (이전 step 포함)
uv run ruff check .               # 전체 ruff 통과
uv run mer-summary --help         # 도움말 정상 출력
```

- 모든 step의 테스트가 깨지지 않고 통과.
- `--help` 출력에 위 사용 예시 2개 포함.

## 검증 절차

1. AC 실행.
2. 체크리스트:
   - `__main__.py`에서 외부 라이브러리(`anthropic`, `httpx`, `bs4`, `trafilatura`) 직접 임포트가 없는가? 모두 `services.*` 통해서만.
   - `__main__.py` 라인 수가 100줄 이내인가? (조합만 하면 짧아야 함)
   - 종료 코드 규칙 (0 / 1 / 2)이 ARD-008과 일치하는가?
3. step 6 상태 업데이트.
4. `phases/index.json` 의 `0-mvp` status를 `completed`로 (execute.py가 자동 처리하면 패스, 수동이면 직접).

## 금지사항

- `__main__.py`에 비즈니스 로직(파싱, HTML 추출, API 호출) 작성 금지. 이유: 레이어 분리. 모두 services로 위임.
- 글로벌 mutable 상태 사용 금지. 이유: 테스트 격리.
- 환경변수 직접 접근 금지 — `load_config()`만. 이유: CLAUDE.md CRITICAL.
- `print(..., file=sys.stdout)` 사용 금지 — 사용자 출력은 stderr 또는 텔레그램으로만. 이유: 사용자가 "테레그램만" 선택. stdout이 비어야 파이프라인 친화적.
