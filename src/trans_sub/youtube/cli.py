"""``trans-sub youtube``: put titles, descriptions and subtitles of every language on one video."""

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from trans_sub.youtube import auth
from trans_sub.youtube.meta import dump_json, load_json, load_markdown
from trans_sub.youtube.plan import (
    DEFAULT_MAX_UNITS,
    PushError,
    apply,
    find_subtitles,
    make_plan,
    render,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trans-sub youtube",
        description="Set the title, description and subtitles of every language on a YouTube video.",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    push = sub.add_parser(
        "push",
        help="show, then with --apply make, the changes to one video",
        description="Read the video and its caption tracks, then list what would change per "
        "language and the quota it costs. Nothing is written without --apply. Languages already "
        "on the video and not in the input are kept.",
    )
    push.add_argument("--video", required=True, help="The video ID (the part after watch?v=).")
    push.add_argument("--meta", type=Path, help="Titles and descriptions: a .json file (see meta).")
    push.add_argument("--subs", type=Path, help="Directory holding <stem>.<lang>.srt files.")
    push.add_argument("--stem", help="File name before .<lang>.srt (needed with --subs).")
    push.add_argument(
        "--default-lang",
        help="The video's default language, needed only when the video has none; the push sets it.",
    )
    push.add_argument(
        "--captions",
        choices=("all", "missing", "none"),
        default="all",
        help="all: insert new tracks and replace existing ones (default); missing: insert only; "
        "none: metadata only.",
    )
    push.add_argument(
        "--track-name", default="", help="Name for new caption tracks (default: none)."
    )
    push.add_argument(
        "--max-units",
        type=int,
        default=DEFAULT_MAX_UNITS,
        help=f"Refuse a push that costs more quota units (default {DEFAULT_MAX_UNITS}).",
    )
    push.add_argument(
        "--skip-lang-check",
        action="store_true",
        help="Do not compare the language codes with YouTube's list.",
    )
    push.add_argument("--apply", action="store_true", help="Make the changes.")
    push.add_argument(
        "--client-secret", type=Path, help=f"OAuth client file (or {auth.CLIENT_SECRET_ENV})."
    )
    push.add_argument(
        "--token", type=Path, help=f"Token file to read and write (or {auth.TOKEN_ENV})."
    )

    meta = sub.add_parser(
        "meta",
        help="turn a Markdown table of titles and descriptions into the --meta JSON",
        description="Read the first Markdown table whose first column is the language code and "
        "write {lang: {title, description}} as JSON.",
    )
    meta.add_argument("table", type=Path, help="Markdown file with the table.")
    meta.add_argument("--title-column", required=True, help="Header text or number (from 1).")
    meta.add_argument("--description-column", required=True, help="Header text or number (from 1).")
    meta.add_argument("-o", "--output", type=Path, help="JSON file to write (default: print).")
    return p


def run_push(
    args: argparse.Namespace,
    service_factory: Callable[[], Any],
    media: Callable[[Path], Any],
) -> int:
    if not args.meta and not args.subs:
        raise PushError("nothing to push: give --meta, --subs or both")
    if args.subs and not args.stem:
        raise PushError("--subs needs --stem")
    meta = load_json(args.meta) if args.meta else {}
    subtitles = find_subtitles(args.subs, args.stem) if args.subs else {}
    if args.subs and not subtitles:
        raise PushError(f"no {args.stem}.<lang>.srt files in {args.subs}")

    service = service_factory()
    plan = make_plan(
        service,
        args.video,
        meta,
        subtitles,
        default_lang=args.default_lang,
        captions=args.captions,
        check_langs=not args.skip_lang_check,
    )
    for line in render(plan, args.max_units):
        print(line)
    problems = []
    if plan.total_units > args.max_units:
        problems.append(
            f"the push costs {plan.total_units} units, over --max-units {args.max_units}"
        )
    if plan.unknown_langs:
        problems.append("fix the language codes YouTube does not list, or pass --skip-lang-check")
    if not args.apply:
        print("dry run: nothing written" + ("" if problems else "; pass --apply to write"))
        for problem in problems:
            print(f"would refuse: {problem}")
        return 1 if problems else 0
    if problems:
        raise PushError("; ".join(problems))
    apply(service, plan, meta, media, track_name=args.track_name)
    print("done")
    return 0


def run_meta(args: argparse.Namespace) -> int:
    meta = load_markdown(args.table, args.title_column, args.description_column)
    text = dump_json(meta)
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
        print(f"{args.output}: {len(meta)} languages")
    else:
        sys.stdout.write(text)
    return 0


def main(
    argv: Sequence[str],
    service_factory: Callable[[], Any] | None = None,
    media: Callable[[Path], Any] = auth.media_upload,
) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "meta":
            return run_meta(args)
        factory = service_factory or (lambda: auth.youtube_service(args.client_secret, args.token))
        return run_push(args, factory, media)
    except (OSError, ValueError, auth.AuthError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
