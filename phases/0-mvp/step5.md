# Step 5: telegram-send

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/ARD.md` (ARD-004)
- `/src/mer_summary/config.py`
- `/src/mer_summary/services/summarize.py` (`Summary` 타입)

## 작업

`src/mer_summary/services/telegram.py` 를 만든다. `Summary`를 받아 텔레그램 Bot API `sendMessage`로 전송.

### 시그니처

```python
from mer_summary.config import Config
from mer_summary.services.summarize import Summary

TELEGRAM_MAX_LENGTH = 4096

def format_message(summary: Summary) -> str:
    """Summary를 텔레그램 메시지 문자열로 포맷.

    형식:
      📌 {title}

      • {bullet1}
      • {bullet2}
      ...

      🔗 {source_url}

    4096자 초과 시 끝을 잘라 '…' 추가.
    """
    ...

def send(summary: Summary, cfg: Config) -> None:
    """텔레그램 Bot API sendMessage 호출.

    POST https://api.telegram.org/bot{token}/sendMessage
      json={"chat_id": cfg.telegram_chat_id, "text": text, "disable_web_page_preview": False}
    응답 status_code != 200 또는 JSON.ok != True 면 RuntimeError raise.
    """
    ...
```

### 핵심 규칙

- `httpx.Client(timeout=10)` 컨텍스트 매니저로 사용.
- POST body는 `json=` 파라미터로 전달 (Content-Type: application/json 자동).
- `parse_mode`는 **사용하지 않음** (Markdown/HTML 이스케이프 골치 — plain text로 안전하게).
- 응답 검증: `r.status_code == 200` AND `r.json().get("ok") is True`. 둘 중 하나라도 위반 시 raise.
- 에러 메시지에는 응답 본문(JSON의 description 필드)을 포함해 디버깅 용이하게.
- 4096자 절단 시 끝 1자를 `…`로 치환해 잘렸음을 표시.

### 테스트 (`tests/test_telegram.py`)

`httpx.Client.post` 를 monkeypatch로 가짜화. 실제 텔레그램 호출 금지.

#### 테스트 케이스

1. `format_message`:
   - 일반 Summary → 예상 형식 (제목, bullet 줄, 링크 포함).
   - bullet 5개 모두 들어감.
2. `format_message` 절단:
   - bullet에 매우 긴 문자열 강제 주입 → 결과 길이 ≤ 4096, 끝이 `…`.
3. `send` 정상:
   - 가짜 응답 `status_code=200`, `json()={"ok": True, ...}` → 예외 없음.
   - 호출 URL이 `https://api.telegram.org/bot{TOKEN}/sendMessage` 인지 검증.
   - payload의 `chat_id`가 `cfg.telegram_chat_id`와 일치.
4. `send` 실패 — status != 200:
   - 가짜 응답 `status_code=400` → `RuntimeError`, 메시지에 응답 본문 포함.
5. `send` 실패 — `ok=False`:
   - `status_code=200` but `json()={"ok": False, "description": "chat not found"}` → `RuntimeError`, 메시지에 "chat not found" 포함.

## Acceptance Criteria

```bash
uv run pytest tests/test_telegram.py -q
uv run ruff check src/mer_summary/services/telegram.py tests/test_telegram.py
```

- 모든 케이스 통과, ruff 통과.

## 검증 절차

1. AC 실행.
2. 체크리스트:
   - 실제 `api.telegram.org` 도메인 호출이 테스트에서 일어나지 않는가? (monkeypatch 적용 확인)
   - `parse_mode` 파라미터를 사용하지 않는가?
   - `httpx.Client`가 모듈 글로벌이 아닌 함수 내부에서 with-블록으로 생성되는가?
3. step 5 상태 업데이트.

## 금지사항

- 메시지 분할 전송(2개 이상 sendMessage) 금지. 이유: ARD-004 — 4096자 절단으로 충분.
- `python-telegram-bot` 또는 다른 텔레그램 라이브러리 추가 금지. 이유: ARD-004.
- Markdown/HTML parse_mode 사용 금지. 이유: 이스케이프 함정. plain text + 이모지로 충분히 가독성 확보됨.
- 재시도 / rate-limit 백오프 추가 금지. 이유: MVP scope. 실패는 raise.
