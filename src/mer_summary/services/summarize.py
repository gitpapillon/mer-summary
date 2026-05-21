"""Anthropic Claude Haiku 4.5로 ArticleText를 요약 → Summary.

system 프롬프트에 prompt caching 적용 (반복 호출 시 비용 절감).
응답은 JSON 단일 객체만 수용; 형식 위반은 RuntimeError.
"""

import json
from dataclasses import dataclass

import anthropic

from mer_summary.config import Config
from mer_summary.services.fetch import ArticleText

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024

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


@dataclass(frozen=True)
class Summary:
    source_url: str
    title: str
    bullets: list[str]


def _extract_json_object(text: str) -> str:
    """LLM 응답에서 JSON 객체 영역만 추출. 코드펜스/설명 prefix가 있어도 흡수.

    첫 '{' 부터 마지막 '}' 까지를 잘라낸다. 둘 다 없으면 빈 문자열 반환 →
    json.loads가 적절한 에러를 낼 것.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1]


def summarize(article: ArticleText, cfg: Config) -> Summary:
    """ArticleText → Summary. Anthropic API 호출."""
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    user_text = f"제목: {article.title}\n\n본문:\n{article.body}"

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )

    raw = message.content[0].text if message.content else ""
    json_str = _extract_json_object(raw)
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"summarize: 응답이 JSON 아님: {raw[:200]!r}"
        ) from e

    if not isinstance(parsed, dict):
        raise RuntimeError(f"summarize: JSON이 객체 아님: {parsed!r}")

    title = parsed.get("title")
    bullets = parsed.get("bullets")
    if not isinstance(title, str) or not title.strip():
        raise RuntimeError(f"summarize: title 누락/비었음: {parsed!r}")
    if not isinstance(bullets, list) or not (3 <= len(bullets) <= 5):
        raise RuntimeError(
            f"summarize: bullets는 3-5개 list여야 함, 받은 값: {bullets!r}"
        )
    if not all(isinstance(b, str) and b.strip() for b in bullets):
        raise RuntimeError(f"summarize: bullets 항목이 비었거나 문자열 아님: {bullets!r}")

    return Summary(source_url=article.url, title=title.strip(), bullets=bullets)
