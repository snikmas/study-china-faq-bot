from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass

import streamlit as st
from pydantic import ValidationError

from app.classifier import GeminiFAQClassifier
from app.config import ConfigLoadResult, load_config
from app.knowledge import KnowledgeLoadError, LoadedKnowledge, load_knowledge
from app.lead import validate_inquiry
from app.models import StudyLevel
from app.service import AnswerResponse, AnswerStatus, resolve_answer
from app.session import (
    CALL_LIMIT,
    QUESTION_LIMIT,
    calls_remaining,
    can_call,
    clean_question,
    cooldown_remaining,
    initialize_session,
    question_error,
    record_call,
)
from app.telegram import TelegramDeliveryState, send_inquiry_notification
from app.ui_text import SUPPORTED_LANGUAGES, normalize_language, text


@dataclass(frozen=True, slots=True)
class KnowledgeState:
    knowledge: LoadedKnowledge | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.knowledge is not None and bool(self.knowledge.faqs)


class GeminiGenerateContentAdapter:
    """Adapt google-genai's models API to the classifier protocol."""

    def __init__(self, api_key: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)

    def classify(
        self,
        *,
        model: str,
        system_instruction: str,
        contents: str,
    ) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
            contents=contents,
        )
        return response.text or ""


@st.cache_resource
def cached_config() -> ConfigLoadResult:
    return load_config()


@st.cache_resource
def cached_knowledge() -> KnowledgeState:
    try:
        knowledge = load_knowledge()
    except KnowledgeLoadError:
        return KnowledgeState(knowledge=None, error="invalid")
    if not knowledge.faqs:
        return KnowledgeState(knowledge=knowledge, error="empty")
    return KnowledgeState(knowledge=knowledge)


@st.cache_resource
def cached_classifier(api_key: str, model: str) -> GeminiFAQClassifier:
    return GeminiFAQClassifier(GeminiGenerateContentAdapter(api_key), model=model)


def selected_language() -> str:
    labels = {"en": "English", "ru": "Русский"}
    current_language = normalize_language(st.session_state.get("language"))
    choice = st.sidebar.radio(
        text("language_label", current_language),
        options=list(SUPPORTED_LANGUAGES),
        format_func=lambda value: labels[value],
        horizontal=True,
        key="language",
    )
    return normalize_language(choice)


def render_session_limits(language: str) -> None:
    remaining = calls_remaining(st.session_state)
    wait = cooldown_remaining(st.session_state, time.monotonic())
    st.caption(text("session_status", language))
    st.caption(text("calls_remaining", language, remaining=remaining, limit=CALL_LIMIT))
    if wait > 0:
        st.caption(text("cooldown_wait", language, seconds=wait))
    else:
        st.caption(text("cooldown_ready", language))


def render_citations(item: object, language: str) -> None:
    citations = getattr(item, "citations")
    if not citations:
        return
    st.markdown(f"**{text('citations', language)}**")
    for citation in citations:
        st.markdown(
            "- "
            + text(
                "citation_line",
                language,
                organization=citation.organization,
                page_title=citation.page_title,
                url=citation.url,
                accessed_on=citation.accessed_on,
            )
        )


def render_answer(response: AnswerResponse, language: str) -> None:
    if response.status is AnswerStatus.ANSWERED:
        st.success(text("answered", language))
    elif response.status is AnswerStatus.NEEDS_CONFIRMATION:
        st.warning(text("needs_confirmation", language))
        st.warning(text("risk_warning", language))
    elif response.status is AnswerStatus.UNSUPPORTED:
        st.info(text("unsupported", language))
        return
    else:
        st.error(text("temporary_failure", language))
        return

    for item in response.items:
        answer = item.answer_ru if language == "ru" else item.answer_en
        st.markdown(answer)
        render_citations(item, language)


def answer_question(
    *,
    config: ConfigLoadResult,
    knowledge: LoadedKnowledge,
    question: str,
) -> AnswerResponse:
    api_key = config.settings.gemini_api_key
    if api_key is None:
        return AnswerResponse(status=AnswerStatus.TEMPORARY_FAILURE)
    classifier = cached_classifier(
        api_key.get_secret_value(),
        config.settings.gemini_model,
    )
    classifier_result = classifier.classify(question, knowledge.faqs)
    return resolve_answer(classifier_result, knowledge)


def render_question_flow(
    *,
    language: str,
    config: ConfigLoadResult,
    knowledge_state: KnowledgeState,
) -> bool:
    render_session_limits(language)

    if not config.chat_available:
        st.warning(text("chat_unavailable", language))
    if knowledge_state.error == "invalid":
        st.error(text("knowledge_unavailable", language))
    elif knowledge_state.error == "empty":
        st.warning(text("knowledge_empty", language))

    chat_ready = config.chat_available and knowledge_state.available
    with st.form("question_form", clear_on_submit=False):
        question = st.text_area(
            text("question_label", language),
            max_chars=QUESTION_LIMIT,
            help=text("question_help", language),
            key="question_text",
        )
        submitted = st.form_submit_button(text("submit", language), disabled=not chat_ready)

    if not submitted:
        return False

    cleaned = clean_question(question)
    error = question_error(cleaned)
    if error == "empty":
        st.warning(text("empty_question", language))
        return False
    if error == "too_long":
        st.warning(text("question_too_long", language))
        return False
    if not chat_ready or knowledge_state.knowledge is None:
        return False

    now = time.monotonic()
    allowed, reason, wait = can_call(st.session_state, now)
    if not allowed:
        if reason == "limit":
            st.warning(text("limit_blocked", language))
        else:
            st.warning(text("cooldown_blocked", language, seconds=wait))
        return False

    record_call(st.session_state, now)
    with st.spinner(text("thinking", language)):
        response = answer_question(
            config=config,
            knowledge=knowledge_state.knowledge,
            question=cleaned,
        )

    st.session_state["answers"].append(
        {"question": cleaned, "response": response, "language": language}
    )
    render_answer(response, language)
    return True


def render_answer_history(language: str, *, skip_latest: bool) -> None:
    answers = st.session_state.get("answers", [])
    entries = answers[:-1] if skip_latest else answers
    for entry in entries:
        question = entry["question"]
        response = entry["response"]
        with st.expander(question):
            render_answer(response, language)


def level_options(language: str) -> Mapping[str, str]:
    return {
        StudyLevel.LANGUAGE_PROGRAM.value: text("level_language_program", language),
        StudyLevel.BACHELOR.value: text("level_bachelor", language),
        StudyLevel.MASTER.value: text("level_master", language),
        StudyLevel.DOCTORATE.value: text("level_doctorate", language),
        StudyLevel.OTHER.value: text("level_other", language),
    }


def render_inquiry_flow(language: str, config: ConfigLoadResult) -> None:
    st.divider()
    st.subheader(text("inquiry_title", language))
    if not config.telegram_available:
        st.caption(text("inquiry_unavailable", language))
        return

    if st.session_state.get("inquiry_sent") is True:
        st.success(text("already_sent", language))
        return

    if st.session_state.get("inquiry_ambiguous") is True:
        fallback = config.settings.agency_contact_fallback or ""
        st.warning(text("inquiry_ambiguous", language, fallback=fallback))
        return

    options = level_options(language)
    with st.form("inquiry_form", clear_on_submit=False):
        name = st.text_input(text("name", language), max_chars=80)
        contact = st.text_input(text("contact", language), max_chars=120)
        study_level = st.selectbox(
            text("study_level", language),
            options=list(options.keys()),
            format_func=lambda value: options[value],
        )
        program = st.text_input(text("program", language), max_chars=120)
        timeline = st.text_input(text("timeline", language), max_chars=80)
        inquiry_question = st.text_area(
            text("inquiry_question", language),
            max_chars=QUESTION_LIMIT,
        )
        consent = st.checkbox(text("consent", language))
        submitted = st.form_submit_button(text("send_inquiry", language))

    if not submitted:
        return

    try:
        inquiry = validate_inquiry(
            {
                "name": name,
                "contact": contact,
                "study_level": study_level,
                "program": program,
                "timeline": timeline,
                "question": inquiry_question,
                "interface_language": language,
                "consent": consent,
            }
        )
    except ValidationError:
        st.warning(text("inquiry_validation_error", language))
        return

    token = config.settings.telegram_bot_token
    owner_chat_id = config.settings.telegram_owner_chat_id
    fallback = config.settings.agency_contact_fallback
    if token is None or owner_chat_id is None or fallback is None:
        st.caption(text("inquiry_unavailable", language))
        return

    result = send_inquiry_notification(
        inquiry,
        bot_token=token.get_secret_value(),
        owner_chat_id=owner_chat_id,
        agency_contact_fallback=fallback,
    )
    if result.state is TelegramDeliveryState.DELIVERED:
        st.session_state["inquiry_sent"] = True
        st.success(text("inquiry_delivered", language))
    elif result.state is TelegramDeliveryState.AMBIGUOUS_FAILURE:
        st.session_state["inquiry_ambiguous"] = True
        st.warning(text("inquiry_ambiguous", language, fallback=fallback))
    else:
        st.warning(text("inquiry_retryable", language, fallback=fallback))


def main() -> None:
    st.set_page_config(page_title="Study in China FAQ", page_icon="CN")
    initialize_session(st.session_state)

    config = cached_config()
    knowledge_state = cached_knowledge()
    language = selected_language()

    st.title(text("app_title", language))
    st.info(text("trust_disclaimer", language))

    rendered_current_answer = render_question_flow(
        language=language,
        config=config,
        knowledge_state=knowledge_state,
    )
    render_answer_history(language, skip_latest=rendered_current_answer)
    render_inquiry_flow(language, config)


if __name__ == "__main__":
    main()
