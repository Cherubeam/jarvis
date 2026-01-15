"""
Integration tests for full conversation flow.

Tests the complete flow from user input through LLM response to logging.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from llm_client import LLMClient, TokenUsage
from memory import ConversationLogger
from context_builder import build_system_prompt
from pricing import ModelPricing


@pytest.mark.integration
class TestFullConversationFlow:
    """Integration tests for complete conversation flows."""

    def test_single_turn_conversation(
        self,
        temp_conversations_dir: Path,
        sample_context_all_files: Path
    ):
        """Test a single user→assistant conversation turn."""
        # Setup
        client = LLMClient(
            api_key="test-key",
            default_model="test-model",
            provider="test"
        )
        logger = ConversationLogger(temp_conversations_dir)
        system_prompt = build_system_prompt(sample_context_all_files, "You are helpful.")

        # Mock LiteLLM completion
        with patch('litellm.completion') as mock_completion:
            # Create mock streaming response
            response_text = "Hello! How can I help you today?"
            mock_chunks = []

            for word in response_text.split():
                chunk = Mock()
                chunk.choices = [Mock()]
                chunk.choices[0].delta = Mock()
                chunk.choices[0].delta.content = word + " "
                mock_chunks.append(chunk)

            mock_stream = Mock()
            mock_stream.__iter__ = Mock(return_value=iter(mock_chunks))
            mock_stream.usage = Mock(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150
            )

            mock_completion.return_value = mock_stream

            # Simulate conversation
            logger.add_message("user", "Hello!")

            messages = [
                {"role": "system", "content": system_prompt},
                *logger.get_messages_for_api()
            ]

            stream = client.chat_stream(messages)
            response_chunks = list(stream)
            full_response = "".join(response_chunks)

            usage = stream.usage
            logger.add_message(
                "assistant",
                full_response,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cost_usd=0.0045
            )

            # Verify
            assert len(logger.current_conversation) == 2
            assert logger.current_conversation[0]["role"] == "user"
            assert logger.current_conversation[1]["role"] == "assistant"
            assert logger.metrics.total_tokens == 150
            assert logger.metrics.request_count == 1

    def test_multi_turn_conversation(
        self,
        temp_conversations_dir: Path,
        temp_context_dir: Path
    ):
        """Test multiple back-and-forth exchanges."""
        client = LLMClient(api_key="test-key", default_model="test-model", provider="test")
        logger = ConversationLogger(temp_conversations_dir)

        with patch('litellm.completion') as mock_completion:
            # Mock responses for 3 turns
            def create_mock_stream(text: str, prompt_tokens: int, completion_tokens: int):
                chunk = Mock()
                chunk.choices = [Mock()]
                chunk.choices[0].delta = Mock()
                chunk.choices[0].delta.content = text

                stream = Mock()
                stream.__iter__ = Mock(return_value=iter([chunk]))
                stream.usage = Mock(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens
                )
                return stream

            mock_completion.side_effect = [
                create_mock_stream("Response 1", 100, 20),
                create_mock_stream("Response 2", 120, 25),
                create_mock_stream("Response 3", 145, 30),
            ]

            # Turn 1
            logger.add_message("user", "Hello")
            stream1 = client.chat_stream([{"role": "user", "content": "Hello"}])
            response1 = "".join(stream1)
            logger.add_message("assistant", response1, 100, 20, 120, 0.001)

            # Turn 2
            logger.add_message("user", "How are you?")
            stream2 = client.chat_stream([{"role": "user", "content": "How are you?"}])
            response2 = "".join(stream2)
            logger.add_message("assistant", response2, 120, 25, 145, 0.002)

            # Turn 3
            logger.add_message("user", "Thanks!")
            stream3 = client.chat_stream([{"role": "user", "content": "Thanks!"}])
            response3 = "".join(stream3)
            logger.add_message("assistant", response3, 145, 30, 175, 0.003)

            # Verify
            assert len(logger.current_conversation) == 6  # 3 user + 3 assistant
            assert logger.metrics.request_count == 3
            assert logger.metrics.total_tokens == 120 + 145 + 175

    def test_context_included_in_request(
        self,
        temp_conversations_dir: Path,
        sample_context_all_files: Path
    ):
        """Test that system prompt with context is sent to LLM."""
        client = LLMClient(api_key="test-key", default_model="test-model", provider="test")
        logger = ConversationLogger(temp_conversations_dir)

        system_prompt = build_system_prompt(
            sample_context_all_files,
            "You are Jarvis."
        )

        with patch('litellm.completion') as mock_completion:
            chunk = Mock()
            chunk.choices = [Mock()]
            chunk.choices[0].delta = Mock()
            chunk.choices[0].delta.content = "Response"

            stream = Mock()
            stream.__iter__ = Mock(return_value=iter([chunk]))
            stream.usage = Mock(prompt_tokens=200, completion_tokens=50, total_tokens=250)

            mock_completion.return_value = stream

            # Add user message
            logger.add_message("user", "What do I do for work?")

            # Build messages with context
            messages = [
                {"role": "system", "content": system_prompt},
                *logger.get_messages_for_api()
            ]

            # Make request
            stream = client.chat_stream(messages)
            # Consume the stream to trigger litellm.completion call
            list(stream)

            # Verify litellm.completion was called with context
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args
            messages_arg = call_args[1]["messages"]

            # Check system message includes context
            assert messages_arg[0]["role"] == "system"
            assert "software engineer" in messages_arg[0]["content"]
            assert "Jarvis" in messages_arg[0]["content"]

    def test_token_tracking_across_turns(self, temp_conversations_dir: Path):
        """Test that metrics accumulate correctly across multiple turns."""
        logger = ConversationLogger(temp_conversations_dir)

        # Add multiple messages with usage
        logger.add_message("user", "Turn 1")
        logger.add_message("assistant", "Response 1", 100, 50, 150, 0.001)

        logger.add_message("user", "Turn 2")
        logger.add_message("assistant", "Response 2", 120, 60, 180, 0.002)

        logger.add_message("user", "Turn 3")
        logger.add_message("assistant", "Response 3", 140, 70, 210, 0.003)

        # Verify accumulated metrics
        assert logger.metrics.request_count == 3
        assert logger.metrics.total_prompt_tokens == 360
        assert logger.metrics.total_completion_tokens == 180
        assert logger.metrics.total_tokens == 540
        assert logger.metrics.total_cost_usd == pytest.approx(0.006)

    def test_cost_calculation_integrated(self, temp_conversations_dir: Path):
        """Test that pricing is fetched and used for cost calculation."""
        client = LLMClient(api_key="test-key", default_model="test-model", provider="test")
        logger = ConversationLogger(temp_conversations_dir)

        # Mock pricing
        pricing = ModelPricing(
            prompt_cost=0.000003,
            completion_cost=0.000015,
            model_id="test-model"
        )

        with patch('litellm.completion') as mock_completion:
            chunk = Mock()
            chunk.choices = [Mock()]
            chunk.choices[0].delta = Mock()
            chunk.choices[0].delta.content = "Response"

            stream = Mock()
            stream.__iter__ = Mock(return_value=iter([chunk]))
            stream.usage = Mock(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)

            mock_completion.return_value = stream

            # Make request
            logger.add_message("user", "Hello")
            messages = [{"role": "user", "content": "Hello"}]
            result_stream = client.chat_stream(messages)
            list(result_stream)  # Consume stream

            usage = result_stream.usage

            # Calculate cost
            cost = pricing.calculate_cost(usage.prompt_tokens, usage.completion_tokens)

            # Expected: (1000 * 0.000003) + (500 * 0.000015) = 0.003 + 0.0075 = 0.0105
            assert cost == pytest.approx(0.0105)

            # Add to logger with cost
            logger.add_message(
                "assistant",
                "Response",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
                cost
            )

            assert logger.metrics.total_cost_usd == pytest.approx(0.0105)
