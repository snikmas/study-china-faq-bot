from dataclasses import dataclass

import pytest

from app.models import Inquiry
from app.telegram import (
    TELEGRAM_MESSAGE_LIMIT,
    TelegramDeliveryState,
    TelegramHttpResponse,
    format_inquiry_message,
    send_inquiry_notification,
)


def make_inquiry(**overrides: object) -> Inquiry:
    values = {
        "name": "Alex",
        "contact": "alex@example.com",
        "study_level": "master",
        "program": "Computer Science",
        "timeline": "September 2027",
        "question": "Which documents should I prepare?",
        "interface_language": "en",
        "consent": True,
    }
    values.update(overrides)
    return Inquiry(**values)


@dataclass
class FakeClient:
    response: TelegramHttpResponse | None = None
    error: BaseException | None = None
    calls: list[tuple[str, dict[str, object], float]] | None = None

    def post_json(
        self,
        url: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
    ) -> TelegramHttpResponse:
        if self.calls is None:
            self.calls = []
        self.calls.append((url, payload, timeout_seconds))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def test_format_inquiry_message_uses_plain_bilingual_labels_and_bounds() -> None:
    inquiry = make_inquiry(question="x" * 500)
    message = format_inquiry_message(inquiry)

    assert len(message) <= TELEGRAM_MESSAGE_LIMIT
    assert "Name / Имя: Alex" in message
    assert "Contact / Контакт: alex@example.com" in message
    assert "Study level / Уровень обучения: Master / Магистратура" in message
    assert "Consent / Согласие: yes / да" in message
    assert "Question / Вопрос:" in message
    assert "<b>" not in message


def test_send_success_requires_http_200_and_ok_true() -> None:
    client = FakeClient(response=TelegramHttpResponse(200, '{"ok": true}'))

    result = send_inquiry_notification(
        make_inquiry(),
        bot_token="token",
        owner_chat_id=123,
        agency_contact_fallback="@agency_support",
        client=client,
        timeout_seconds=3.0,
    )

    assert result.state is TelegramDeliveryState.DELIVERED
    assert result.delivered is True
    assert result.retry_allowed is False
    assert result.manual_fallback is None
    assert client.calls is not None
    url, payload, timeout_seconds = client.calls[0]
    assert url == "https://api.telegram.org/bottoken/sendMessage"
    assert payload["chat_id"] == 123
    assert payload["disable_web_page_preview"] is True
    assert len(str(payload["text"])) <= TELEGRAM_MESSAGE_LIMIT
    assert timeout_seconds == 3.0


@pytest.mark.parametrize(
    "response",
    [
        TelegramHttpResponse(500, '{"ok": true}'),
        TelegramHttpResponse(200, '{"ok": false}'),
        TelegramHttpResponse(200, "not-json"),
    ],
)
def test_definite_failure_allows_retry_and_exposes_fallback(
    response: TelegramHttpResponse,
) -> None:
    result = send_inquiry_notification(
        make_inquiry(),
        bot_token="token",
        owner_chat_id=123,
        agency_contact_fallback="@agency_support",
        client=FakeClient(response=response),
    )

    assert result.state is TelegramDeliveryState.RETRYABLE_FAILURE
    assert result.delivered is False
    assert result.retry_allowed is True
    assert result.manual_fallback == "@agency_support"


@pytest.mark.parametrize("error", [TimeoutError("timed out"), ConnectionError("lost")])
def test_ambiguous_timeout_or_connection_loss_prevents_retry_and_exposes_fallback(
    error: BaseException,
) -> None:
    client = FakeClient(error=error)

    result = send_inquiry_notification(
        make_inquiry(),
        bot_token="token",
        owner_chat_id=123,
        agency_contact_fallback="@agency_support",
        client=client,
    )

    assert result.state is TelegramDeliveryState.AMBIGUOUS_FAILURE
    assert result.delivered is False
    assert result.retry_allowed is False
    assert result.manual_fallback == "@agency_support"
    assert client.calls is not None
    assert len(client.calls) == 1
