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

def make_llm_model(provider_name="ollama", model_name="llama3", api_url="http://localhost:11434", api_key_encrypted=None):
    """Create a mock LLMModel with a linked provider."""
    provider = MagicMock()
    provider.name = provider_name
    provider.api_url = api_url
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

        selection = MagicMock()
        selection.model = make_llm_model()
        selection.provider = selection.model.provider

        with patch("litellm.acompletion", side_effect=_hang):
            with patch("backend.config.LLM_TIMEOUT_SECONDS", 1):
                from backend.services.llm_service import send_message
                with patch(
                    "backend.services.llm_service.resolve_chat_model_selection",
                    return_value=selection,
                ) as resolve:
                    result = await send_message("hello", db=db, routing_purpose="general_chat")
                assert result is None
                resolve.assert_called_once_with(db, purpose="general_chat")


class TestCompletionKwargs:
    def test_keeps_v1_api_base_for_openai_compatible_providers(self):
        from backend.services.llm_service import _build_completion_kwargs

        model = make_llm_model(
            provider_name="nvidia_nim",
            model_name="meta/llama3-70b-instruct",
            api_url="https://integrate.api.nvidia.com/v1",
            api_key_encrypted="encrypted-key",
        )

        with patch("backend.security.decrypt_data", return_value="secret"):
            kwargs = _build_completion_kwargs(
                model.provider,
                model,
                messages=[{"role": "user", "content": "ping"}],
            )

        assert kwargs["api_base"] == "https://integrate.api.nvidia.com/v1"
        assert kwargs["model"] == "nvidia_nim/meta/llama3-70b-instruct"

    def test_uses_groq_default_base_and_openai_compatible_model_name(self):
        from backend.services.llm_service import _build_completion_kwargs

        model = make_llm_model(
            provider_name="groq",
            model_name="openai/gpt-oss-120b",
            api_url=None,
            api_key_encrypted="encrypted-key",
        )

        with patch("backend.security.decrypt_data", return_value="secret"):
            kwargs = _build_completion_kwargs(
                model.provider,
                model,
                messages=[{"role": "user", "content": "ping"}],
            )

        assert kwargs["api_base"] == "https://api.groq.com/openai/v1"
        assert kwargs["model"] == "openai/gpt-oss-120b"

    @pytest.mark.parametrize("provider_name", ["gemini", "mistral", "cohere", "together", "huggingface", "lm_studio"])
    def test_uses_openai_compatible_prefix_for_template_providers(self, provider_name):
        from backend.services.llm_service import _build_completion_kwargs

        model = make_llm_model(
            provider_name=provider_name,
            model_name="example-model",
            api_url="https://example.test/v1",
            api_key_encrypted="encrypted-key",
        )

        with patch("backend.security.decrypt_data", return_value="secret"):
            kwargs = _build_completion_kwargs(
                model.provider,
                model,
                messages=[{"role": "user", "content": "ping"}],
            )

        assert kwargs["model"] == "openai/example-model"
        assert kwargs["api_base"] == "https://example.test/v1"


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
