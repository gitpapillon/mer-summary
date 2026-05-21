"""CLI 진입점. services를 조합만 한다 — 비즈니스 로직은 services 안에."""

import argparse
import sys
from datetime import datetime

from mer_summary.config import Config, load_config
from mer_summary.services import fetch, summarize, telegram


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mer-summary",
        description="블로그 URL을 받아 본문을 추출·요약해 텔레그램으로 전송.",
        epilog=(
            "예시:\n"
            "  mer-summary https://blog.naver.com/ranto28\n"
            "  mer-summary https://blog.naver.com/PostView.naver?blogId=ranto28&logNo=224291989573\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="블로그 메인 URL 또는 개별 게시글 URL")
    parser.add_argument(
        "--now",
        type=datetime.fromisoformat,
        default=None,
        help='ISO8601 (예: "2026-05-21T10:00:00"). 당일 필터 기준 시각. 미지정 시 datetime.now().',
    )
    return parser.parse_args(argv)


def _process_one(url: str, cfg: Config) -> bool:
    """URL 1개 처리. 성공 True, 실패 False(stderr 로그)."""
    try:
        article = fetch.fetch_article(url)
        smry = summarize.summarize(article, cfg)
        telegram.send(smry, cfg)
        return True
    except RuntimeError as e:
        print(f"[skip] {url}: {e}", file=sys.stderr)
        return False


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        cfg = load_config()
    except RuntimeError as e:
        print(f"[config] {e}", file=sys.stderr)
        return 2

    now = args.now or datetime.now()
    main_match = fetch.is_naver_blog_main(args.url)

    if main_match is None:
        ok = _process_one(args.url, cfg)
        return 0 if ok else 1

    blog_id, category_no = main_match
    # 네이버 블로그 메인 — 당일 글 N개 순회
    try:
        refs = fetch.list_posts(blog_id, category_no=category_no)
    except RuntimeError as e:
        print(f"[list] {args.url}: {e}", file=sys.stderr)
        return 1

    today_refs = fetch.filter_today(refs, now)
    if not today_refs:
        print("당일 작성된 글이 없습니다.", file=sys.stderr)
        return 0

    print(f"[info] 당일 글 {len(today_refs)}개 처리 시작", file=sys.stderr)
    any_failed = False
    for ref in today_refs:
        if not _process_one(ref.url, cfg):
            any_failed = True
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
