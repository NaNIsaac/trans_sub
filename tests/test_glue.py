"""Offline tests for the trans_sub glue around pysubtrans."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import srt
from PySubtrans import SubtitleError
from PySubtrans.SettingsType import SettingsType
from PySubtrans.Translation import Translation
from PySubtrans.TranslationClient import TranslationClient
from PySubtrans.TranslationPrompt import TranslationPrompt
from PySubtrans.TranslationProvider import TranslationProvider
from PySubtrans.TranslationRequest import TranslationRequest

from trans_sub import PROVIDER_KEY_ENV, default_output_path, translate_srt
from trans_sub.cli import main

SAMPLE_SRT = (
    "1\n00:00:01,000 --> 00:00:02,500\nHello world.\n\n"
    "2\n00:00:03,000 --> 00:00:04,500\nSecond subtitle line.\n\n"
)


class _FakeTranslationClient(TranslationClient):
    def __init__(self, settings: SettingsType):
        super().__init__(settings)
        self._last_lines: list = []

    def BuildTranslationPrompt(
        self,
        user_prompt: str,
        instructions: str,
        lines: list,
        context: dict,
    ) -> TranslationPrompt:
        self._last_lines = list(lines)
        prompt = TranslationPrompt(user_prompt, False)
        prompt.prompt_template = "{prompt}"
        prompt.supports_system_prompt = True
        prompt.GenerateMessages(instructions, lines, context)
        return prompt

    def _request_translation(
        self, request: TranslationRequest, temperature: float | None = None
    ) -> Translation:
        blocks = [
            f"#{line.number}\nOriginal>\n{line.text}\nTranslation>\n[ko] {line.text}"
            for line in self._last_lines
        ]
        return Translation({"text": "\n\n".join(blocks)})


class _FakeProvider(TranslationProvider):
    name = "FakeProvider"

    def __init__(self, model: str = "fake-model"):
        super().__init__(self.name, SettingsType({"model": model}))

    def GetTranslationClient(self, settings: SettingsType) -> TranslationClient:
        merged = deepcopy(self.settings)
        merged.update(settings)
        return _FakeTranslationClient(merged)

    def ValidateSettings(self) -> bool:
        return True


def _clear_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_var in (*PROVIDER_KEY_ENV.values(), "CUSTOM_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)


def test_default_output_path():
    assert default_output_path(Path("dir/movie.srt"), "ko") == Path("dir/movie.ko.srt")


def test_cli_requires_provider_and_has_no_api_key_flag(tmp_path: Path):
    src = tmp_path / "movie.srt"
    src.write_text(SAMPLE_SRT, encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main([str(src), "--to", "ko"])
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        main([str(src), "--to", "ko", "--provider", "OpenRouter", "--api-key", "nope"])
    assert exc.value.code == 2


def test_dry_run_works_without_any_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _clear_provider_keys(monkeypatch)
    monkeypatch.setenv("LLM_SUBTRANS_CONFIG_PATH", str(tmp_path / "cfg"))

    src = tmp_path / "sample.srt"
    src.write_text(SAMPLE_SRT, encoding="utf-8")

    code = main([str(src), "--to", "ko", "--provider", "OpenRouter", "--dry-run"])
    assert code == 0

    out = tmp_path / "sample.ko.srt"
    assert not out.exists()

    stdout = capsys.readouterr().out
    assert "Dry run: 2 lines" in stdout
    assert str(out) in stdout


def test_missing_api_key_reports_provider_and_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _clear_provider_keys(monkeypatch)
    # Set another provider's secret to confirm no env secret value ever appears in stderr.
    sentinel = "secret-should-not-leak"
    monkeypatch.setenv("OPENAI_API_KEY", sentinel)

    src = tmp_path / "sample.srt"
    src.write_text(SAMPLE_SRT, encoding="utf-8")

    with pytest.raises(SubtitleError, match="OpenRouter") as exc:
        translate_srt(src, to="ko", provider="OpenRouter", config_dir=tmp_path / "cfg")
    assert "OPENROUTER_API_KEY" in str(exc.value)
    assert sentinel not in str(exc.value)

    code = main([str(src), "--to", "ko", "--provider", "OpenRouter"])
    assert code == 2
    stderr = capsys.readouterr().err
    assert "OpenRouter" in stderr
    assert "OPENROUTER_API_KEY" in stderr
    assert sentinel not in stderr

    with pytest.raises(SubtitleError, match="Gemini") as exc_opt:
        translate_srt(src, to="ko", provider="Gemini", config_dir=tmp_path / "cfg")
    assert "GEMINI_API_KEY" in str(exc_opt.value)


def test_translate_srt_with_fake_provider_and_resume(tmp_path: Path):
    src = tmp_path / "clip.srt"
    src.write_text(SAMPLE_SRT, encoding="utf-8")
    cfg = tmp_path / "cfg"

    summary = translate_srt(
        src,
        to="ko",
        provider="OpenRouter",
        resume=True,
        translation_provider=_FakeProvider(),
        config_dir=cfg,
    )

    assert not summary.dry_run
    assert summary.lines_total == 2
    assert summary.lines_translated == 2
    assert summary.output == tmp_path / "clip.ko.srt"
    assert (tmp_path / "clip.subtrans").exists()

    original_cues = list(srt.parse(SAMPLE_SRT))
    translated_cues = list(srt.parse(summary.output.read_text(encoding="utf-8")))
    assert [(c.index, c.start, c.end) for c in translated_cues] == [
        (c.index, c.start, c.end) for c in original_cues
    ]
    assert [c.content for c in translated_cues] == [
        "[ko] Hello world.",
        "[ko] Second subtitle line.",
    ]
