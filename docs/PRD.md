# PRD: mer-summary

## 목표
블로그 URL 하나를 주면, 본문을 자동으로 추출·요약해 텔레그램으로 받아본다.

## 사용자
- 매일 여러 블로그/기사를 빠르게 훑고 싶은 본인(한 명).
- CLI에서 단발성으로 실행하거나, cron/스케줄러로 묶어 자동화한다.

## 핵심 기능
1. **URL 입력 분기**
   - 블로그 메인 URL (`https://blog.naver.com/{blogId}`) → 글 목록에서 **당일 작성된 글만** 추려 N개 처리.
   - 개별 게시글 URL (`PostView.naver?blogId=...&logNo=...` 또는 임의 사이트 글 URL) → 그 1개만 처리.
2. **본문 추출**
   - 네이버: `PostTitleListAsync.naver` JSON으로 메타 조회, `PostView.naver` HTML에서 `class="se-main-container"` 추출.
   - 일반 사이트: `trafilatura` 폴백.
3. **요약**: Claude API로 한국어 요약 (제목 + bullet 3–5개).
4. **전송**: 글 1개당 텔레그램 메시지 1개. 원문 링크 포함.

## MVP 제외 사항
- 여러 URL 일괄 처리 (입력은 1개 URL — 단, 그 1개가 블로그 메인이면 당일 글 N개 자동 처리).
- RSS/Atom 피드 폴링 (네이버 JSON API 1회 호출은 폴링 아님).
- 요약 이력 저장(DB) — 같은 글 중복 전송 가능.
- 웹 UI / 설정 UI — 모든 설정은 환경변수.
- 멀티 사용자 / 멀티 chat_id 분기.
- 이미지·동영상 추출.
- 재시도/큐잉 — 글 1개 실패 시 stderr 로그 후 다음 글로 진행 (전체 중단 X).

## 설계 원칙
- 작동하는 최소 구현 우선.
- 외부 의존성 최소화 (`anthropic`, `httpx`, `trafilatura`, `beautifulsoup4`, `python-dotenv` 외 추가 금지).
- 모든 실패는 명확한 에러 메시지로 표면화 (조용히 실패 X).
- 당일 글 0개면 정상 종료(exit 0) + stderr 한 줄 안내.
