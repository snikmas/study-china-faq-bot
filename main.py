from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import streamlit as st
from pydantic import ValidationError

from app.classifier import GeminiFAQClassifier
from app.config import ConfigLoadResult, load_config
from app.knowledge import KnowledgeLoadError, LoadedKnowledge, load_knowledge
from app.lead import validate_inquiry
from app.models import FAQRecord, StudyLevel
from app.service import AnswerItem, AnswerResponse, AnswerStatus, Citation, resolve_answer
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

SAMPLE_FAQ_IDS: tuple[str, ...] = (
    "scholarship-categories",
    "csc-application-routes",
    "language-requirements",
    "application-documents",
)


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


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 880px;
        }
        div[data-testid="stToolbar"] {visibility: hidden; height: 0; position: fixed;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .faq-badge {
            display: inline-block;
            background: #E8F1FF;
            color: #1F6FEB;
            border: 1px solid #C9DEFF;
            border-radius: 999px;
            padding: 0.25rem 0.7rem;
            font-size: 0.84rem;
            font-weight: 600;
            margin-bottom: 0.55rem;
        }
        .faq-card {
            background: #FFFFFF;
            border: 1px solid #D9E2EC;
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 8px 24px rgba(20, 33, 43, 0.04);
            margin: 0.75rem 0 1rem 0;
        }
        .faq-card h4 {
            margin: 0 0 0.55rem 0;
            font-size: 1rem;
            color: #14212B;
        }
        .faq-meta {
            color: #627D98;
            font-size: 0.88rem;
            margin-bottom: 0.35rem;
        }
        .faq-answer {
            color: #243B53;
            line-height: 1.55;
            margin: 0.4rem 0 0.7rem 0;
        }
        .faq-source a {
            color: #1F6FEB;
            text-decoration: none;
        }
        .faq-source {
            font-size: 0.9rem;
            margin: 0.15rem 0;
        }
        .stButton > button[kind="primary"] {
            border-radius: 10px;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def example_faqs(knowledge: LoadedKnowledge | None) -> list[FAQRecord]:
    if knowledge is None:
        return []
    by_id = {faq.id: faq for faq in knowledge.faqs}
    ordered = [by_id[faq_id] for faq_id in SAMPLE_FAQ_IDS if faq_id in by_id]
    if ordered:
        return ordered
    return list(knowledge.faqs[:4])


def sample_response_from_faq(faq: FAQRecord, knowledge: LoadedKnowledge) -> AnswerResponse:
    sources = knowledge.sources_for(faq)
    citations = tuple(
        Citation(
            source_id=source.id,
            organization=source.organization,
            page_title=source.page_title,
            url=str(source.url),
            language=source.language.value,
            accessed_on=source.accessed_on.isoformat(),
        )
        for source in sources
    )
    item = AnswerItem(
        faq_id=faq.id,
        topic=faq.topic,
        answer_en=faq.answer.en,
        answer_ru=faq.answer.ru,
        risk=faq.risk.value,
        citations=citations,
    )
    if faq.risk.value == "human_confirmation_required":
        status = AnswerStatus.NEEDS_CONFIRMATION
    else:
        status = AnswerStatus.ANSWERED
    return AnswerResponse(status=status, items=(item,), reason="portfolio_sample")


def render_session_limits(language: str) -> None:
    remaining = calls_remaining(st.session_state)
    wait = cooldown_remaining(st.session_state, time.monotonic())
    left, right = st.columns(2)
    left.caption(text("calls_remaining", language, remaining=remaining, limit=CALL_LIMIT))
    if wait > 0:
        right.caption(text("cooldown_wait", language, seconds=wait))
    else:
        right.caption(text("cooldown_ready", language))


def render_item_card(item: AnswerItem, language: str) -> None:
    answer = item.answer_ru if language == "ru" else item.answer_en
    with st.container(border=True):
        st.markdown(f"**{text('answer_topic', language)}:** {item.topic}")
        st.write(answer)
        if item.citations:
            st.markdown(f"**{text('sources_title', language)}**")
            for citation in item.citations:
                st.markdown(
                    f"- [{citation.organization} — {citation.page_title}]({citation.url}) "
                    f"({citation.accessed_on})"
                )


def render_answer(response: AnswerResponse, language: str, *, sample: bool = False) -> None:
    if sample:
        st.caption(text("sample_answer_hint", language))

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
        render_item_card(item, language)


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


def set_example_question(question: str) -> None:
    st.session_state["question_text"] = question


def render_examples(language: str, faqs: Sequence[FAQRecord]) -> None:
    if not faqs:
        return
    st.markdown(f"**{text('examples_title', language)}**")
    cols = st.columns(2)
    for index, faq in enumerate(faqs):
        question = faq.question.ru if language == "ru" else faq.question.en
        label = question if len(question) <= 70 else question[:67] + "..."
        with cols[index % 2]:
            st.button(
                label,
                key=f"example_{faq.id}_{language}",
                use_container_width=True,
                on_click=set_example_question,
                args=(question,),
            )


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

    examples = example_faqs(knowledge_state.knowledge)
    render_examples(language, examples)

    if knowledge_state.available and knowledge_state.knowledge is not None and examples:
        if st.button(text("show_sample_answer", language), type="secondary"):
            sample_faq = examples[0]
            sample_question = (
                sample_faq.question.ru if language == "ru" else sample_faq.question.en
            )
            sample_response = sample_response_from_faq(sample_faq, knowledge_state.knowledge)
            st.session_state["preview_answer"] = {
                "question": sample_question,
                "response": sample_response,
                "language": language,
                "sample": True,
            }

    chat_ready = config.chat_available and knowledge_state.available
    with st.form("question_form", clear_on_submit=False):
        question = st.text_area(
            text("question_label", language),
            max_chars=QUESTION_LIMIT,
            help=text("question_help", language),
            key="question_text",
            height=110,
        )
        submitted = st.form_submit_button(
            text("submit", language),
            disabled=not chat_ready,
            type="primary",
        )

    if st.session_state.get("preview_answer") and not submitted:
        preview = st.session_state["preview_answer"]
        st.markdown(f"**Q:** {preview['question']}")
        render_answer(preview["response"], language, sample=True)

    if not submitted:
        return False

    st.session_state.pop("preview_answer", None)
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
        {"question": cleaned, "response": response, "language": language, "sample": False}
    )
    st.markdown(f"**Q:** {cleaned}")
    render_answer(response, language)
    return True


def render_answer_history(language: str, *, skip_latest: bool) -> None:
    answers = st.session_state.get("answers", [])
    entries = answers[:-1] if skip_latest else answers
    for entry in entries:
        question = entry["question"]
        response = entry["response"]
        with st.expander(question):
            render_answer(response, language, sample=bool(entry.get("sample")))


def level_options(language: str) -> Mapping[str, str]:
    return {
        StudyLevel.LANGUAGE_PROGRAM.value: text("level_language_program", language),
        StudyLevel.BACHELOR.value: text("level_bachelor", language),
        StudyLevel.MASTER.value: text("level_master", language),
        StudyLevel.DOCTORATE.value: text("level_doctorate", language),
        StudyLevel.OTHER.value: text("level_other", language),
    }


def render_inquiry_flow(language: str, config: ConfigLoadResult) -> None:
    # Hide unfinished/debug empty handoff from portfolio screenshots.
    if not config.telegram_available:
        st.divider()
        st.caption(text("inquiry_optional_note", language))
        return

    st.divider()
    st.subheader(text("inquiry_title", language))

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
        submitted = st.form_submit_button(text("send_inquiry", language), type="primary")

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
    st.set_page_config(
        page_title="Study in China FAQ",
        page_icon="📘",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    inject_styles()
    initialize_session(st.session_state)

    config = cached_config()
    knowledge_state = cached_knowledge()
    language = selected_language()

    st.markdown(
        f"<div class='faq-badge'>{text('product_badge', language)}</div>",
        unsafe_allow_html=True,
    )
    st.title(text("app_title", language))
    st.markdown(text("hero_subtitle", language))
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
