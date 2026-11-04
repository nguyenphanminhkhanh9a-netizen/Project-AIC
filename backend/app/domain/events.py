"""WebSocket event envelope and standardized event definitions.

Section 8.2 and Section 3.3 in AIC_ARCHITECTURE_v0.5.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Standardized event types for WebSocket communication.

    Section 8.2 in AIC_ARCHITECTURE_v0.5.md.
    """

    # Client -> Server
    USER_TEXT_SUBMIT = "user.text.submit"
    USER_AUDIO_START = "user.audio.start"
    USER_AUDIO_CHUNK = "user.audio.chunk"
    USER_AUDIO_END = "user.audio.end"
    USER_TURN_CANCEL = "user.turn.cancel"
    CLIENT_PING = "client.ping"

    # Server -> Client
    SESSION_READY = "session.ready"
    STT_PARTIAL = "stt.partial"
    STT_FINAL = "stt.final"
    ASSISTANT_THINKING = "assistant.thinking"
    ASSISTANT_TEXT_DELTA = "assistant.text.delta"
    ASSISTANT_RESPONSE = "assistant.response"
    SUBTITLE_SEGMENT = "subtitle.segment"
    VISUAL_STATE = "visual.state"
    TTS_AUDIO_CHUNK = "tts.audio.chunk"
    TTS_AUDIO_COMPLETED = "tts.audio.completed"
    TURN_COMPLETED = "turn.completed"
    ERROR = "error"


class EventEnvelope(BaseModel):
    """Standardized event envelope wrapping all server<->client WebSocket events."""

    schema_version: str = Field(
        default="1.0",
        description="Event envelope schema version",
    )
    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this specific event message",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp of creation",
    )
    conversation_id: str = Field(
        min_length=1,
        description="Associated conversation session UUID",
    )
    turn_id: str | None = Field(
        default=None,
        description="Turn correlation UUID if bound to a specific turn",
    )
    type: EventType | str = Field(
        description="Event classification (EventType enum or custom string)",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific structured data",
    )

    @classmethod
    def create(
        cls,
        event_type: EventType | str,
        conversation_id: str,
        payload: dict[str, Any],
        turn_id: str | None = None,
    ) -> EventEnvelope:
        """Convenience factory creating a validated EventEnvelope."""
        return cls(
            type=event_type,
            conversation_id=conversation_id,
            turn_id=turn_id,
            payload=payload,
        )
