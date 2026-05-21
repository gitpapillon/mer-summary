"""Summary를 텔레그램 Bot API sendMessage로 전송. parse_mode 미사용 (plain text)."""

import httpx

from mer_summary.config import Config
from mer_summary.services.summarize import Summary

TELEGRAM_MAX_LENGTH = 4096
_TIMEOUT = 10.0
USER_AGENT = "Mozilla/5.0 (compatible; mer-summary/0.1)"


def format_message(summary: Summary) -> str:
    """Summary → 텔레그램 메시지 문자열.

    형식:
      📌 {title}

      • {bullet1}
      • {bullet2}
      ...

      🔗 {source_url}

    4096자 초과 시 끝 1자를 '…'로 치환해 절단 표시.
    """
    bullet_lines = "\n".join(f"• {b}" for b in summary.bullets)
    text = f"📌 {summary.title}\n\n{bullet_lines}\n\n🔗 {summary.source_url}"
    if len(text) > TELEGRAM_MAX_LENGTH:
        text = text[: TELEGRAM_MAX_LENGTH - 1] + "…"
    return text


def send(summary: Summary, cfg: Config) -> None:
    """Telegram Bot API sendMessage 호출. 실패 시 RuntimeError."""
    url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": cfg.telegram_chat_id,
        "text": format_message(summary),
        "disable_web_page_preview": False,
    }
    with httpx.Client(timeout=_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        r = client.post(url, json=payload)

    if r.status_code != 200:
        raise RuntimeError(
            f"telegram.send: HTTP {r.status_code}, body={r.text[:300]!r}"
        )

    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"telegram.send: ok=False, description={data.get('description')!r}"
        )
