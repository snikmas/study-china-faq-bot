"""Feature-aware configuration loading with safe public states."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class AvailabilityCode(str, Enum):
    AVAILABLE = "available"
    MISSING_CONFIGURATION = "missing_configuration"
    INVALID_CONFIGURATION = "invalid_configuration"


class FeatureAvailability(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    code: AvailabilityCode
    message: str


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gemini_api_key: SecretStr | None
    gemini_model: str
    telegram_bot_token: SecretStr | None
    telegram_owner_chat_id: int | None
    agency_contact_fallback: str | None


class ConfigLoadResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    settings: RuntimeSettings
    chat: FeatureAvailability
    telegram: FeatureAvailability

    @property
    def chat_available(self) -> bool:
        return self.chat.available

    @property
    def telegram_available(self) -> bool:
        return self.telegram.available


def _load_streamlit_secrets() -> Mapping[str, Any]:
    try:
        import streamlit as st

        return st.secrets
    except Exception:
        return {}


def _read_setting(
    key: str,
    secrets: Mapping[str, Any],
    environ: Mapping[str, str],
) -> Any:
    try:
        if key in secrets:
            return secrets[key]
    except Exception:
        pass
    return environ.get(key)


def _clean_text(value: Any, *, max_length: int | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or (max_length is not None and len(cleaned) > max_length):
        return None
    return cleaned


def _parse_chat_id(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not re.fullmatch(r"[+-]?\d+", cleaned):
        return None
    return int(cleaned)


def load_config(
    *,
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ConfigLoadResult:
    """Load settings without raising user-facing secret-bearing errors."""

    secret_values = _load_streamlit_secrets() if secrets is None else secrets
    environment = os.environ if environ is None else environ

    raw_gemini_key = _read_setting(
        "GEMINI_API_KEY", secret_values, environment
    )
    raw_gemini_model = _read_setting(
        "GEMINI_MODEL", secret_values, environment
    )
    raw_telegram_token = _read_setting(
        "TELEGRAM_BOT_TOKEN", secret_values, environment
    )
    raw_owner_chat_id = _read_setting(
        "TELEGRAM_OWNER_CHAT_ID", secret_values, environment
    )
    raw_fallback = _read_setting(
        "AGENCY_CONTACT_FALLBACK", secret_values, environment
    )

    gemini_key = _clean_text(raw_gemini_key)
    gemini_model = (
        _clean_text(raw_gemini_model, max_length=100) or DEFAULT_GEMINI_MODEL
    )
    telegram_token = _clean_text(raw_telegram_token)
    owner_chat_id = _parse_chat_id(raw_owner_chat_id)
    fallback = _clean_text(raw_fallback, max_length=500)

    if gemini_key:
        chat = FeatureAvailability(
            available=True,
            code=AvailabilityCode.AVAILABLE,
            message="Chat is available.",
        )
    else:
        chat_code = (
            AvailabilityCode.INVALID_CONFIGURATION
            if raw_gemini_key not in (None, "")
            else AvailabilityCode.MISSING_CONFIGURATION
        )
        chat = FeatureAvailability(
            available=False,
            code=chat_code,
            message="Chat is unavailable because Gemini is not configured.",
        )

    telegram_values = (
        raw_telegram_token,
        raw_owner_chat_id,
        raw_fallback,
    )
    telegram_has_any_value = any(value not in (None, "") for value in telegram_values)
    telegram_has_invalid_value = (
        (raw_telegram_token not in (None, "") and telegram_token is None)
        or (raw_owner_chat_id not in (None, "") and owner_chat_id is None)
        or (raw_fallback not in (None, "") and fallback is None)
    )

    if telegram_token and owner_chat_id is not None and fallback:
        telegram = FeatureAvailability(
            available=True,
            code=AvailabilityCode.AVAILABLE,
            message="Inquiry handoff is available.",
        )
    elif telegram_has_invalid_value:
        telegram = FeatureAvailability(
            available=False,
            code=AvailabilityCode.INVALID_CONFIGURATION,
            message="Inquiry handoff is unavailable because Telegram configuration is invalid.",
        )
    else:
        telegram = FeatureAvailability(
            available=False,
            code=AvailabilityCode.MISSING_CONFIGURATION,
            message=(
                "Inquiry handoff is unavailable because Telegram is not fully configured."
                if telegram_has_any_value
                else "Inquiry handoff is unavailable because Telegram is not configured."
            ),
        )

    settings = RuntimeSettings(
        gemini_api_key=SecretStr(gemini_key) if gemini_key else None,
        gemini_model=gemini_model,
        telegram_bot_token=SecretStr(telegram_token) if telegram_token else None,
        telegram_owner_chat_id=owner_chat_id,
        agency_contact_fallback=fallback,
    )
    return ConfigLoadResult(settings=settings, chat=chat, telegram=telegram)
