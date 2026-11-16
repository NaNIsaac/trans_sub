"""Thin CLI and Python wrapper around ``pysubtrans`` for ``.srt`` translation."""

import importlib
import os
from dataclasses import dataclass
from pathlib import Path

from PySubtrans import (
    Options,
    SubtitleError,
    SubtitleTranslator,
    TranslationProvider,
    init_options,
    init_project,
    init_translation_provider,
    init_translator,
)
from PySubtrans.Helpers.Resources import ConfigureConfigDir

PROVIDER_KEY_ENV: dict[str, str] = {
    "OpenAI": "OPENAI_API_KEY",
    "Gemini": "GEMINI_API_KEY",
    "Claude": "CLAUDE_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
    "DeepSeek": "DEEPSEEK_API_KEY",
    "Mistral": "MISTRAL_API_KEY",
    "Azure": "AZURE_API_KEY",
    "Bedrock": "AWS_ACCESS_KEY_ID",
    "LiteLLM": "LITELLM_API_KEY",
    "Requesty": "REQUESTY_API_KEY",
}

OPTIONAL_PROVIDER_EXTRAS: dict[str, str] = {
    "OpenAI": "openai",
    "Azure": "azure",
    "Gemini": "gemini",
    "Claude": "claude",
    "Mistral": "mistral",
    "Bedrock": "bedrock",
    "LiteLLM": "litellm",
}


@dataclass(frozen=True, slots=True)
class TranslationSummary:
    source: Path
    output: Path
    provider: str
    model: str | None
    lines_total: int
    lines_translated: int
    scenes: int
    batches: int
    dry_run: bool


def default_output_path(source: Path, to: str) -> Path:
    suffix = source.suffix or ".srt"
    return source.with_name(f"{source.stem}.{to}{suffix}")


def _resolve_provider(provider: str, options: Options) -> TranslationProvider:
    # Importing PySubtrans.Providers registers built-in and installed provider plugins.
    importlib.import_module("PySubtrans.Providers")

    try:
        return init_translation_provider(provider, options)
    except SubtitleError as exc:
        env_var = PROVIDER_KEY_ENV.get(provider)
        msg = str(exc)
        lower = msg.lower()
        if env_var and ("api key" in lower or "aws access key" in lower):
            raise SubtitleError(
                f"Missing API key for provider {provider!r}: set {env_var} or pass --dry-run"
            ) from exc
        extra = OPTIONAL_PROVIDER_EXTRAS.get(provider)
        if extra and "unknown translation provider" in lower:
            env_note = f" and set {env_var}" if env_var else ""
            raise SubtitleError(
                f"Provider {provider!r} requires optional extra [{extra}] "
                f"(uv sync --extra {extra}){env_note}"
            ) from exc
        raise


def translate_srt(
    source: str | os.PathLike[str],
    *,
    to: str,
    output: str | os.PathLike[str] | None = None,
    provider: str,
    model: str | None = None,
    dry_run: bool = False,
    resume: bool = False,
    translation_provider: TranslationProvider | None = None,
    config_dir: str | os.PathLike[str] | None = None,
) -> TranslationSummary:
    """Translate an ``.srt`` file using ``pysubtrans`` defaults and provider env vars."""
    if not to.strip():
        raise ValueError("Target language 'to' is required")
    if not provider.strip():
        raise ValueError("Translation 'provider' is required")

    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    out_path = Path(output) if output is not None else default_output_path(source_path, to)

    if config_dir is not None:
        app_dir = Path(config_dir)
        app_dir.mkdir(parents=True, exist_ok=True)
        ConfigureConfigDir(str(app_dir))

    option_kwargs: dict[str, str] = {"provider": provider, "target_language": to}
    if model is not None:
        option_kwargs["model"] = model
    options = init_options(**option_kwargs)

    project = init_project(options, filepath=str(source_path), persistent=resume)
    subtitles = project.subtitles
    if subtitles is None:
        raise SubtitleError(f"Failed to load subtitles from {source_path}")

    lines_total = subtitles.linecount
    scenes = len(subtitles.scenes)
    batches = sum(len(scene.batches) for scene in subtitles.scenes)

    if dry_run:
        return TranslationSummary(
            source=source_path,
            output=out_path,
            provider=provider,
            model=model,
            lines_total=lines_total,
            lines_translated=0,
            scenes=scenes,
            batches=batches,
            dry_run=True,
        )

    active_provider = (
        translation_provider
        if translation_provider is not None
        else _resolve_provider(provider, options)
    )
    translator: SubtitleTranslator = init_translator(options, translation_provider=active_provider)
    project.TranslateSubtitles(translator)

    if resume and project.use_project_file:
        project.UpdateProjectFile()

    project.SaveTranslation(str(out_path))
    lines_translated = len(subtitles.translated) if subtitles.translated else 0
    return TranslationSummary(
        source=source_path,
        output=out_path,
        provider=provider,
        model=active_provider.selected_model or model,
        lines_total=lines_total,
        lines_translated=lines_translated,
        scenes=scenes,
        batches=batches,
        dry_run=False,
    )


__all__ = ["PROVIDER_KEY_ENV", "TranslationSummary", "default_output_path", "translate_srt"]
