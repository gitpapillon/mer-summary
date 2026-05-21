# mer-summary

블로그 게시글 URL을 받아 본문을 추출하고 Claude로 요약한 뒤 텔레그램으로 전송하는 CLI.

```bash
uv sync
cp .env.example .env       # ANTHROPIC_API_KEY / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 채우기
uv run mer-summary https://example.com/post/123
```

## 문서
- `CLAUDE.md` — 프로젝트 규칙 (스택, 아키텍처, 개발 프로세스)
- `docs/PRD.md` — 목표/사용자/핵심 기능/MVP 제외
- `docs/ARCHITECTURE.md` — 디렉토리·데이터 흐름·패턴
- `docs/ARD.md` — 핵심 아키텍처 결정과 이유

## 자동화 (GitHub Actions)
`.github/workflows/daily-summary.yml`이 매시간 자동 실행해 메르(ranto28) 블로그 카테고리 **21(경제)** + **28(IT/투자)** 신규 글을 텔레그램으로 전송한다. 이미 보낸 글은 `state/sent_log.json` 기반으로 스킵.

**시크릿 등록** (repo Settings → Secrets and variables → Actions):
```
ANTHROPIC_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

수동 실행: Actions 탭 → `daily-summary` → "Run workflow".

## 개발 워크플로우
이 프로젝트는 `harness` 스켈레톤 기반이다. 새 task는 `/harness` 슬래시 명령으로 step 분해 후 진행한다.

## 환경변수
| 변수 | 용도 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 호출 |
| `TELEGRAM_BOT_TOKEN` | @BotFather 발급 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 메시지 수신 대상 chat id |
