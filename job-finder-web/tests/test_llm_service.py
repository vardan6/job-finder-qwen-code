"""
Tests for llm_service.py

Mocks litellm.acompletion so no real LLM is required.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.llm_service import extract_json_from_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_llm_model(provider_name="ollama", model_name="llama3", api_url=None, api_key_encrypted=None):
    """Create a mock LLMModel with a linked provider."""
    provider = MagicMock()
    provider.name = provider_name
    provider.api_url = api_url or "http://localhost:11434"
    provider.api_key_encrypted = api_key_encrypted
    provider.auth_method = "api_key"

    model = MagicMock()
    model.model_name = model_name
    model.provider = provider
    return model


def make_mock_response(content="Test response"):
    """Create a mock LiteLLM response object."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# call_llm — timeout behaviour
# ---------------------------------------------------------------------------

class TestCallLLMTimeout:
    @pytest.mark.asyncio
    async def test_times_out_when_llm_hangs(self, db):
        """call_llm should raise asyncio.TimeoutError when LLM does not respond."""
        async def _hang(*args, **kwargs):
            await asyncio.sleep(9999)

        model = make_llm_model()

        with patch("litellm.acompletion", side_effect=_hang):
            with patch("backend.config.LLM_TIMEOUT_SECONDS", 1):  # 1s for fast tests
                from backend.services.llm_service import call_llm
                # The function catches TimeoutError and returns None rather than propagating
                result = await call_llm(db, model, "test prompt")
                assert result is None  # timed out → returns None (not raises)

    @pytest.mark.asyncio
    async def test_returns_response_on_success(self, db):
        """call_llm should return the LLM text on a successful call."""
        model = make_llm_model()
        mock_response = make_mock_response("Hello from LLM")

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            from backend.services.llm_service import call_llm
            result = await call_llm(db, model, "test prompt")
            assert result == "Hello from LLM"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self, db):
        """call_llm should return None when the LLM response has no choices."""
        model = make_llm_model()
        mock_response = MagicMock()
        mock_response.choices = []

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            from backend.services.llm_service import call_llm
            result = await call_llm(db, model, "test prompt")
            assert result is None


# ---------------------------------------------------------------------------
# send_message — timeout behaviour
# ---------------------------------------------------------------------------

class TestSendMessageTimeout:
    @pytest.mark.asyncio
    async def test_times_out_returns_none(self, db):
        """send_message should return None (not hang) when LLM is unresponsive."""
        async def _hang(*args, **kwargs):
            await asyncio.sleep(9999)

        # Set up a function mapping in the DB
        from backend.models.document import LLMFunctionMapping
        from backend.models.llm_provider import LLMProvider, LLMModel as DBLLMModel

        provider = LLMProvider(name="ollama", api_url="http://localhost:11434", is_active=True)
        db.add(provider)
        db.flush()

        llm_model = DBLLMModel(
            provider_id=provider.id,
            model_name="llama3",
            is_default_for_provider=True,
        )
        db.add(llm_model)
        db.flush()

        mapping = LLMFunctionMapping(
            function_name="ai_chat",
            model_id=llm_model.id,
            is_active=True,
        )
        db.add(mapping)
        db.commit()

        with patch("litellm.acompletion", side_effect=_hang):
            with patch("backend.config.LLM_TIMEOUT_SECONDS", 1):
                from backend.services import llm_service
                import importlib
                importlib.reload(llm_service)
                from backend.services.llm_service import send_message
                result = await send_message("hello", function_name="ai_chat", db=db)
                assert result is None


# ---------------------------------------------------------------------------
# extract_json_from_response
# ---------------------------------------------------------------------------

class TestExtractJsonFromResponse:
    def test_extracts_json_object_from_markdown_block(self):
        response = '```json\n{"key": "value"}\n```'
        result = extract_json_from_response(response)
        assert result == {"key": "value"}

    def test_extracts_json_array_from_markdown_block(self):
        response = '```json\n[{"skill": "Python"}]\n```'
        result = extract_json_from_response(response)
        assert result == [{"skill": "Python"}]

    def test_extracts_raw_json_object(self):
        response = 'Here is the result: {"score": 85}'
        result = extract_json_from_response(response)
        assert result == {"score": 85}

    def test_extracts_raw_json_array(self):
        response = '[{"a": 1}, {"b": 2}]'
        result = extract_json_from_response(response)
        assert result == [{"a": 1}, {"b": 2}]

    def test_returns_none_on_invalid_json(self):
        response = "This is not JSON at all."
        result = extract_json_from_response(response)
        assert result is None

    def test_code_block_without_json_language_tag(self):
        response = "```\n{\"key\": \"value\"}\n```"
        result = extract_json_from_response(response)
        assert result == {"key": "value"}
