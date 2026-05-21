# 프로젝트: mer-summary

블로그 게시글 URL을 받아 본문을 추출하고 Claude로 요약한 뒤 텔레그램으로 전송하는 CLI.

## 기술 스택
- Python 3.12 + uv (패키지/실행)
- 본문 추출: `trafilatura`
- 요약: Anthropic SDK (`claude-haiku-4-5`)
- 텔레그램: Bot API 직접 호출 (`httpx`)
- 패키지 레이아웃: `src/mer_summary/`

## 아키텍처 규칙
- CRITICAL: 외부 API 호출(Anthropic, Telegram, HTTP fetch)은 `src/mer_summary/services/` 안에서만 한다. CLI 진입점(`__main__.py`)은 services를 조합만 한다.
- CRITICAL: 비밀값(API 키, 봇 토큰, chat_id)은 환경변수로만 읽는다. 코드/커밋에 절대 하드코딩 금지. `.env.example`을 항상 최신으로 유지.
- 서비스 모듈은 책임 단위로 분리: `services/fetch.py` (URL → 본문), `services/summarize.py` (본문 → 요약), `services/telegram.py` (요약 → 전송).
- 의존성은 `pyproject.toml`에만 명시. `requirements.txt` 만들지 않음.

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD).
- 외부 API는 테스트에서 monkeypatch / 가짜 응답 주입으로 처리. 실제 네트워크 호출 금지.
- 커밋 메시지는 conventional commits 형식 (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- 큰 변경은 `phases/{task}/step{N}.md` 단위로 쪼개서 진행 (`/harness` 명령 참고).

## 명령어
```
uv sync                       # 의존성 설치
uv run mer-summary <URL>      # 실행
uv run pytest -q              # 테스트
uv run ruff check .           # 린트
```
