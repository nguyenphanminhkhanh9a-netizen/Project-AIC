"""Core domain contracts for Project AIC.

Corresponds to Section 7 of docs/AIC_ARCHITECTURE_v0.5.md and Milestone M0 requirements.
"""

from __future__ import annotations

import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# Common default constants
DEFAULT_OUTPUT_LANGUAGE = "ja-JP"
DEFAULT_TRANSITION_MS = 250
ALLOWED_LOCALES = {"ja-JP", "vi-VN", "en-US"}


class TranscriptSegment(BaseModel):
    """Optional time-aligned transcript segment from STT provider."""

    start_ms: int = Field(ge=0, description="Segment start offset in milliseconds")
    end_ms: int = Field(ge=0, description="Segment end offset in milliseconds")
    text: str = Field(min_length=1, description="Segment recognized text")


class TranscriptResult(BaseModel):
    """Normalized output from Speech-to-Text (STT) providers.

    Section 7.1 in AIC_ARCHITECTURE_v0.5.md.
    """

    text: str = Field(description="Recognized transcript text")
    detected_language: str = Field(
        min_length=2,
        max_length=10,
        description="ISO language code detected (e.g. 'vi', 'ja', 'en')",
    )
    language_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 (None if unsupported)",
    )
    segments: list[TranscriptSegment] = Field(
        default_factory=list,
        description="List of timestamped segments if provider supports word/phrase alignment",
    )
    provider: str = Field(
        min_length=1,
        description="Identifier of STT provider (e.g. 'faster_whisper', 'cloud_whisper')",
    )
    duration_ms: int = Field(
        ge=0,
        description="Audio duration in milliseconds",
    )


class EmotionState(BaseModel):
    """Emotion classification and intensity for character animation."""

    label: str = Field(
        default="neutral",
        description="Standardized emotion label (e.g. 'neutral', 'comforting', 'happy', 'sad')",
    )
    intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Intensity factor between 0.0 (subtle) and 1.0 (maximum expression)",
    )


class TTSConfig(BaseModel):
    """Text-to-Speech configuration for an assistant response."""

    voice_profile_id: str = Field(
        default="default_ja_voice",
        description="Reference identifier to character voice preset",
    )
    enabled: bool = Field(
        default=True,
        description="Whether voice synthesis should be triggered",
    )


class AssistantTurn(BaseModel):
    """Structured assistant response turn.

    Section 7.2 in AIC_ARCHITECTURE_v0.5.md.
    Enforces Japanese-first output default (SRS Section 5.1/14).
    """

    turn_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique UUID for this turn",
    )
    text: str = Field(
        min_length=1,
        description="Primary spoken/written response (Japanese by default)",
    )
    output_language: str = Field(
        default=DEFAULT_OUTPUT_LANGUAGE,
        description="Language of response text, default ja-JP",
    )
    subtitle_translations: dict[str, str] = Field(
        default_factory=dict,
        description="Keyed by locale code, e.g. {'vi-VN': '...', 'en-US': '...'}",
    )
    emotion: EmotionState = Field(
        default_factory=EmotionState,
        description="Target emotion and intensity",
    )
    scene: str = Field(
        default="default",
        description="Scene context identifier (e.g. 'default', 'comfort', 'study')",
    )
    animation: str = Field(
        default="idle",
        description="Animation state name (e.g. 'idle', 'speaking', 'gentle_idle')",
    )
    effects: list[str] = Field(
        default_factory=list,
        description="Visual particle/screen effects",
    )
    tts: TTSConfig = Field(
        default_factory=TTSConfig,
        description="TTS synthesis options",
    )

    @field_validator("output_language")
    @classmethod
    def validate_output_language(cls, value: str) -> str:
        """Validate output language code format."""
        if not re.match(r"^[a-z]{2,3}(-[A-Z]{2,4})?$", value):
            raise ValueError(f"Invalid BCP-47 locale format: '{value}'")
        return value


class VisualState(BaseModel):
    """Resolved visual state dispatched to frontend Character Overlay.

    Section 7.3 in AIC_ARCHITECTURE_v0.5.md.
    """

    character_id: str = Field(
        min_length=1,
        description="Active character identifier (e.g. 'character_01')",
    )
    state: str = Field(
        default="idle",
        description="High-level state (e.g. 'idle', 'speaking', 'listening')",
    )
    emotion: str = Field(
        default="neutral",
        description="Resolved emotion string",
    )
    intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Emotion intensity factor",
    )
    scene: str = Field(
        default="default",
        description="Current visual scene",
    )
    asset_id: str = Field(
        min_length=1,
        description="Resolved asset ID from character manifest",
    )
    effects: list[str] = Field(
        default_factory=list,
        description="Active CSS or overlay visual effects",
    )
    transition_ms: int = Field(
        default=DEFAULT_TRANSITION_MS,
        ge=0,
        description="Transition duration in milliseconds",
    )


MemoryType = Literal[
    "communication_preference",
    "user_profile",
    "episodic",
    "relationship_marker",
    "fact",
]

MemoryStatus = Literal["active", "archived", "revoked"]

MemorySensitivity = Literal["non_sensitive", "sensitive"]


class MemoryCandidate(BaseModel):
    """Candidate memory extracted from conversation turn.

    Section 7.5 in AIC_ARCHITECTURE_v0.5.md.
    Designed for automatic background processing without requiring per-item approval.
    Explicitly guards against storing credentials or API keys.
    """

    memory_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the memory entry",
    )
    type: MemoryType = Field(
        description="Semantic category of memory",
    )
    content: str = Field(
        min_length=1,
        description="Normalized memory proposition or statement",
    )
    source_message_ids: list[str] = Field(
        default_factory=list,
        description="Originating message IDs providing attribution evidence",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from automated extraction pipeline",
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Salience score for retrieval ranking",
    )
    status: MemoryStatus = Field(
        default="active",
        description="Lifecycle status: 'active', 'archived', 'revoked'",
    )
    sensitivity: MemorySensitivity = Field(
        default="non_sensitive",
        description="Sensitivity classification",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Schema/revision counter for audit trail and undo",
    )
    updated_by: str = Field(
        default="automation",
        description="Author or modifier identifier ('automation', 'user_edit')",
    )
    change_reason: str = Field(
        default="",
        description="Audit log reason explaining creation or revision",
    )

    @field_validator("content")
    @classmethod
    def reject_apparent_secrets(cls, value: str) -> str:
        """Enforce credential boundary: Memory must never store API keys or passwords."""
        lowered = value.lower()
        forbidden_indicators = [
            "sk-",
            "bearer ",
            "api_key=",
            "apikey=",
            "gho_",
            "password=",
            "secret_key=",
        ]
        for pattern in forbidden_indicators:
            if pattern in lowered:
                raise ValueError(
                    f"MemoryCandidate content contains apparent credential or secret marker: '{pattern}'. "
                    "Credentials and sensitive keys must never enter persistent memory."
                )
        return value
