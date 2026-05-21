# Step 4: summarize

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/ARCHITECTURE.md` (타입 섹션)
- `/docs/ARD.md` (ARD-003)
- `/src/mer_summary/config.py`
- `/src/mer_summary/services/fetch.py` (`ArticleText` 타입 사용)

## 작업

`src/mer_summary/services/summarize.py` 를 만든다. Anthropic SDK로 Claude Haiku 4.5를 호출해 본문을 요약.

### 타입 정의

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Summary:
    source_url: str
    title: str
    bullets: list[str]   # 3-5개 권장
```

### 시그니처

```python
from mer_summary.config import Config
from mer_summary.services.fetch import ArticleText

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """당신은 한국어 블로그 글을 빠르게 요약하는 도우미입니다.
출력은 반드시 JSON 한 개 객체로만 작성하세요. 다른 설명, 마크다운, 코드펜스 금지.

스키마:
{
  "title": "원문 제목 또는 한 줄 요약 제목 (한국어)",
  "bullets": ["핵심 포인트 1", "핵심 포인트 2", "...3-5개"]
}

규칙:
- bullet은 3-5개. 너무 짧으면 의미 없고, 너무 길면 읽기 부담.
- 각 bullet은 한국어 한 문장, 80자 이내.
- 의견·해석은 빼고 글이 말한 사실/주장만 추출.
- 숫자·고유명사는 그대로 보존.
"""

def summarize(article: ArticleText, cfg: Config) -> Summary:
    """ArticleText를 Anthropic API로 요약해 Summary 반환.

    - 모델: claude-haiku-4-5-20251001
    - max_tokens: 1024
    - system 프롬프트에 cache_control 적용 (prompt caching)
    - user 메시지: "제목: {title}\\n\\n본문:\\n{body}"
    - 응답: JSON 문자열을 파싱해 Summary 조립
    실패 시 RuntimeError (네트워크/JSON 파싱/스키마 위반).
    """
    ...
```

### 핵심 규칙

- `anthropic.Anthropic(api_key=cfg.anthropic_api_key)` 로 클라이언트 생성 (모듈 레벨 X, 함수 내부에서).
- `client.messages.create(...)` 호출 시 `system` 파라미터에 prompt caching 적용:
  ```python
  system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
  ```
- 응답 `message.content[0].text` 를 `json.loads` 로 파싱. 실패 시 RuntimeError에 응답 일부 포함.
- 파싱된 JSON이 `title` (str) + `bullets` (list[str], 3-5개) 형태인지 검증. 위반 시 RuntimeError.
- `Summary.source_url = article.url`, `Summary.title`은 LLM 응답의 title 사용 (article.title 무시 — LLM이 더 요약된 제목을 줄 수 있음).
- 본문이 너무 길면 (예: 30000자 초과) 앞부분만 보내도 됨 (선택). 안 잘라도 Haiku는 200k 컨텍스트라 보통 문제 없음.

### 테스트 (`tests/test_summarize.py`)

`anthropic.Anthropic` 또는 `client.messages.create` 를 monkeypatch로 가짜화. 실제 API 호출 금지.

#### 가짜 응답 객체

`client.messages.create`가 반환할 가짜 객체:
```python
class FakeMessage:
    class Content:
        text = '{"title": "엔비디아 실적 요약", "bullets": ["매출 816억 달러", "데이터센터 752억", "전년대비 +85%"]}'
    content = [Content()]
```

#### 테스트 케이스

1. 정상 케이스: `summarize(article, cfg)` → `Summary(source_url=article.url, title="엔비디아 실적 요약", bullets=[3개])`.
2. 응답이 JSON 아님 (예: `"여기 요약입니다: ..."`): `RuntimeError`.
3. JSON이지만 스키마 위반 (예: `{"title": "x"}` — bullets 없음): `RuntimeError`.
4. bullets가 2개 (3개 미만): `RuntimeError`.
5. API 호출 시 모델 ID가 `claude-haiku-4-5-20251001` 인지 검증 (monkeypatch에서 호출 인자 캡처).
6. system 파라미터에 `cache_control` 포함됐는지 검증.

## Acceptance Criteria

```bash
uv run pytest tests/test_summarize.py -q
uv run ruff check src/mer_summary/services/summarize.py tests/test_summarize.py
```

- 6개 케이스 통과, ruff 통과.

## 검증 절차

1. AC 실행.
2. 체크리스트:
   - `MODEL` 상수가 `"claude-haiku-4-5-20251001"` 인가?
   - 모듈 임포트 시점에 `anthropic.Anthropic()` 인스턴스화 안 되는가? (`grep -n "Anthropic(" src/mer_summary/services/summarize.py` 로 확인 — 함수 내부에만 있어야 함)
   - `os.environ`/`os.getenv` 직접 호출이 없는가? (`Config`를 통해서만)
3. step 4 상태 업데이트.

## 금지사항

- 모델을 Sonnet/Opus로 바꾸지 마라. 이유: ARD-003 결정. 비용/속도 균형이 Haiku에 맞춰져 있음.
- 응답 형식을 plain text나 markdown으로 받지 마라. 이유: 파싱 안정성. JSON만.
- 재시도 로직 추가 금지. 이유: MVP scope. 실패는 raise.
- 실제 ANTHROPIC_API_KEY로 테스트 호출 금지. 이유: 비용/속도/CI 안정성.
