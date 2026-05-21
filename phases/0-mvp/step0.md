# Step 0: project-setup

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/CLAUDE.md`
- `/docs/PRD.md`
- `/docs/ARCHITECTURE.md`
- `/docs/ARD.md`
- `/pyproject.toml`

## 사전 준비 (사용자 시스템 점검)

이 step은 의존성 설치와 패키지 트리 생성을 한다. 실행 환경에 `uv`가 없으면 사용자가 설치해야 한다.

```bash
uv --version  # 없으면 아래 안내
```

`uv`가 없으면 다음 안내를 stderr에 출력하고 `status="blocked"`로 표시한 뒤 종료한다:

```
uv가 설치되어 있지 않습니다. 다음 중 하나로 설치하세요:
  Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh
  Windows:     winget install --id=astral-sh.uv  (또는 scoop install uv)
설치 후 'phases/0-mvp/index.json'에서 이 step의 status를 'pending'으로 바꾸고 재실행.
```

`blocked_reason`: "uv 미설치 — 사용자 설치 필요"

## 작업

`uv`가 있다면:

1. **의존성 설치 및 lock**
   ```bash
   uv sync
   ```
   `uv.lock` 파일이 생성된다.

2. **패키지 트리 생성** — `src/mer_summary/` 안에 다음 파일이 이미 있으나, `services/` 서브패키지는 없을 수 있다. 없으면 생성:
   - `src/mer_summary/services/__init__.py` (빈 파일 또는 한 줄 docstring)

3. **테스트 트리 생성**
   - `tests/__init__.py` (빈 파일)
   - `tests/conftest.py` — pytest 공통 픽스처용 빈 파일 (현재는 빈 파일이어도 됨)

4. **검증**: `uv run pytest --collect-only -q` 가 0개 테스트 수집으로 정상 종료해야 한다 (`tests/` 디렉토리 인식 확인용).

## Acceptance Criteria

```bash
uv sync
uv run ruff check .
uv run pytest --collect-only -q
```

- `uv sync` 가 성공한다 (`uv.lock` 생성됨).
- `ruff check .` 가 에러 없이 통과한다.
- `pytest --collect-only` 가 종료 코드 5(no tests collected)로 끝나거나 0으로 끝난다. 다른 코드면 실패.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트:
   - `pyproject.toml`의 의존성 목록이 변경되지 않았는가? (이 step에서 추가/삭제 금지)
   - 디렉토리 구조가 ARCHITECTURE.md와 일치하는가?
3. `phases/0-mvp/index.json`의 step 0 상태 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "uv sync 완료, services/ + tests/ 패키지 트리 생성"`
   - uv 미설치 → `"status": "blocked"`, `"blocked_reason": "uv 미설치 — 사용자 설치 필요"`
   - 그 외 실패 → `"status": "error"`, `"error_message": "<구체 메시지>"`

## 금지사항

- 실제 코드(config.py, services/*.py 등) 작성 금지. 이 step은 셋업만. 이유: scope 최소화 + 후속 step에서 TDD로 만든다.
- `pyproject.toml`의 의존성 변경 금지. 이유: ARD에서 확정된 의존성 목록. 변경 필요 시 ARD 업데이트 후 별도 step으로.
- 기존 파일(`CLAUDE.md`, `README.md`, `.env.example`, `docs/*`) 수정 금지. 이유: 이 step의 책임 밖.
