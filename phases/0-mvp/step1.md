# Step 1: config

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/ARCHITECTURE.md` (특히 "타입" 섹션)
- `/docs/ARD.md` (ARD-006)
- `/.env.example`
- `/src/mer_summary/__init__.py`

이전 step에서 만들어진 `tests/` 트리도 확인하라.

## 작업

`src/mer_summary/config.py` 를 만든다. 환경변수를 읽어 frozen dataclass `Config`로 반환하는 모듈.

### 시그니처

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str

def load_config() -> Config:
    """환경변수에서 Config 로드. .env 자동 로드.

    누락된 변수가 있으면 RuntimeError를 raise한다.
    메시지에는 어떤 변수가 누락됐는지 콤마 구분으로 모두 나열한다.
    """
    ...
```

### 핵심 규칙

- `python-dotenv`의 `load_dotenv()`를 함수 시작에서 호출 (이미 환경에 로드돼 있으면 no-op).
- 빈 문자열은 "누락"으로 간주한다 (`os.getenv(...) or None` 패턴 사용).
- 누락 환경변수 메시지 예시:
  > `필수 환경변수 누락: ANTHROPIC_API_KEY, TELEGRAM_CHAT_ID. .env 파일을 확인하세요.`
- `Config`는 frozen이므로 호출자가 실수로 수정 불가.

### 테스트 (`tests/test_config.py`)

`monkeypatch.setenv` / `monkeypatch.delenv`로 각 케이스 검증:

1. 세 변수 모두 설정 시: `load_config()` 가 정확한 값을 가진 `Config` 반환.
2. `ANTHROPIC_API_KEY` 누락: `RuntimeError`, 메시지에 "ANTHROPIC_API_KEY" 포함.
3. 모두 누락: 메시지에 세 변수명 모두 포함.
4. 빈 문자열도 누락 처리: `monkeypatch.setenv("ANTHROPIC_API_KEY", "")` 시 RuntimeError.

테스트에서 `.env` 파일 실제 로드를 막으려면 `monkeypatch.chdir(tmp_path)` 사용 가능.

## Acceptance Criteria

```bash
uv run pytest tests/test_config.py -q
uv run ruff check src/mer_summary/config.py tests/test_config.py
```

- 4개 테스트 모두 통과.
- ruff 통과.

## 검증 절차

1. 위 AC 커맨드 실행.
2. 체크리스트:
   - `Config`가 `@dataclass(frozen=True)` 인가?
   - `os.environ` / `os.getenv` 가 `config.py` 외 다른 파일에 등장하지 않는가? (`grep -r "os.getenv\|os.environ" src/` 로 확인 — config.py만 매칭돼야 함)
3. `phases/0-mvp/index.json`의 step 1 상태 업데이트:
   - 성공 → `"summary": "config.py + 4개 테스트 통과"`
   - 실패 → `error_message` 구체적으로

## 금지사항

- `config.py` 외 다른 모듈을 만들지 마라. 이유: scope 최소화.
- `Config`에 필드 추가 금지 (anthropic_api_key, telegram_bot_token, telegram_chat_id 3개만). 이유: ARCHITECTURE.md 타입 정의 준수.
- 기본값(default) 제공 금지. 이유: 누락은 명시적 실패로 다뤄야 함 (조용한 실패 금지).
- `load_dotenv()`를 모듈 import 시점에 실행 금지 — `load_config()` 함수 안에서만 호출. 이유: 테스트 격리.
