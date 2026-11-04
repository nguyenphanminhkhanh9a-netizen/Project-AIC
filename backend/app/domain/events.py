"""WebSocket event envelope and standardized event definitions.

Section 8.2 and Section 3.3 in AIC_ARCHITECTURE_v0.5.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


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
    type: str = Field(
        min_length=1,
        description="Event classification (e.g., 'session.ready', 'assistant.response', 'error')",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific structured data",
    )

    @classmethod
    def create(
        cls,
        event_type: str,
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
