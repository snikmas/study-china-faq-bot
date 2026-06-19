from pathlib import Path

from pydantic import SecretStr

import app.config as config
from app.config import (
    DEFAULT_GEMINI_MODEL,
    AvailabilityCode,
    load_config,
)


def test_streamlit_secrets_take_precedence_over_environment() -> None:
    result = load_config(
        secrets={
            "GEMINI_API_KEY": "streamlit-placeholder",
            "GEMINI_MODEL": "model-from-secrets",
        },
        environ={
            "GEMINI_API_KEY": "environment-placeholder",
            "GEMINI_MODEL": "model-from-environment",
        },
    )

    assert result.chat_available is True
    assert result.settings.gemini_api_key == SecretStr("streamlit-placeholder")
    assert result.settings.gemini_model == "model-from-secrets"


def test_default_loader_reads_streamlit_secrets_before_process_environment(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        config,
        "_load_streamlit_secrets",
        lambda: {"GEMINI_API_KEY": "streamlit-placeholder"},
    )
    monkeypatch.setenv("GEMINI_API_KEY", "environment-placeholder")

    result = load_config()

    assert result.settings.gemini_api_key == SecretStr("streamlit-placeholder")


def test_environment_is_used_when_streamlit_secret_is_absent() -> None:
    result = load_config(
        secrets={},
        environ={"GEMINI_API_KEY": "environment-placeholder"},
    )

    assert result.chat_available is True
    assert result.settings.gemini_api_key == SecretStr("environment-placeholder")
    assert result.settings.gemini_model == DEFAULT_GEMINI_MODEL


def test_default_loader_reads_local_dotenv_file(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_load_streamlit_secrets", lambda: {})
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    tmp_path.joinpath(".env").write_text(
        "GEMINI_API_KEY" "=dotenv-placeholder\n"
        "GEMINI_MODEL=model-from-dotenv\n",
        encoding="utf-8",
    )

    result = load_config()

    assert result.chat_available is True
    assert result.settings.gemini_api_key == SecretStr("dotenv-placeholder")
    assert result.settings.gemini_model == "model-from-dotenv"


def test_copied_env_example_placeholders_do_not_enable_features(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "_load_streamlit_secrets", lambda: {})
    for key in (
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_OWNER_CHAT_ID",
        "AGENCY_CONTACT_FALLBACK",
    ):
        monkeypatch.delenv(key, raising=False)
    env_example = Path(__file__).resolve().parents[1] / ".env.example"
    tmp_path.joinpath(".env").write_text(
        env_example.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = load_config()

    assert result.chat_available is False
    assert result.chat.code is AvailabilityCode.INVALID_CONFIGURATION
    assert result.telegram_available is False
    assert result.telegram.code is AvailabilityCode.INVALID_CONFIGURATION
    assert result.settings.gemini_api_key is None
    assert result.settings.telegram_bot_token is None
    assert result.settings.telegram_owner_chat_id is None
    assert result.settings.agency_contact_fallback is None
    public_evidence = (
        f"{result.chat.message} {result.telegram.message} "
        f"{repr(result.settings)} {result.model_dump_json()}"
    )
    assert "your_gemini_api_key" not in public_evidence
    assert "your_telegram_bot_token" not in public_evidence
    assert "@your_agency_contact" not in public_evidence


def test_placeholder_streamlit_secret_does_not_fall_through_to_environment() -> None:
    result = load_config(
        secrets={"GEMINI_API_KEY": "your_gemini_api_key"},
        environ={"GEMINI_API_KEY": "environment-placeholder"},
    )

    assert result.chat_available is False
    assert result.chat.code is AvailabilityCode.INVALID_CONFIGURATION
    assert result.settings.gemini_api_key is None


def test_missing_gemini_disables_chat_without_disabling_explanatory_state() -> None:
    result = load_config(secrets={}, environ={})

    assert result.chat_available is False
    assert result.chat.code is AvailabilityCode.MISSING_CONFIGURATION
    assert result.chat.message == (
        "Chat is unavailable because Gemini is not configured."
    )
    assert result.settings.gemini_api_key is None


def test_complete_telegram_configuration_enables_inquiry_handoff() -> None:
    result = load_config(
        secrets={
            "TELEGRAM_BOT_TOKEN": "telegram-placeholder",
            "TELEGRAM_OWNER_CHAT_ID": "-123456",
            "AGENCY_CONTACT_FALLBACK": "@agency_support",
        },
        environ={},
    )

    assert result.telegram_available is True
    assert result.telegram.code is AvailabilityCode.AVAILABLE
    assert result.settings.telegram_bot_token == SecretStr("telegram-placeholder")
    assert result.settings.telegram_owner_chat_id == -123456
    assert result.settings.agency_contact_fallback == "@agency_support"
    assert result.chat_available is False


def test_incomplete_telegram_configuration_disables_only_inquiry_handoff() -> None:
    result = load_config(
        secrets={},
        environ={
            "GEMINI_API_KEY": "gemini-placeholder",
            "TELEGRAM_BOT_TOKEN": "telegram-placeholder",
        },
    )

    assert result.chat_available is True
    assert result.telegram_available is False
    assert result.telegram.code is AvailabilityCode.MISSING_CONFIGURATION


def test_invalid_chat_id_is_reported_without_exposing_configuration_values() -> None:
    private_token = "private-token-placeholder"
    invalid_chat_id = "owner-chat-id-placeholder"
    result = load_config(
        secrets={
            "TELEGRAM_BOT_TOKEN": private_token,
            "TELEGRAM_OWNER_CHAT_ID": invalid_chat_id,
            "AGENCY_CONTACT_FALLBACK": "contact@example.com",
        },
        environ={},
    )

    public_evidence = f"{result.telegram.code.value} {result.telegram.message}"
    assert result.telegram_available is False
    assert result.telegram.code is AvailabilityCode.INVALID_CONFIGURATION
    assert private_token not in public_evidence
    assert invalid_chat_id not in public_evidence
    assert private_token not in repr(result.settings)
    assert private_token not in result.model_dump_json()


def test_blank_streamlit_secret_does_not_fall_through_to_environment() -> None:
    result = load_config(
        secrets={"GEMINI_API_KEY": "   "},
        environ={"GEMINI_API_KEY": "environment-placeholder"},
    )

    assert result.chat_available is False
    assert result.settings.gemini_api_key is None
