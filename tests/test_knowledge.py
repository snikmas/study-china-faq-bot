import json
from datetime import date
from pathlib import Path

import pytest

from app.knowledge import KnowledgeLoadError, load_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAQ_PATH = PROJECT_ROOT / "faq.json"
SOURCES_PATH = PROJECT_ROOT / "sources.json"

EXPECTED_FAQ_IDS = [
    "scholarship-categories",
    "csc-application-routes",
    "cgs-eligibility",
    "language-requirements",
    "application-documents",
    "submission-location",
    "application-timing",
    "scholarship-coverage",
    "student-visas-x1-x2",
    "first-arrival-steps",
    "admission-scam-warnings",
    "document-translation",
    "hsk-framework",
    "hsk-admission-expectations",
    "russian-applicant-routing",
]


def read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_repository_knowledge_has_exact_approved_bilingual_scope() -> None:
    knowledge = load_knowledge(
        FAQ_PATH,
        SOURCES_PATH,
        current_utc_date=date(2026, 6, 12),
    )

    assert [record.id for record in knowledge.faqs] == EXPECTED_FAQ_IDS
    assert len(knowledge.faqs) == 15
    assert all(record.question.en and record.question.ru for record in knowledge.faqs)
    assert all(record.answer.en and record.answer.ru for record in knowledge.faqs)
    assert "стипендии" in knowledge.faqs[0].answer.ru


def test_every_reference_resolves_to_specific_https_source_metadata() -> None:
    knowledge = load_knowledge(
        FAQ_PATH,
        SOURCES_PATH,
        current_utc_date=date(2026, 6, 12),
    )

    referenced_ids = {
        source_id for record in knowledge.faqs for source_id in record.source_ids
    }
    assert referenced_ids <= knowledge.sources.keys()
    assert all(source.url.scheme == "https" for source in knowledge.sources.values())
    assert all(source.organization and source.page_title for source in knowledge.sources.values())
    assert all(source.accessed_on == date(2026, 6, 12) for source in knowledge.sources.values())

    for record in knowledge.faqs:
        assert tuple(source.id for source in knowledge.sources_for(record)) == tuple(
            record.source_ids
        )


def test_review_date_is_inclusive_and_record_expires_next_utc_day(
    tmp_path: Path,
) -> None:
    faq_payload = read_json(FAQ_PATH)
    faq_payload["faqs"][0]["review_by"] = "2026-06-12"  # type: ignore[index]
    faq_file = tmp_path / "faq.json"
    write_json(faq_file, faq_payload)

    on_review_date = load_knowledge(
        faq_file,
        SOURCES_PATH,
        current_utc_date=date(2026, 6, 12),
    )
    after_review_date = load_knowledge(
        faq_file,
        SOURCES_PATH,
        current_utc_date=date(2026, 6, 13),
    )

    assert EXPECTED_FAQ_IDS[0] in {record.id for record in on_review_date.faqs}
    assert EXPECTED_FAQ_IDS[0] not in {record.id for record in after_review_date.faqs}
    assert len(on_review_date.faqs) == 15
    assert len(after_review_date.faqs) == 14


def test_full_dataset_is_validated_before_expired_records_are_filtered(
    tmp_path: Path,
) -> None:
    faq_payload = read_json(FAQ_PATH)
    faq_payload["faqs"][0]["review_by"] = "2026-06-12"  # type: ignore[index]
    faq_payload["faqs"][0]["source_ids"] = ["missing-source"]  # type: ignore[index]
    faq_file = tmp_path / "faq.json"
    write_json(faq_file, faq_payload)

    with pytest.raises(KnowledgeLoadError, match="schema validation"):
        load_knowledge(
            faq_file,
            SOURCES_PATH,
            current_utc_date=date(2026, 6, 13),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["faqs"].pop(),
        lambda payload: payload["faqs"][1].update(
            {"id": payload["faqs"][0]["id"]}
        ),
        lambda payload: payload["faqs"][0]["question"].update({"ru": " "}),
    ],
)
def test_invalid_faq_dataset_is_rejected(
    tmp_path: Path,
    mutation,
) -> None:
    payload = read_json(FAQ_PATH)
    mutation(payload)
    faq_file = tmp_path / "faq.json"
    write_json(faq_file, payload)

    with pytest.raises(KnowledgeLoadError, match="schema validation"):
        load_knowledge(faq_file, SOURCES_PATH)


def test_invalid_source_data_and_malformed_json_are_rejected(tmp_path: Path) -> None:
    source_payload = read_json(SOURCES_PATH)
    source_payload["sources"][0]["url"] = "http://campuschina.org/not-https"  # type: ignore[index]
    sources_file = tmp_path / "sources.json"
    write_json(sources_file, source_payload)

    with pytest.raises(KnowledgeLoadError, match="schema validation"):
        load_knowledge(FAQ_PATH, sources_file)

    malformed_file = tmp_path / "faq.json"
    malformed_file.write_text('{"faqs": [', encoding="utf-8")

    with pytest.raises(KnowledgeLoadError, match="valid UTF-8 JSON"):
        load_knowledge(malformed_file, SOURCES_PATH)
