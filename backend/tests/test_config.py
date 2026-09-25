from __future__ import annotations

from app.config import gemini_key_is_plausible, normalize_gemini_key


def test_normalize_strips_quotes_and_inline_comment():
    assert normalize_gemini_key('  "AIzaSyRealKey1234567890"  ') == "AIzaSyRealKey1234567890"
    assert normalize_gemini_key("AIzaSyRealKey1234567890 # comment") == "AIzaSyRealKey1234567890"


def test_plausible_accepts_studio_style_key():
    assert gemini_key_is_plausible("AIzaSyDummyTestKeyForUnitTestsOnlyZZ") is True


def test_plausible_rejects_short_or_wrong_prefix():
    assert gemini_key_is_plausible("") is False
    assert gemini_key_is_plausible("sk-not-a-google-key-1234567890") is False
    assert gemini_key_is_plausible("AIzaShort") is False


def test_plausible_rejects_placeholders():
    assert gemini_key_is_plausible("AIzaSyYour_API_Key_HereXXXX") is False
    assert gemini_key_is_plausible("AIzaSyExamplePlaceholderKey1234") is False
    assert gemini_key_is_plausible("AIzaSyXXXXXXXXXXXXXXXXXXXX") is False
