"""CLI entry point for ``trans-sub``."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from PySubtrans import SubtitleError
from srt import SRTParseError

from trans_sub import translate_srt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trans-sub",
        description="Translate an .srt subtitle file using pysubtrans and provider env vars.",
    )
    parser.add_argument("source", type=Path, help="Path to the input .srt file.")
    parser.add_argument("--to", required=True, help="Target language (for example ko or French).")
    parser.add_argument(
        "--provider",
        required=True,
        help="pysubtrans provider name (for example OpenRouter, Gemini, OpenAI, or 'Custom Server').",
    )
    parser.add_argument("-m", "--model", default=None, help="Optional model override.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .srt path (defaults to <stem>.<to>.srt next to source).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and batch the input without contacting any provider or needing an API key.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Write and reuse a persistent .subtrans project file next to the source file.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = translate_srt(
            args.source,
            to=args.to,
            output=args.output,
            provider=args.provider,
            model=args.model,
            dry_run=args.dry_run,
            resume=args.resume,
        )
    except (FileNotFoundError, SubtitleError, SRTParseError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if summary.dry_run:
        print(
            f"Dry run: {summary.lines_total} lines, {summary.scenes} scene(s), "
            f"{summary.batches} batch(es) ({summary.provider}) -> {summary.output}"
        )
        return 0

    if summary.lines_translated < summary.lines_total:
        missing = summary.lines_total - summary.lines_translated
        print(
            f"Translated {summary.lines_translated}/{summary.lines_total} lines "
            f"({missing} missing, {summary.provider}) -> {summary.output}"
        )
        return 1

    print(
        f"Translated {summary.lines_translated}/{summary.lines_total} lines "
        f"({summary.provider}) -> {summary.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
