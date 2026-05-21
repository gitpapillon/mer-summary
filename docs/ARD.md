# Architecture Decision Records (ARD)

## 철학
MVP 속도 + 외부 의존성 최소화. 한 가지 일을 잘 하는 CLI. 모든 결정은 "가장 단순한 작동 버전"으로 회귀.

---

### ARD-001: Python 3.12 + uv 패키지 매니저
**결정**: Python 3.12, `uv`로 의존성/실행 관리. `pyproject.toml`만 사용.
**이유**: dailycast와 동일 스택 — 학습 비용 0. uv는 venv 자동 + pip보다 훨씬 빠름.
**트레이드오프**: uv는 비교적 신생 도구 — Windows에서 가끔 깔리는 위치가 다름. 대안은 venv + pip. 사용자 시스템에 uv가 없으면 Step 0에서 설치 안내.

### ARD-002: 본문 추출 — 사이트별 라우팅 (네이버 BS4 우선, 일반은 trafilatura 폴백)
**결정**:
- 네이버 블로그 (`blog.naver.com` 도메인): `PostView.naver` HTML에서 `class="se-main-container"` 컨테이너를 `beautifulsoup4`로 직접 추출.
- 그 외 일반 사이트: `trafilatura.extract()`로 본문 텍스트 추출.
**이유**: 네이버는 iframe 셸 + 스마트에디터 구조라 trafilatura가 자주 실패. se-main-container는 안정적 셀렉터. 일반 사이트는 trafilatura가 광고/메뉴를 잘 거름.
**트레이드오프**: 네이버 셀렉터가 바뀌면 어댑터 수정 필요 (안정적이긴 함). 일부 SPA/JS 렌더 사이트는 trafilatura도 실패 — MVP에선 명시적 에러로 종료.

### ARD-003: 요약 엔진은 Anthropic SDK + Claude Haiku 4.5
**결정**: `anthropic` 파이썬 SDK로 `claude-haiku-4-5-20251001` 호출. 시스템 프롬프트(요약 지침)에 prompt caching 적용.
**이유**: 한국어 요약 품질 좋고, Haiku 비용/속도가 단발 CLI에 최적. dailycast에서 이미 검증.
**트레이드오프**: API 키와 네트워크 필수. 오프라인/로컬 LLM은 안 씀. 비용은 글 1편당 수 원 수준이라 무시 가능.

### ARD-004: 텔레그램은 Bot API 직접 호출 (httpx)
**결정**: `python-telegram-bot` 라이브러리 안 씀. `httpx.post("https://api.telegram.org/bot{token}/sendMessage", ...)` 한 번이면 끝.
**이유**: 메시지 1개 보내는 데 풀-피처 라이브러리는 과함. 의존성/유지보수 감소.
**트레이드오프**: 메시지 분할(>4096자)·미디어 첨부 같은 기능이 필요해지면 직접 짜야 함. 4096자 초과 시 끝을 잘라서 보냄(`…` 표시).

### ARD-005: 입력은 CLI URL 1개 이상 — 네이버 메인이면 카테고리별로 N개 자동 처리
**결정**: `mer-summary <URL> [<URL>...]` 형태. URL을 한 개 이상 받고 순서대로 처리.
- 네이버 블로그 메인 패턴 감지 시 당일 글 모두를 자동 순회 처리. 허용 패턴:
  - `https://blog.naver.com/{blogId}` (PC 도메인, path-based)
  - `https://m.blog.naver.com/{blogId}` (모바일 도메인)
  - `https://blog.naver.com/PostList.naver?blogId={id}` (글 목록 페이지, query-based)
  - 위 모두 + `?categoryNo={N}` 쿼리 → 해당 카테고리만 조회.
- 그 외 URL: 그 1개만 처리 (`fetch_article` 라우터).
- 한 URL 처리 실패가 나머지 URL을 막지 않음(부분 실패 정책 = ARD-008과 동일).
**이유**: 사용 시나리오가 "이 블로그의 카테고리 21 + 28 동시에 보내줘" 같은 다중 카테고리 시청. 외부 셸 루프 없이 한 번 실행에 해결. PostList.naver는 네이버 PC 웹의 글 목록 페이지 형식이라 자주 복붙됨 → 직접 인식 지원.
**트레이드오프**: argparse `nargs='+'`로 한 자리수 URL은 자연스럽지만, 수십~수백 개라면 stdin 입력/파일이 필요. MVP에서는 N≤10 가정.

### ARD-006: 비밀값은 환경변수 + python-dotenv
**결정**: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 환경변수로. 로컬에선 `.env` 자동 로드.
**이유**: 표준 방식, cron/CI 어디서나 동일. `.env`는 `.gitignore`로 막아 유출 방지.
**트레이드오프**: 시크릿 관리자(1Password, Vault) 연동은 없음. 1인 사용이라 불필요.

### ARD-007: 네이버 블로그 어댑터 — JSON API + se-main-container
**결정**:
- 글 목록: `https://blog.naver.com/PostTitleListAsync.naver?blogId={id}&currentPage=1&countPerPage=30` — **JSON 반환**, `postList[]`에 `logNo`/`title`(URL-encoded)/`addDate` 포함.
- 본문 URL: `https://blog.naver.com/PostView.naver?blogId={id}&logNo={logNo}`.
- 본문 추출: `BeautifulSoup` + `soup.select_one("div.se-main-container").get_text(separator="\n", strip=True)`.
- HTTP 요청은 모두 User-Agent 헤더 필수 (없으면 차단).
**이유**: HTML 파싱보다 JSON 파싱이 안정적이고 가볍다. iframe 우회 불필요. UA만 있으면 인증·쿠키 없이 200 OK 검증됨.
**트레이드오프**: 네이버 내부 엔드포인트라 사전 공지 없이 사라질 수 있음 — 그때는 RSS(`rss.naver.com`)나 외부 어댑터로 교체.

### ARD-008: 당일 글 0개·일부 실패 처리 정책
**결정**:
- 글 목록 → 시간 필터 결과 0개 / dedup 후 0개: 정상 종료 (exit 0), stderr에 "새로 전송할 글이 없습니다." 한 줄.
- N개 글 처리 중 일부 실패 (fetch/summarize/send 어느 단계든): 그 글만 스킵하고 stderr 로그, 다음 글 진행. 전체 종료 코드는 모두 성공 시 0, 일부라도 실패 시 1.
- 시간 필터(`filter_recent_days(days=N)`) 규칙:
  - `"X분 전"` / `"X시간 전"`: 항상 포함 (오늘로 간주).
  - `"YYYY. M. D."`: `now.date() - (days-1)` 이상이면 포함.
  - 그 외 포맷: 제외 (보수적).
- 자동화 기본값: `--days 2` (어제+오늘) — 자정 직전 글 누락 방지.
**이유**: cron 자동 실행을 가정 — 텔레그램 알림이 "0개네요" 한 줄로 가는 것보다 침묵이 낫다. 부분 실패가 전체를 죽이면 가장 중요한 글을 못 받는다.
**트레이드오프**: 알림 미수신 시 사용자가 "왜 안 옴?"을 판단할 단서가 stderr 로그뿐 — Actions 실행 결과 페이지에서 로그 확인 가능.

### ARD-009: 중복 전송 방지(dedup) — sent_log.json + GitHub Actions
**결정**:
- 전송 성공한 글의 `logNo`를 `state/sent_log.json`에 누적 저장. 형식: `{"sent_log_nos": ["...", ...]}` (sorted).
- 실행 시: `list_posts` → `filter_recent_days(days=2)` → `sent_log`에 없는 logNo만 전송 → 성공한 logNo를 `sent_log`에 추가.
- 자동화는 **GitHub Actions schedule(매시간)** — repo에 `.github/workflows/daily-summary.yml`. 새 글 있을 때만 `[bot]`이 `state/sent_log.json` 변경분을 자동 commit + push.
- 시크릿은 GitHub repo Secrets에 보관 (`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
**이유**: 네이버 블로그는 push 알림 없음 → 폴링만 가능. 매시간 체크는 비용 미미(새 글 없으면 Anthropic 호출 0건). repo에 sent_log 저장하면 실행 환경(컨테이너) 격리에 영향 없고 git history로 추적 가능.
**트레이드오프**: 매시간 GitHub Actions 분 소모(무료 한도 내, public repo는 무제한). sent_log가 무한 누적되지만 logNo 13자×N → 메르 패턴(~6글/일×365일)으로 연 ~30KB 수준이라 무시 가능. 외부 시크릿 관리자 미사용.
