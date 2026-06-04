"""Shared string constants — practice modes and language codes.

These values live in one place instead of as magic strings scattered across the engine, so a
typo can't silently misroute. They match the `mode` and `language` fields in questions/*.json.
(Note: a content rubric's `kind` — "interview" / "proficiency" — is a separate discriminator,
not a mode, and lives with its dataclass.)
"""

# Practice modes (a track's `mode`): selects which content rubric runs.
MODE_INTERVIEW = "interview"
MODE_JAPANESE = "japanese"

# Language / ISO codes (a track's `language`; also the transcription language).
LANG_EN = "en"
LANG_JA = "ja"
