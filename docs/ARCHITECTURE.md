# 아키텍처

## 디렉토리 구조
```
mer-summary/
├── src/
│   └── mer_summary/
│       ├── __init__.py
│       ├── __main__.py         # CLI 진입점 (argparse + 오케스트레이션)
│       ├── config.py           # 환경변수 로드 + 검증 (frozen dataclass)
│       └── services/
│           ├── __init__.py
│           ├── fetch.py        # URL → 본문 텍스트 (trafilatura)
│           ├── summarize.py    # 본문 → Summary (Anthropic SDK)
│           └── telegram.py     # Summary → Telegram Bot API 전송 (httpx)
├── tests/
│   ├── test_fetch.py
│   ├── test_summarize.py
│   └── test_telegram.py
├── docs/                       # PRD / ARCHITECTURE / ARD
├── phases/                     # /harness step 산출물
├── pyproject.toml
├── .env.example
└── CLAUDE.md
```

## 패턴
- **레이어 분리**: `__main__`은 CLI 파싱·오케스트레이션만, 실제 외부 호출은 `services/` 모듈이 담당.
- **순수 함수 + 얇은 어댑터**: 각 service는 `fn(input) -> output` 시그니처로 입력/출력이 명확. 부수효과(네트워크 호출)는 함수 경계에서 마무리.
- **설정은 한 곳에서**: `config.py`가 환경변수를 읽어 frozen dataclass(`Config`)로 반환. 다른 모듈은 dataclass만 받음 — `os.environ` 직접 접근 금지.

## 데이터 흐름
```
CLI 인자 (URL)
  → config.load() → Config { anthropic_api_key, telegram_bot_token, telegram_chat_id }
  → URL 분기:
     ┌─ blog.naver.com/{blogId} (메인) → fetch.list_posts → filter_today → [PostRef, ...]
     │      └─ 각 PostRef: fetch.fetch_naver_post → ArticleText
     └─ 그 외 URL → fetch.fetch_generic (trafilatura) → ArticleText
  → 각 ArticleText마다:
     summarize.run(article, cfg) → Summary { title, bullets[], source_url }
     telegram.send(summary, cfg) → None  (실패 시 raise → 해당 글만 스킵)
```

## 타입 (`config.py` 또는 `types.py`)
- `Config` (frozen dataclass): anthropic_api_key, telegram_bot_token, telegram_chat_id
- `PostRef`: url, title, posted_at(addDate 원문 텍스트), is_today(bool)
- `ArticleText`: url, title, body
- `Summary`: source_url, title, bullets: list[str]

## 상태 관리
- 상태 없음. 1회 실행 후 종료.
- 실패 시 비-0 종료 코드 + stderr에 사람이 읽을 수 있는 메시지.
