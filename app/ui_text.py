"""Bilingual UI copy for the Streamlit visitor flow."""

from __future__ import annotations

from typing import Literal


Language = Literal["en", "ru"]
DEFAULT_LANGUAGE: Language = "en"
SUPPORTED_LANGUAGES: tuple[Language, ...] = ("en", "ru")


COPY: dict[str, dict[Language, str]] = {
    "app_title": {
        "en": "Study in China FAQ assistant",
        "ru": "FAQ-помощник по учебе в Китае",
    },
    "language_label": {"en": "Language", "ru": "Язык"},
    "trust_disclaimer": {
        "en": (
            "This assistant only returns reviewed stored FAQ answers with official "
            "citations. It is general information, not legal, visa, or admission "
            "advice."
        ),
        "ru": (
            "Помощник показывает только проверенные сохраненные ответы FAQ с "
            "официальными источниками. Это общая информация, а не юридическая, "
            "визовая или приемная консультация."
        ),
    },
    "question_label": {"en": "Your question", "ru": "Ваш вопрос"},
    "question_help": {
        "en": "Maximum 500 characters.",
        "ru": "Максимум 500 символов.",
    },
    "submit": {"en": "Ask", "ru": "Спросить"},
    "session_status": {"en": "Session limits", "ru": "Лимиты сессии"},
    "calls_remaining": {
        "en": "Questions remaining: {remaining} of {limit}",
        "ru": "Осталось вопросов: {remaining} из {limit}",
    },
    "cooldown_ready": {"en": "Cooldown: ready", "ru": "Пауза: можно спросить"},
    "cooldown_wait": {
        "en": "Cooldown: wait {seconds:.1f}s",
        "ru": "Пауза: подождите {seconds:.1f} с",
    },
    "empty_question": {
        "en": "Enter a question before submitting.",
        "ru": "Введите вопрос перед отправкой.",
    },
    "question_too_long": {
        "en": "Question is too long. Please keep it under 500 characters.",
        "ru": "Вопрос слишком длинный. Ограничьте его 500 символами.",
    },
    "cooldown_blocked": {
        "en": "Please wait {seconds:.1f}s before asking another question.",
        "ru": "Подождите {seconds:.1f} с перед следующим вопросом.",
    },
    "limit_blocked": {
        "en": "The 20-question session allowance has been used.",
        "ru": "Лимит 20 вопросов за сессию исчерпан.",
    },
    "chat_unavailable": {
        "en": "Chat is unavailable because Gemini is not configured. No classifier call was made.",
        "ru": "Чат недоступен: Gemini не настроен. Запрос к классификатору не выполнялся.",
    },
    "knowledge_unavailable": {
        "en": "Stored FAQ knowledge could not be loaded safely. Chat is disabled until the data is fixed.",
        "ru": "Сохраненную базу FAQ не удалось безопасно загрузить. Чат отключен до исправления данных.",
    },
    "knowledge_empty": {
        "en": "No current reviewed FAQ answers are available. Chat is disabled.",
        "ru": "Нет актуальных проверенных ответов FAQ. Чат отключен.",
    },
    "thinking": {"en": "Checking the stored FAQ...", "ru": "Проверяю сохраненный FAQ..."},
    "answered": {"en": "Stored answer", "ru": "Сохраненный ответ"},
    "needs_confirmation": {
        "en": "Human confirmation recommended",
        "ru": "Рекомендуется подтверждение специалистом",
    },
    "risk_warning": {
        "en": "This topic can depend on your country, program, date, or documents. Confirm with the school or an advisor before acting.",
        "ru": "Ответ может зависеть от страны, программы, даты или документов. Перед действиями подтвердите информацию в вузе или у консультанта.",
    },
    "unsupported": {
        "en": (
            "I do not have a supported stored answer for that exact question. "
            "Try asking about scholarships, CampusChina/CSC routes, Type A/B, "
            "documents, deadlines, X1/X2 visas, arrival steps, HSK, scams, "
            "costs, safety, or choosing a university/city."
        ),
        "ru": (
            "Для этого точного вопроса нет поддержанного сохраненного ответа. "
            "Попробуйте спросить про стипендии, CampusChina/CSC, тип A/B, "
            "документы, сроки, визы X1/X2, первые шаги после приезда, HSK, "
            "мошенников, расходы, безопасность или выбор университета/города."
        ),
    },
    "temporary_failure": {
        "en": "The assistant could not safely resolve this question right now. Please try again later.",
        "ru": "Сейчас помощник не может безопасно обработать вопрос. Попробуйте позже.",
    },
    "citations": {"en": "Citations", "ru": "Источники"},
    "citation_line": {
        "en": "{organization}, {page_title}, {url}, accessed {accessed_on}",
        "ru": "{organization}, {page_title}, {url}, дата доступа: {accessed_on}",
    },
    "inquiry_title": {"en": "Request human follow-up", "ru": "Запросить связь со специалистом"},
    "inquiry_unavailable": {
        "en": "Inquiry handoff is not configured, so the contact form is hidden.",
        "ru": "Передача заявки не настроена, поэтому форма контакта скрыта.",
    },
    "name": {"en": "Name", "ru": "Имя"},
    "contact": {"en": "Email or Telegram username", "ru": "Email или имя пользователя Telegram"},
    "study_level": {"en": "Study level", "ru": "Уровень обучения"},
    "program": {"en": "Program of interest", "ru": "Интересующая программа"},
    "timeline": {"en": "Timeline", "ru": "Сроки"},
    "inquiry_question": {"en": "Question for follow-up", "ru": "Вопрос для связи"},
    "consent": {
        "en": "I consent to sending this inquiry to the agency contact.",
        "ru": "Я согласен(на) отправить эту заявку контактному лицу агентства.",
    },
    "send_inquiry": {"en": "Send inquiry", "ru": "Отправить заявку"},
    "inquiry_validation_error": {
        "en": "Please check the inquiry form fields.",
        "ru": "Проверьте поля формы заявки.",
    },
    "inquiry_delivered": {
        "en": "Inquiry sent. It will not be sent again in this session.",
        "ru": "Заявка отправлена. В этой сессии она не будет отправлена повторно.",
    },
    "inquiry_retryable": {
        "en": "Telegram did not accept the message. You can retry, or use the fallback contact: {fallback}",
        "ru": "Telegram не принял сообщение. Можно повторить или использовать запасной контакт: {fallback}",
    },
    "inquiry_ambiguous": {
        "en": "Delivery is ambiguous, so automatic retry is disabled. Use the fallback contact: {fallback}",
        "ru": "Статус доставки неясен, поэтому автоповтор отключен. Используйте запасной контакт: {fallback}",
    },
    "already_sent": {
        "en": "Inquiry already sent in this session.",
        "ru": "Заявка уже отправлена в этой сессии.",
    },
    "level_language_program": {"en": "Language program", "ru": "Языковая программа"},
    "level_bachelor": {"en": "Bachelor", "ru": "Бакалавриат"},
    "level_master": {"en": "Master", "ru": "Магистратура"},
    "level_doctorate": {"en": "Doctorate", "ru": "Докторантура"},
    "level_other": {"en": "Other", "ru": "Другое"},
}


def normalize_language(language: str | None) -> Language:
    if language in SUPPORTED_LANGUAGES:
        return language  # type: ignore[return-value]
    return DEFAULT_LANGUAGE


def text(key: str, language: str | None = DEFAULT_LANGUAGE, **values: object) -> str:
    """Return localized copy, falling back to English for unsupported languages."""

    try:
        translations = COPY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown UI text key: {key}") from exc

    lang = normalize_language(language)
    template = translations.get(lang) or translations[DEFAULT_LANGUAGE]
    return template.format(**values)


__all__ = [
    "COPY",
    "DEFAULT_LANGUAGE",
    "Language",
    "SUPPORTED_LANGUAGES",
    "normalize_language",
    "text",
]
