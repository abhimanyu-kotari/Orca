"""
tests/test_unified_input.py — Tests for ORCA's unified voice & text input interface.
Verifies transcription helpers, MIME-type autodetection, session state prefilling,
error handling, and chat input submission flows.
"""

import unittest
from unittest.mock import patch, MagicMock
from app import transcribe_voice_query, detect_audio_mime_type
from streamlit.testing.v1 import AppTest


class TestUnifiedVoiceInput(unittest.TestCase):

    def test_detect_audio_mime_type(self):
        """Verifies binary magic byte detection for various browser audio containers."""
        # WebM
        webm_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 200
        self.assertEqual(detect_audio_mime_type(webm_bytes, "audio/wav"), "audio/webm")

        # WAV
        wav_bytes = b"RIFF" + b"\x00" * 4 + b"WAVEfmt " + b"\x00" * 100
        self.assertEqual(detect_audio_mime_type(wav_bytes, "audio/octet-stream"), "audio/wav")

        # OGG
        ogg_bytes = b"OggS\x00\x02" + b"\x00" * 100
        self.assertEqual(detect_audio_mime_type(ogg_bytes, "audio/wav"), "audio/ogg")

        # MP3 (ID3)
        mp3_bytes = b"ID3\x03\x00" + b"\x00" * 100
        self.assertEqual(detect_audio_mime_type(mp3_bytes, "audio/wav"), "audio/mp3")

        # MP4 / M4A
        mp4_bytes = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 100
        self.assertEqual(detect_audio_mime_type(mp4_bytes, "audio/wav"), "audio/mp4")

        # Fallback for unknown
        unknown_bytes = b"\x01\x02\x03\x04" + b"\x00" * 100
        self.assertEqual(detect_audio_mime_type(unknown_bytes, "audio/wav"), "audio/wav")

    def test_transcribe_voice_query_no_api_key(self):
        """When GEMINI_API_KEY is missing, transcribe_voice_query raises ValueError."""
        with patch("config.get_gemini_api_key", return_value=""):
            with self.assertRaises(ValueError):
                transcribe_voice_query(b"fake_audio_bytes" * 20, mime_type="audio/wav")

    def test_transcribe_voice_query_too_short(self):
        """Audio under 128 bytes returns empty string without calling Gemini API."""
        with patch("config.get_gemini_api_key", return_value="fake-key"):
            result = transcribe_voice_query(b"short", mime_type="audio/wav")
            self.assertEqual(result, "")

    @patch("config.get_gemini_api_key", return_value="fake-api-key")
    @patch("app._get_voice_gemini_client")
    def test_transcribe_voice_query_webm_mime_autodetected(self, mock_get_client, mock_get_key):
        """Verifies that WebM bytes labeled as audio/wav are corrected to audio/webm when sent to Gemini."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Where are the safest fishing zones today?"
        mock_client.models.generate_content.return_value = mock_response

        # WebM magic header
        webm_audio = b"\x1a\x45\xdf\xa3" + b"\x00" * 300
        result = transcribe_voice_query(webm_audio, mime_type="audio/wav")

        self.assertEqual(result, "Where are the safest fishing zones today?")
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args[1]
        contents = call_kwargs["contents"]
        # Verify that the Part was created with audio/webm despite declared audio/wav
        part = contents[0]
        self.assertEqual(part.inline_data.mime_type, "audio/webm")

    @patch("config.get_gemini_api_key", return_value="fake-api-key")
    @patch("app._get_voice_gemini_client")
    def test_transcribe_voice_query_exception_raised(self, mock_get_client, mock_get_key):
        """When Gemini API throws an exception, it is re-raised so caller can provide clear error feedback."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.models.generate_content.side_effect = RuntimeError("Connection timed out")

        with self.assertRaises(RuntimeError):
            transcribe_voice_query(b"RIFF....WAVEfmt " + b"\x00" * 200, mime_type="audio/wav")


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
