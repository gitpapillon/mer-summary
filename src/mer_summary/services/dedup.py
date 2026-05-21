"""이미 전송한 글의 logNo를 파일로 추적해 중복 전송을 막는다.

저장 형식 (`state/sent_log.json`):
    {"sent_log_nos": ["224291989573", "224291577587", ...]}

파일이 없거나 비어있으면 빈 set으로 시작.
호출자는 (1) load → (2) 새 글 후보 필터 → (3) 전송 성공 시 add → (4) save 흐름을 따른다.
"""

import json
from pathlib import Path


def load_sent(state_file: Path) -> set[str]:
    """파일에서 전송 이력 set 로드. 파일 없으면 빈 set."""
    if not state_file.exists():
        return set()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"sent_log 파일 파싱 실패: {state_file}: {e}") from e
    nos = data.get("sent_log_nos", [])
    if not isinstance(nos, list):
        raise RuntimeError(
            f"sent_log 형식 위반(list 아님): {state_file}: {type(nos).__name__}"
        )
    return set(str(x) for x in nos)


def save_sent(state_file: Path, sent: set[str]) -> None:
    """전송 이력 set을 파일로 저장. 디렉토리가 없으면 만든다.

    저장 순서는 정렬해서 git diff가 안정적으로 나오게 한다.
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {"sent_log_nos": sorted(sent)},
        ensure_ascii=False,
        indent=2,
    )
    state_file.write_text(body + "\n", encoding="utf-8")
