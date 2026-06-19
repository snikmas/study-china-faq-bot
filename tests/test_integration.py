from datetime import date

from app.classifier import parse_classifier_output
from app.knowledge import LoadedKnowledge, load_knowledge
from app.service import AnswerStatus, resolve_answer
from app.telegram import TelegramDeliveryState, TelegramHttpResponse, send_inquiry_notification
from app.models import Inquiry


def test_known_match_resolves_to_stored_cited_answer() -> None:
    knowledge = load_knowledge(current_utc_date=date(2026, 6, 19))
    result = parse_classifier_output(
        '{"match_status":"matched","matches":[{"faq_id":"scholarship-categories","confidence":0.91}]}'
    )

    response = resolve_answer(result, knowledge)

    assert response.status is AnswerStatus.ANSWERED
    assert response.items
    assert "scholarship" in response.items[0].answer_en.lower()
    assert response.items[0].citations


def test_injected_classifier_output_does_not_render_factual_answer() -> None:
    knowledge = load_knowledge(current_utc_date=date(2026, 6, 19))
    result = parse_classifier_output(
        '{"match_status":"matched","matches":[{"faq_id":"scholarship-categories","confidence":0.95}],"answer":"made up"}'
    )

    response = resolve_answer(result, knowledge)

    assert response.status is AnswerStatus.TEMPORARY_FAILURE
    assert response.items == ()


class FakeTelegramClient:
    def post_json(self, url: str, payload: dict[str, object], *, timeout_seconds: float) -> TelegramHttpResponse:
        assert "sendMessage" in url
        assert payload["text"]
        return TelegramHttpResponse(200, '{"ok": true}')


def test_valid_inquiry_can_be_sent_without_local_persistence() -> None:
    inquiry = Inquiry(
        name="Alex",
        contact="@valid_user",
        study_level="master",
        program="Computer Science",
        timeline="2027",
        question="Which documents should I prepare?",
        interface_language="en",
        consent=True,
    )

    result = send_inquiry_notification(
        inquiry,
        bot_token="token",
        owner_chat_id=123,
        agency_contact_fallback="@agency",
        client=FakeTelegramClient(),
    )

    assert result.state is TelegramDeliveryState.DELIVERED
