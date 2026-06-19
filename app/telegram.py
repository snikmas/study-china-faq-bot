"""Bounded Telegram inquiry handoff with explicit delivery outcomes."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.lead import summarize_inquiry
from app.models import Inquiry


TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_API_ROOT = "https://api.telegram.org"
DEFAULT_TIMEOUT_SECONDS = 10.0


class TelegramDeliveryState(str, Enum):
    DELIVERED = "delivered"
    RETRYABLE_FAILURE = "retryable_failure"
    AMBIGUOUS_FAILURE = "ambiguous_failure"


@dataclass(frozen=True, slots=True)
class TelegramHttpResponse:
    status_code: int
    body: str


class TelegramDeliveryClient(Protocol):
    def post_json(
        self,
        url: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
    ) -> TelegramHttpResponse:
        """Send JSON and return the HTTP status plus response body."""


@dataclass(frozen=True, slots=True)
class TelegramDeliveryResult:
    state: TelegramDeliveryState
    retry_allowed: bool
    manual_fallback: str | None
    detail: str

    @property
    def delivered(self) -> bool:
        return self.state is TelegramDeliveryState.DELIVERED


class UrllibTelegramClient:
    """Small stdlib client; tests use fakes and do not call the network."""

    def post_json(
        self,
        url: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
    ) -> TelegramHttpResponse:
        encoded = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                return TelegramHttpResponse(status_code=response.status, body=body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return TelegramHttpResponse(status_code=exc.code, body=body)


def _clip(value: str, max_length: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 1]}..."


def _line(label_en: str, label_ru: str, value: str) -> str:
    return f"{label_en} / {label_ru}: {value}"


def format_inquiry_message(inquiry: Inquiry) -> str:
    """Build a bounded plain-text bilingual Telegram notification."""

    summary = summarize_inquiry(inquiry)
    program = summary.program or "Not specified / Не указано"
    lines = [
        "New study inquiry / Новая заявка на обучение",
        _line("Name", "Имя", _clip(summary.name, 80)),
        _line("Contact", "Контакт", _clip(summary.contact, 120)),
        _line(
            "Study level",
            "Уровень обучения",
            f"{summary.study_level_en} / {summary.study_level_ru}",
        ),
        _line("Program", "Программа", _clip(program, 120)),
        _line("Timeline", "Сроки", _clip(summary.timeline, 80)),
        _line(
            "Interface language",
            "Язык интерфейса",
            f"{summary.interface_language_en} / {summary.interface_language_ru}",
        ),
        _line("Consent", "Согласие", "yes / да"),
        _line("Question", "Вопрос", _clip(summary.question, 500)),
    ]
    message = "\n".join(lines)
    if len(message) <= TELEGRAM_MESSAGE_LIMIT:
        return message
    return message[: TELEGRAM_MESSAGE_LIMIT - 3].rstrip() + "..."


def _telegram_ok(response: TelegramHttpResponse) -> bool:
    if response.status_code != 200:
        return False
    try:
        data = json.loads(response.body)
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and data.get("ok") is True


def send_inquiry_notification(
    inquiry: Inquiry,
    *,
    bot_token: str,
    owner_chat_id: int,
    agency_contact_fallback: str,
    client: TelegramDeliveryClient | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> TelegramDeliveryResult:
    """Send one Telegram notification and classify the delivery outcome."""

    sender = client or UrllibTelegramClient()
    message = format_inquiry_message(inquiry)
    url = f"{TELEGRAM_API_ROOT}/bot{bot_token}/sendMessage"
    payload: dict[str, object] = {
        "chat_id": owner_chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = sender.post_json(
            url,
            payload,
            timeout_seconds=timeout_seconds,
        )
    except (TimeoutError, ConnectionError, OSError):
        return TelegramDeliveryResult(
            state=TelegramDeliveryState.AMBIGUOUS_FAILURE,
            retry_allowed=False,
            manual_fallback=agency_contact_fallback,
            detail=(
                "Telegram delivery is ambiguous; use the manual fallback before "
                "sending again."
            ),
        )

    if _telegram_ok(response):
        return TelegramDeliveryResult(
            state=TelegramDeliveryState.DELIVERED,
            retry_allowed=False,
            manual_fallback=None,
            detail="Telegram accepted the inquiry notification.",
        )

    return TelegramDeliveryResult(
        state=TelegramDeliveryState.RETRYABLE_FAILURE,
        retry_allowed=True,
        manual_fallback=agency_contact_fallback,
        detail="Telegram rejected the notification or returned an invalid response.",
    )


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "TELEGRAM_MESSAGE_LIMIT",
    "TelegramDeliveryClient",
    "TelegramDeliveryResult",
    "TelegramDeliveryState",
    "TelegramHttpResponse",
    "UrllibTelegramClient",
    "format_inquiry_message",
    "send_inquiry_notification",
]
