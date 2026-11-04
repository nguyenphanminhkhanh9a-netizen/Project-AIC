"""Unit tests for domain contracts, protocols, and AI Access Strategy boundaries.

Verifies acceptance criteria for Milestone M0 / Task 0.1 & Task 0.2.
"""

import pytest
from pydantic import ValidationError

from app.domain.contracts import (
    AIAccessMode,
    AIAccessRouter,
    AIAccessStrategy,
    AICapability,
    AIExecutionRequest,
    AIExecutionResult,
    AssistantTurn,
    EmotionState,
    LLMProvider,
    MemoryCandidate,
    STTProvider,
    TranscriptResult,
    TranscriptSegment,
    TTSConfig,
    TTSProvider,
    VisualState,
)
from app.domain.events import EventEnvelope, EventType

# ==============================================================================
# MOCK PROVIDERS FOR TESTING PROTOCOLS
# ==============================================================================


class MockSTTProvider:
    provider_id = "mock_stt"

    async def transcribe(self, audio_data: bytes, language: str | None = None) -> TranscriptResult:
        return TranscriptResult(
            text="Mock transcript",
            detected_language=language or "ja",
            language_confidence=1.0,
            provider=self.provider_id,
            duration_ms=1000,
        )


class MockLLMProvider:
    provider_id = "mock_llm"

    async def generate_turn(
        self,
        prompt: str,
        context: list[dict[str, str]] | None = None,
        system_instruction: str | None = None,
    ) -> AssistantTurn:
        return AssistantTurn(
            text="はい、わかりました。",
            output_language="ja-JP",
        )


class MockTTSProvider:
    provider_id = "mock_tts"

    async def synthesize(self, text: str, voice_profile_id: str) -> bytes:
        return b"RIFFmock_audio_bytes"


class MockByokStrategy:
    mode = AIAccessMode.BYOK_DIRECT

    async def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        return AIExecutionResult(
            capability=request.capability,
            success=True,
            data={"generated_text": "Mock BYOK response"},
            route_used=self.mode,
        )


# ==============================================================================
# TEST SUITE
# ==============================================================================


class TestTranscriptResult:
    """Tests for TranscriptResult schema validation."""

    def test_valid_transcript_with_segments(self) -> None:
        result = TranscriptResult(
            text="Hôm nay tôi hơi mệt.",
            detected_language="vi",
            language_confidence=0.95,
            segments=[
                TranscriptSegment(start_ms=0, end_ms=1200, text="Hôm nay"),
                TranscriptSegment(start_ms=1200, end_ms=2400, text="tôi hơi mệt."),
            ],
            provider="faster_whisper",
            duration_ms=2400,
        )
        assert result.text == "Hôm nay tôi hơi mệt."
        assert result.detected_language == "vi"
        assert result.language_confidence == 0.95
        assert len(result.segments) == 2
        assert result.duration_ms == 2400

    def test_valid_transcript_without_optional_fields(self) -> None:
        result = TranscriptResult(
            text="Konnichiwa",
            detected_language="ja",
            provider="mock_stt",
            duration_ms=1000,
        )
        assert result.language_confidence is None
        assert result.segments == []

    def test_invalid_confidence_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TranscriptResult(
                text="Test",
                detected_language="en",
                language_confidence=1.5,
                provider="mock",
                duration_ms=500,
            )

    def test_negative_duration_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TranscriptResult(
                text="Test",
                detected_language="en",
                provider="mock",
                duration_ms=-100,
            )


class TestAssistantTurn:
    """Tests for AssistantTurn contract and Japanese-first default."""

    def test_default_values_enforce_japanese_first(self) -> None:
        turn = AssistantTurn(
            text="そっか。今日は少し休もうね。",
        )
        assert turn.output_language == "ja-JP"
        assert turn.turn_id is not None
        assert turn.scene == "default"
        assert turn.animation == "idle"
        assert turn.emotion.label == "neutral"
        assert turn.tts.enabled is True
        assert turn.tts.voice_profile_id == "default_ja_voice"

    def test_full_assistant_turn_with_subtitles(self) -> None:
        turn = AssistantTurn(
            text="そっか。今日は少し休もうね。",
            output_language="ja-JP",
            subtitle_translations={"vi-VN": "Ra vậy. Hôm nay nghỉ ngơi một chút nhé."},
            emotion=EmotionState(label="comforting", intensity=0.7),
            scene="comfort",
            animation="gentle_idle",
            effects=["soft_glow"],
            tts=TTSConfig(voice_profile_id="voice_ayumi_ja", enabled=True),
        )
        assert turn.subtitle_translations["vi-VN"] == "Ra vậy. Hôm nay nghỉ ngơi một chút nhé."
        assert turn.emotion.label == "comforting"
        assert turn.emotion.intensity == 0.7
        assert "soft_glow" in turn.effects

    def test_invalid_locale_format_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssistantTurn(
                text="Hello",
                output_language="INVALID_LOCALE_12345",
            )

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AssistantTurn(text="")


class TestVisualState:
    """Tests for VisualState schema dispatched to frontend."""

    def test_valid_visual_state(self) -> None:
        state = VisualState(
            character_id="character_01",
            state="speaking",
            emotion="happy",
            intensity=0.8,
            scene="comfort",
            asset_id="comfort_happy_01",
            effects=["sparkles"],
            transition_ms=300,
        )
        assert state.character_id == "character_01"
        assert state.transition_ms == 300
        assert state.intensity == 0.8

    def test_default_transition_ms(self) -> None:
        state = VisualState(
            character_id="character_01",
            asset_id="idle_01",
        )
        assert state.transition_ms == 250
        assert state.state == "idle"
        assert state.emotion == "neutral"


class TestMemoryCandidate:
    """Tests for MemoryCandidate automatic pipeline and security guards."""

    def test_valid_memory_candidate(self) -> None:
        mem = MemoryCandidate(
            type="communication_preference",
            content="Người dùng thích câu trả lời ngắn gọn khi đang căng thẳng.",
            source_message_ids=["msg-001", "msg-002"],
            confidence=0.85,
            importance=0.75,
            status="active",
            sensitivity="non_sensitive",
            version=1,
            updated_by="automation",
            change_reason="repeated_user_prompt",
        )
        assert mem.confidence == 0.85
        assert mem.status == "active"
        assert len(mem.source_message_ids) == 2

    def test_credential_rejection_in_memory_content(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            MemoryCandidate(
                type="user_profile",
                content="API key là sk-1234567890abcdef",
                confidence=0.99,
            )
        assert "apparent credential or secret marker" in str(exc_info.value)

    def test_bearer_token_rejection(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            MemoryCandidate(
                type="user_profile",
                content="User provided Bearer eyJhbGciOi...",
                confidence=0.99,
            )
        assert "apparent credential or secret marker" in str(exc_info.value)


class TestEventEnvelopeAndTypes:
    """Tests for WebSocket EventEnvelope and EventType enum."""

    def test_event_type_enum_values(self) -> None:
        assert EventType.USER_TEXT_SUBMIT.value == "user.text.submit"
        assert EventType.ASSISTANT_RESPONSE.value == "assistant.response"
        assert EventType.SESSION_READY.value == "session.ready"
        assert EventType.VISUAL_STATE.value == "visual.state"

    def test_create_factory_method_with_enum(self) -> None:
        envelope = EventEnvelope.create(
            event_type=EventType.ASSISTANT_RESPONSE,
            conversation_id="conv-123",
            turn_id="turn-456",
            payload={"text": "こんにちは", "output_language": "ja-JP"},
        )
        assert envelope.schema_version == "1.0"
        assert envelope.type == EventType.ASSISTANT_RESPONSE
        assert envelope.conversation_id == "conv-123"
        assert envelope.turn_id == "turn-456"
        assert envelope.payload["text"] == "こんにちは"
        assert envelope.timestamp is not None

    def test_serialization_and_deserialization(self) -> None:
        envelope = EventEnvelope.create(
            event_type=EventType.SESSION_READY,
            conversation_id="conv-abc",
            payload={"backend_status": "healthy"},
        )
        data = envelope.model_dump()
        restored = EventEnvelope.model_validate(data)
        assert restored.event_id == envelope.event_id
        assert restored.payload == envelope.payload


class TestProviderProtocols:
    """Tests verifying runtime_checkable provider adapter protocols."""

    def test_mock_stt_implements_protocol(self) -> None:
        mock = MockSTTProvider()
        assert isinstance(mock, STTProvider)

    def test_mock_llm_implements_protocol(self) -> None:
        mock = MockLLMProvider()
        assert isinstance(mock, LLMProvider)

    def test_mock_tts_implements_protocol(self) -> None:
        mock = MockTTSProvider()
        assert isinstance(mock, TTSProvider)


class TestAIAccessRouterAndADR014:
    """Tests for ADR-014 strategy-based AI access routing."""

    def test_default_mode_is_byok_direct(self) -> None:
        router = AIAccessRouter()
        assert router.get_route(AICapability.LLM) == AIAccessMode.BYOK_DIRECT
        assert router.get_route(AICapability.STT) == AIAccessMode.BYOK_DIRECT
        assert router.get_route(AICapability.TTS) == AIAccessMode.BYOK_DIRECT

    def test_managed_gateway_strictly_disabled_in_m0(self) -> None:
        router = AIAccessRouter()
        with pytest.raises(ValueError) as exc_info:
            router.set_route(AICapability.LLM, AIAccessMode.MANAGED_GATEWAY)
        assert "strictly DISABLED in Milestone M0" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_successful_execution_via_registered_strategy(self) -> None:
        router = AIAccessRouter()
        strategy = MockByokStrategy()
        assert isinstance(strategy, AIAccessStrategy)

        router.register_strategy(strategy)
        request = AIExecutionRequest(
            capability=AICapability.LLM,
            action="generate_turn",
            payload={"prompt": "Hello"},
        )

        result = await router.execute(request)
        assert result.success is True
        assert result.route_used == AIAccessMode.BYOK_DIRECT
        assert result.data["generated_text"] == "Mock BYOK response"

    @pytest.mark.asyncio
    async def test_no_silent_fallback_on_unregistered_strategy(self) -> None:
        router = AIAccessRouter()
        request = AIExecutionRequest(
            capability=AICapability.LLM,
            action="generate_turn",
            payload={"prompt": "Hello"},
        )
        with pytest.raises(RuntimeError) as exc_info:
            await router.execute(request)
        assert "Silent fallback is prohibited by ADR-014" in str(exc_info.value)

    def test_secret_in_payload_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            AIExecutionRequest(
                capability=AICapability.LLM,
                action="generate_turn",
                payload={"api_key": "sk-12345"},
            )
        assert "Secret marker" in str(exc_info.value)
