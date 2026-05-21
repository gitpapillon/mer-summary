"""환경변수 로드 + 검증. 다른 모듈은 Config 인스턴스만 받고 os.environ 직접 접근 금지."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

_REQUIRED = ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str


def load_config() -> Config:
    """환경변수에서 Config 로드. .env가 있으면 자동 로드.

    빈 문자열도 누락으로 간주. 누락 변수는 RuntimeError 메시지에 모두 나열한다.
    """
    load_dotenv()
    values = {name: (os.getenv(name) or None) for name in _REQUIRED}
    missing = [name for name, v in values.items() if v is None]
    if missing:
        raise RuntimeError(
            f"필수 환경변수 누락: {', '.join(missing)}. .env 파일을 확인하세요."
        )
    return Config(
        anthropic_api_key=values["ANTHROPIC_API_KEY"],
        telegram_bot_token=values["TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=values["TELEGRAM_CHAT_ID"],
    )
