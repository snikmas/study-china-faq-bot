import json
from collections import Counter
from pathlib import Path


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
