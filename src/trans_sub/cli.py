"""CLI entry point for ``trans-sub``.

``translate`` sends the file to an LLM provider through pysubtrans. ``build``, ``check`` and
``template`` work offline from a translation table. The bare form ``trans-sub <file> --to ...``
is ``translate``.
"""

import argparse
import io
import sys
from collections.abc import Sequence
from pathlib import Path

from PySubtrans import SubtitleError
from srt import SRTParseError

from trans_sub import subrip, translate_srt
from trans_sub.check import Limits, base_name, check
from trans_sub.table import Table, TableError
from trans_sub.template import prompt_text, table_text

COMMANDS = ("translate", "build", "check", "template")


def add_translate_args(parser: argparse.ArgumentParser) -> None:
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


def build_parser() -> argparse.ArgumentParser:
    """The parser of the bare form, ``trans-sub <file> --to ...``."""
    parser = argparse.ArgumentParser(
        prog="trans-sub",
        description="Translate an .srt subtitle file using pysubtrans and provider env vars.",
    )
    add_translate_args(parser)
    return parser


def command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trans-sub",
        description="Translate .srt subtitle files and check the translations against the source.",
        epilog="'trans-sub <file> --to ...' without a command is 'trans-sub translate'.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = sub.add_parser(
        "translate",
        help="translate with an LLM provider (needs its API key)",
        description="Translate an .srt subtitle file using pysubtrans and provider env vars.",
    )
    add_translate_args(p)
    p.set_defaults(run=run_translate)

    p = sub.add_parser(
        "build",
        help="write one .srt per language from a translation table",
        description="Write <name>.<lang>.srt for each language, with the source's cues and times "
        "and the table's text. No network access.",
    )
    p.add_argument("source", type=Path, help="The source .srt file.")
    p.add_argument(
        "--table",
        type=Path,
        action="append",
        required=True,
        help="Translation table; repeat to read several (they must agree).",
    )
    p.add_argument(
        "--langs", nargs="+", help="Languages to write (default: every one in the table)."
    )
    p.add_argument("--out", type=Path, help="Output directory (default: the source's directory).")
    p.add_argument(
        "--name", help="Output base name (default: the source name without its language)."
    )
    p.add_argument(
        "--source-lang",
        help="Language of the source; listing it in --langs writes a copy of the source.",
    )
    p.set_defaults(run=run_build)

    p = sub.add_parser(
        "check",
        help="check translated .srt files against the source",
        description="Fail on a file that does not parse, a cue count or time that differs from the "
        "source, an empty cue, too many lines or a line too long; warn on cues read too fast. "
        "Exit 1 on any failure.",
    )
    p.add_argument("source", type=Path, help="The source .srt file.")
    p.add_argument(
        "targets",
        type=Path,
        nargs="+",
        help="Translated files, or directories holding <name>.<lang>.srt files.",
    )
    defaults = Limits()
    p.add_argument("--max-lines", type=int, default=defaults.max_lines, help="Lines per cue.")
    p.add_argument("--width", type=int, default=defaults.width, help="Characters per line.")
    p.add_argument(
        "--dense-width",
        type=int,
        default=defaults.dense_width,
        help="Characters per line of Chinese, Japanese, Korean or Thai.",
    )
    p.add_argument(
        "--cps",
        type=float,
        default=defaults.cps,
        help="Characters a second above which a cue is a warning; 0 turns the warning off.",
    )
    p.add_argument(
        "--dense-cps",
        type=float,
        default=defaults.dense_cps,
        help="The same for Chinese, Japanese, Korean or Thai.",
    )
    p.set_defaults(run=run_check)

    p = sub.add_parser(
        "template",
        help="write an empty translation table and a prompt to fill it",
        description="Write <name>.table.txt with every distinct source line once and an empty row "
        "per language, and <name>.prompt.txt, which asks any AI chat to fill the table. "
        "No network access.",
    )
    p.add_argument("source", type=Path, help="The source .srt file.")
    p.add_argument("--langs", nargs="+", required=True, help="Languages to translate into.")
    p.add_argument("--table", type=Path, action="append", help="Existing table to fill rows from.")
    p.add_argument("--out", type=Path, help="Output directory (default: the source's directory).")
    p.add_argument("--force", action="store_true", help="Overwrite an existing table file.")
    p.set_defaults(run=run_template)
    return parser


def run_translate(args: argparse.Namespace) -> int:
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


def run_build(args: argparse.Namespace) -> int:
    cues = subrip.read(args.source)
    table = Table.load(*args.table)
    langs = args.langs or table.languages()
    if not langs:
        raise TableError("the table has no translations and no --langs were given")
    out = args.out or args.source.parent
    name = args.name or base_name(args.source)
    files = {
        lang: cues if lang == args.source_lang else table.translate(cues, lang) for lang in langs
    }
    out.mkdir(parents=True, exist_ok=True)
    for lang, translated in files.items():
        path = out / f"{name}.{lang}.srt"
        if path.resolve() == args.source.resolve():
            raise ValueError(f"{path} is the source; give another --out or --name")
        subrip.write(path, translated)
        print(path)
    return 0


def run_check(args: argparse.Namespace) -> int:
    limits = Limits(args.max_lines, args.width, args.dense_width, args.cps, args.dense_cps)
    report = check(args.source, args.targets, limits)
    if not report.files:
        report.failures.append(f"no translated files found for {args.source.name}")
    print(
        f"checked {report.files} files: {len(report.failures)} failures, "
        f"{len(report.warnings)} warnings"
    )
    for line in report.failures:
        print("FAIL", line)
    for line in report.warnings:
        print("warn", line)
    return 1 if report.failures else 0


def run_template(args: argparse.Namespace) -> int:
    cues = subrip.read(args.source)
    known = Table.load(*args.table) if args.table else None
    out = args.out or args.source.parent
    name = base_name(args.source)
    table_path, prompt_path = out / f"{name}.table.txt", out / f"{name}.prompt.txt"
    if table_path.exists() and not args.force:
        raise ValueError(f"{table_path} exists; pass it as --table to keep its rows, or --force")
    table = table_text(cues, args.langs, known)
    out.mkdir(parents=True, exist_ok=True)
    table_path.write_text(table, encoding="utf-8", newline="\n")
    prompt_path.write_text(prompt_text(table, args.langs), encoding="utf-8", newline="\n")
    print(table_path)
    print(prompt_path)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in (*COMMANDS, "-h", "--help"):
        return run_translate(build_parser().parse_args(argv))
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = command_parser().parse_args(argv)
    try:
        return args.run(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
