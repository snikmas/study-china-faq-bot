import json
from collections import Counter
from io import StringIO
from pathlib import Path

from app.classifier import parse_classifier_output
from app.config import load_config
from app.knowledge import load_knowledge
from app.service import resolve_answer
from evals.run_live import EvaluationCase, evaluate_case, run_live_eval


CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "cases.json"


def test_evaluation_corpus_shape_and_counts() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    assert len(cases) >= 30
    assert len({case["id"] for case in cases}) == len(cases)

    required = {
        "id",
        "language",
        "question",
        "expected_status",
        "allowed_ids",
        "forbidden_ids",
        "requires_citation",
        "factual_output_allowed",
    }
    counts = Counter(case["expected_status"] for case in cases)
    for case in cases:
        assert required <= case.keys()
        assert case["language"] in {"en", "ru"}
        assert case["expected_status"] in {
            "answered",
            "needs_confirmation",
            "unsupported",
            "temporary_failure",
        }
        assert isinstance(case["allowed_ids"], list)
        assert isinstance(case["forbidden_ids"], list)
        assert isinstance(case["requires_citation"], bool)
        assert isinstance(case["factual_output_allowed"], bool)

    assert counts["answered"] >= 4
    assert counts["needs_confirmation"] >= 8
    assert counts["unsupported"] >= 14


def test_unsupported_eval_cases_forbid_factual_output() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    unsupported = [case for case in cases if case["expected_status"] == "unsupported"]

    assert unsupported
    assert all(case["factual_output_allowed"] is False for case in unsupported)
    assert all(case["requires_citation"] is False for case in unsupported)


def test_live_eval_requires_credentials_before_model_calls() -> None:
    output = StringIO()
    error = StringIO()

    exit_code = run_live_eval(
        config=load_config(secrets={}, environ={}),
        output=output,
        error=error,
    )

    assert exit_code != 0
    assert "GEMINI_API_KEY" in error.getvalue()
    assert output.getvalue() == ""


def test_live_eval_case_checks_returned_allowed_and_forbidden_ids() -> None:
    knowledge = load_knowledge()
    response = resolve_answer(
        parse_classifier_output(
            '{"match_status":"matched","matches":[{"faq_id":"scholarship-categories","confidence":0.91}]}'
        ),
        knowledge,
    )

    passing_case = EvaluationCase(
        id="case-ok",
        question="What scholarships are available?",
        expected_status="answered",
        allowed_ids=("scholarship-categories",),
        forbidden_ids=(),
        requires_citation=True,
        factual_output_allowed=True,
    )
    failing_case = EvaluationCase(
        id="case-bad",
        question="Do not return scholarship.",
        expected_status="answered",
        allowed_ids=("csc-application-routes",),
        forbidden_ids=("scholarship-categories",),
        requires_citation=True,
        factual_output_allowed=False,
    )

    assert evaluate_case(passing_case, response) == ()
    failures = evaluate_case(failing_case, response)
    assert any("outside allowed" in failure for failure in failures)
    assert any("forbidden" in failure for failure in failures)
    assert any("no-factual-output" in failure for failure in failures)
