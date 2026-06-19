import pytest

from app.ui_text import normalize_language, text


def test_core_copy_exists_in_english_and_russian() -> None:
    assert "Study in China" in text("app_title", "en")
    assert "Китае" in text("app_title", "ru")
    assert "official citations" in text("trust_disclaimer", "en")
    assert "официальными источниками" in text("trust_disclaimer", "ru")
    assert text("submit", "en") == "Ask"
    assert text("submit", "ru") == "Спросить"


def test_formatting_and_language_fallback() -> None:
    assert text("calls_remaining", "en", remaining=19, limit=20) == (
        "Questions remaining: 19 of 20"
    )
    assert text("calls_remaining", "ru", remaining=19, limit=20) == (
        "Осталось вопросов: 19 из 20"
    )
    assert normalize_language("de") == "en"
    assert text("submit", "de") == "Ask"


def test_missing_key_raises_clear_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown UI text key: missing"):
        text("missing", "en")
