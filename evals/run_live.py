"""Optional live evaluation runner for the Gemini FAQ classifier."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.classifier import GeminiFAQClassifier
from app.config import ConfigLoadResult, load_config
from app.knowledge import KnowledgeLoadError, LoadedKnowledge, load_knowledge
from app.service import AnswerResponse, resolve_answer


CASES_PATH = PROJECT_ROOT / "evals" / "cases.json"
FAQ_PATH = PROJECT_ROOT / "faq.json"
SOURCES_PATH = PROJECT_ROOT / "sources.json"


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    question: str
    expected_status: str
    allowed_ids: tuple[str, ...]
    forbidden_ids: tuple[str, ...]
    requires_citation: bool
    factual_output_allowed: bool


@dataclass(frozen=True, slots=True)
class CaseFailure:
    case_id: str
    reasons: tuple[str, ...]


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


def _expect_string(value: object, field: str, case_id: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{case_id}: {field} must be a string")
    return value


def _expect_string_tuple(value: object, field: str, case_id: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{case_id}: {field} must be a list of strings")
    return tuple(value)


def _expect_bool(value: object, field: str, case_id: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{case_id}: {field} must be a boolean")
    return value


def parse_case(raw_case: Mapping[str, object]) -> EvaluationCase:
    case_id = _expect_string(raw_case.get("id"), "id", "<unknown>")
    return EvaluationCase(
        id=case_id,
        question=_expect_string(raw_case.get("question"), "question", case_id),
        expected_status=_expect_string(
            raw_case.get("expected_status"), "expected_status", case_id
        ),
        allowed_ids=_expect_string_tuple(
            raw_case.get("allowed_ids"), "allowed_ids", case_id
        ),
        forbidden_ids=_expect_string_tuple(
            raw_case.get("forbidden_ids"), "forbidden_ids", case_id
        ),
        requires_citation=_expect_bool(
            raw_case.get("requires_citation"), "requires_citation", case_id
        ),
        factual_output_allowed=_expect_bool(
            raw_case.get("factual_output_allowed"), "factual_output_allowed", case_id
        ),
    )


def load_cases(path: Path = CASES_PATH) -> tuple[EvaluationCase, ...]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError("eval cases file must contain a JSON list")
    cases: list[EvaluationCase] = []
    for index, raw_case in enumerate(payload):
        if not isinstance(raw_case, Mapping):
            raise ValueError(f"eval case at index {index} must be an object")
        cases.append(parse_case(raw_case))
    return tuple(cases)


def evaluate_case(case: EvaluationCase, response: AnswerResponse) -> tuple[str, ...]:
    reasons: list[str] = []
    returned_ids = tuple(item.faq_id for item in response.items)

    if response.status.value != case.expected_status:
        reasons.append(
            f"expected status {case.expected_status}, got {response.status.value}"
        )

    if case.allowed_ids:
        unexpected_ids = sorted(set(returned_ids) - set(case.allowed_ids))
        if not returned_ids:
            reasons.append(f"expected one of allowed IDs {sorted(case.allowed_ids)}")
        elif unexpected_ids:
            reasons.append(f"returned IDs outside allowed set: {unexpected_ids}")

    forbidden_matches = sorted(set(returned_ids) & set(case.forbidden_ids))
    if forbidden_matches:
        reasons.append(f"returned forbidden IDs: {forbidden_matches}")

    if case.requires_citation and any(not item.citations for item in response.items):
        reasons.append("returned an item without citations")

    if not case.factual_output_allowed and response.items:
        reasons.append("returned factual items for a no-factual-output case")

    return tuple(reasons)


def run_live_eval(
    *,
    config: ConfigLoadResult | None = None,
    knowledge: LoadedKnowledge | None = None,
    cases_path: Path = CASES_PATH,
    classifier_factory: Callable[[str, str], GeminiFAQClassifier] | None = None,
    output: TextIO = sys.stdout,
    error: TextIO = sys.stderr,
) -> int:
    config = config or load_config()
    api_key = config.settings.gemini_api_key
    if not config.chat_available or api_key is None:
        print(
            "Live evaluation requires a real GEMINI_API_KEY. "
            "Set GEMINI_API_KEY in .env or the environment before running.",
            file=error,
        )
        print(f"Config: {config.chat.code.value} - {config.chat.message}", file=error)
        return 2

    try:
        active_knowledge = knowledge or load_knowledge(FAQ_PATH, SOURCES_PATH)
        cases = load_cases(cases_path)
    except (OSError, ValueError, json.JSONDecodeError, KnowledgeLoadError) as exc:
        print(f"Live evaluation setup failed: {exc}", file=error)
        return 2

    if classifier_factory is None:
        classifier_factory = lambda key, model: GeminiFAQClassifier(
            GeminiGenerateContentAdapter(key), model=model
        )

    classifier = classifier_factory(
        api_key.get_secret_value(),
        config.settings.gemini_model,
    )

    failures: list[CaseFailure] = []
    for case in cases:
        classifier_result = classifier.classify(case.question, active_knowledge.faqs)
        response = resolve_answer(classifier_result, active_knowledge)
        reasons = evaluate_case(case, response)
        if reasons:
            failures.append(CaseFailure(case_id=case.id, reasons=reasons))

    passed = len(cases) - len(failures)
    print(f"Live eval: {passed}/{len(cases)} passed", file=output)
    for failure in failures:
        print(
            f"FAIL {failure.case_id}: {'; '.join(failure.reasons)}",
            file=output,
        )

    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    if argv not in (None, []):
        print("Usage: python evals/run_live.py", file=sys.stderr)
        return 2
    return run_live_eval()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
