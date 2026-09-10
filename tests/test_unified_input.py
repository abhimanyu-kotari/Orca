"""
tests/test_unified_input.py — Tests for ORCA's unified voice & text input interface.
Verifies transcription helpers, session state prefilling, error handling,
and chat input submission flows.
"""

import unittest
from unittest.mock import patch, MagicMock
from app import transcribe_voice_query
from streamlit.testing.v1 import AppTest


class TestUnifiedVoiceInput(unittest.TestCase):

    def test_transcribe_voice_query_no_api_key(self):
        """When GEMINI_API_KEY is missing, transcribe_voice_query returns empty string."""
        with patch("config.get_gemini_api_key", return_value=""):
            result = transcribe_voice_query(b"fake_audio_bytes", mime_type="audio/wav")
            self.assertEqual(result, "")

    @patch("config.get_gemini_api_key", return_value="fake-api-key")
    @patch("google.genai.Client")
    def test_transcribe_voice_query_success(self, mock_client_cls, mock_get_key):
        """Verifies Gemini multimodal transcription extracts the spoken text verbatim."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "मुंबई के पास मछली कहाँ पकड़ें?"
        mock_client.models.generate_content.return_value = mock_response

        audio_bytes = b"RIFF....WAVEfmt "
        result = transcribe_voice_query(audio_bytes, mime_type="audio/wav")

        self.assertEqual(result, "मुंबई के पास मछली कहाँ पकड़ें?")
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args[1]
        self.assertIn("contents", call_kwargs)

    @patch("config.get_gemini_api_key", return_value="fake-api-key")
    @patch("google.genai.Client")
    def test_transcribe_voice_query_exception_returns_empty(self, mock_client_cls, mock_get_key):
        """When an exception occurs during transcription, returns an empty string without crashing."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError("Network timeout")

        result = transcribe_voice_query(b"fake_audio", mime_type="audio/wav")
        self.assertEqual(result, "")


class TestChatInputAppTest(unittest.TestCase):

    def test_chat_input_unified_flow(self):
        """Verifies programmatic prefill and submission with accept_audio enabled."""
        script = '''
import streamlit as st

if "mock_voice_transcribed" in st.session_state:
    st.session_state["orca_chat_input"] = st.session_state.pop("mock_voice_transcribed")
    st.session_state["voice_notice"] = "Speech transcribed! You can edit above or submit."

if voice_error := st.session_state.get("voice_error"):
    st.caption(f":red[{voice_error}]")
elif voice_notice := st.session_state.get("voice_notice"):
    st.caption(f":blue[{voice_notice}]")

chat_val = st.chat_input(
    placeholder="Ask about sea conditions, fishing zones, or safety...",
    accept_audio=True,
    key="orca_chat_input",
)

if chat_val:
    text = getattr(chat_val, "text", chat_val)
    st.session_state["submitted_query"] = text
'''
        at = AppTest.from_string(script).run()
        self.assertEqual(len(at.chat_input), 1)
        self.assertIn("Ask about sea conditions", at.chat_input[0].placeholder)

        # 1. Simulate voice transcription setting session state before rerun
        at.session_state["mock_voice_transcribed"] = "Where can I fish near Kochi today?"
        at.run()

        # Chat input is populated with the transcribed text for review/editing
        self.assertEqual(at.chat_input[0].proto.value, "Where can I fish near Kochi today?")
        self.assertTrue(at.chat_input[0].proto.set_value)
        self.assertTrue(len(at.caption) > 0)
        self.assertIn("Speech transcribed", at.caption[0].value)

        # 2. Simulate user submitting the reviewed query
        at.chat_input[0].set_value("Where can I fish near Kochi today?").run()
        self.assertEqual(at.session_state["submitted_query"], "Where can I fish near Kochi today?")


if __name__ == "__main__":
    unittest.main()
