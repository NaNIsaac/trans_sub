# trans_sub

AI translation of `.srt` subtitle files: SRT in, a context-aware translation of the whole file, SRT out. It started as a tool to help produce YouTube subtitles and is meant to stay a practical tool for that.

**Status: early, unfinished.** Only the project skeleton exists. `main.py` prints a greeting; there is no translation code yet. The plan for resuming is below.

A snapshot of this repository (commit `18489eb`) was copied with its history into the private `sandbox` repository as `trans_sub/` on 2026-10-16. Later commits exist only here.

## Usage

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/NaNIsaac/trans_sub.git
cd trans_sub
uv run main.py
```

Tests:

```bash
uv run pytest
```

## Core experience

```
movie.srt  ->  trans_sub  ->  movie.ko.srt
```

The user gives an SRT file and a target language. The tool translates the entire file with an AI model, using the surrounding cues as context, and writes a valid SRT with the same cues in the same order at the same times. Nothing is silently lost, duplicated or reordered, and an interrupted run can be continued.

## Required features (not yet implemented)

| Feature | What it means |
| --- | --- |
| Long files | Split into batches that fit a model's context and output limit; hundreds to thousands of cues per file |
| Context | Each batch carries preceding and following cues (translated only once) plus an optional glossary and a short description of the video |
| Order and timing | Cue count, index and start/end times of the output equal the input; only the text changes |
| Validation | Missing, duplicated, merged or split cues, empty translations and broken tags are detected and reported per cue |
| Checkpoint and retry | Finished batches are written to disk as they complete; a failed batch is retried, a rerun skips finished batches |
| Models | A provider interface so that different models can be used; no provider is assumed |
| MCP | An MCP server exposing the same operations, so an AI client can drive a translation |
| CLI | A standalone command, `trans-sub movie.srt --to ko` |

General SRT handling (parsing, composing, retiming, merging, splitting, overlap checks) is not part of trans_sub. It uses a library for that; `srt` is the current dependency.

## Validation

The `srt` parser does not check any of these, so the pipeline must:

- overlapping cues are accepted silently;
- non-contiguous or duplicated indices are kept as they are;
- a blank line inside a cue cannot be represented, so a translation containing one has to be cleaned (`srt.make_legal_content`);
- `compose` writes LF line endings regardless of the input;
- a malformed block raises `srt.SRTParseError`, so a damaged input fails loudly.

`tests/test_srt_contract.py` pins these behaviours of `srt` 3.5.3.

## Plan for resuming

1. Read the file (`utf-8-sig`), parse with `srt`, fail on `SRTParseError`.
2. Batch with context: fixed-size windows with context cues on both sides.
3. A `Translator` protocol with one implementation first; the prompt asks for a JSON list keyed by cue index so that the reply can be matched to the input.
4. Check each reply against the validation rules above; retry the batch with the failure reason.
5. Write finished batches to a sidecar JSON file; compose the SRT at the end.
6. CLI, then MCP server on top of the same functions.

Each step is testable with a fake translator, so no API key is needed for the test suite.
