"""CLI 진입점. services를 조합만 한다 — 비즈니스 로직은 services 안에."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from mer_summary.config import Config, load_config
from mer_summary.services import dedup, fetch, summarize, telegram

DEFAULT_STATE_FILE = Path("state/sent_log.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mer-summary",
        description="블로그 URL을 받아 본문을 추출·요약해 텔레그램으로 전송 (중복 dedup 지원).",
        epilog=(
            "예시:\n"
            "  mer-summary https://blog.naver.com/ranto28\n"
            "  mer-summary https://m.blog.naver.com/ranto28?categoryNo=21 \\\n"
            "    https://blog.naver.com/PostList.naver?blogId=ranto28&categoryNo=28\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "urls",
        nargs="+",
        metavar="URL",
        help="블로그 메인 URL 또는 개별 게시글 URL (여러 개 가능 — 모두 같은 실행에 처리)",
    )
    parser.add_argument(
        "--now",
        type=datetime.fromisoformat,
        default=None,
        help='ISO8601 (예: "2026-05-22T10:00:00"). 시간 필터 기준 시각. 미지정 시 datetime.now().',
    )
    parser.add_argument(
        "--days",
        type=int,
        default=2,
        help="최근 N일의 글까지 후보로 본다 (오늘 포함). 기본 2 = 어제+오늘.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help=f"전송 이력 파일 경로 (기본 {DEFAULT_STATE_FILE}). dedup 용도.",
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
    state_file: Path = args.state_file
    sent = dedup.load_sent(state_file)
    initial_count = len(sent)
    print(f"[info] sent_log: {initial_count}건 로드 ({state_file})", file=sys.stderr)

    any_failed = False
    total_processed = 0

    for url in args.urls:
        main_match = fetch.is_naver_blog_main(url)

        if main_match is None:
            # 개별 글 URL — dedup 적용 안 함 (logNo 없을 수 있음)
            if _process_one(url, cfg):
                total_processed += 1
            else:
                any_failed = True
            continue

        blog_id, category_no = main_match
        try:
            refs = fetch.list_posts(blog_id, category_no=category_no)
        except RuntimeError as e:
            print(f"[list] {url}: {e}", file=sys.stderr)
            any_failed = True
            continue

        recent_refs = fetch.filter_recent_days(refs, now, days=args.days)
        # 이미 보낸 logNo 제거
        new_refs = [r for r in recent_refs if r.log_no not in sent]

        if not new_refs:
            print(
                f"[info] {url} (blog_id={blog_id}, category={category_no or '전체'}) "
                f"— 최근 {args.days}일 글 {len(recent_refs)}개 모두 전송 완료 (신규 0)",
                file=sys.stderr,
            )
            continue

        print(
            f"[info] {url} (blog_id={blog_id}, category={category_no or '전체'}) "
            f"— 최근 {args.days}일 글 {len(recent_refs)}개 중 신규 {len(new_refs)}개 처리",
            file=sys.stderr,
        )

        for ref in new_refs:
            if _process_one(ref.url, cfg):
                sent.add(ref.log_no)
                total_processed += 1
            else:
                any_failed = True

    # 신규 전송이 있었으면 sent_log 저장
    if len(sent) > initial_count:
        dedup.save_sent(state_file, sent)
        print(
            f"[info] sent_log: {len(sent) - initial_count}건 추가 저장 (총 {len(sent)}건)",
            file=sys.stderr,
        )

    if total_processed == 0 and not any_failed:
        print("새로 전송할 글이 없습니다.", file=sys.stderr)
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
