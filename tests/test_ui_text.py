import pytest

from app.ui_text import normalize_language, text


def test_core_copy_exists_in_english_and_russian() -> None:
    assert "Study in China" in text("app_title", "en")
    assert "Китае" in text("app_title", "ru")
    assert "official citations" in text("trust_disclaimer", "en")
    assert "официальными источниками" in text("trust_disclaimer", "ru")
    assert text("submit", "en") == "Get answer"
    assert text("submit", "ru") == "Получить ответ"
    assert "CampusChina/CSC" in text("unsupported", "en")
    assert "выбор университета/города" in text("unsupported", "ru")
    assert "trust-first" in text("product_badge", "en")
    assert "Show sample answer" in text("show_sample_answer", "en")


def test_formatting_and_language_fallback() -> None:
    assert text("calls_remaining", "en", remaining=19, limit=20) == (
        "19/20 questions left"
    )
    assert text("calls_remaining", "ru", remaining=19, limit=20) == (
        "Вопросов осталось: 19/20"
    )
    assert normalize_language("de") == "en"
    assert text("submit", "de") == "Get answer"


def test_missing_key_raises_clear_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown UI text key: missing"):
        text("missing", "en")
