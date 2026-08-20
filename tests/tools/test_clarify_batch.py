"""Regression tests for Clio's backward-compatible batch clarify contract."""

import json

from tools.clarify_tool import CLARIFY_SCHEMA, MAX_QUESTIONS, clarify_tool


def test_batch_callback_receives_one_normalized_form():
    received = []

    def callback(question, choices, *, questions=None):
        received.append((question, choices, questions))
        return {"answers": {"environment": "Production", "q1": "After approval"}}

    result = json.loads(
        clarify_tool(
            questions=[
                {
                    "id": "environment",
                    "question": "Where?",
                    "choices": ["Staging", "Production"],
                },
                {"question": "Notes?"},
            ],
            callback=callback,
        )
    )

    assert len(received) == 1
    assert received[0][2][0]["qid"] == "environment"
    assert result["answers"] == {
        "environment": "Production",
        "q1": "After approval",
    }
    assert [row["question"] for row in result["responses"]] == ["Where?", "Notes?"]


def test_batch_old_callback_falls_back_to_ordered_questions():
    asked = []

    def callback(question, choices):
        asked.append((question, choices))
        return str(len(asked))

    result = json.loads(
        clarify_tool(
            questions=["First?", {"question": "Second?", "choices": ["A", "B"]}],
            callback=callback,
        )
    )

    assert asked == [("First?", None), ("Second?", ["A", "B"])]
    assert result["answers"] == {"q0": "1", "q1": "2"}


def test_batch_multiselect_normalizes_json_or_csv_answers():
    result = json.loads(
        clarify_tool(
            questions=[
                {
                    "id": "features",
                    "question": "Choose features",
                    "choices": ["A", "B", "C"],
                    "multi_select": True,
                }
            ],
            callback=lambda _q, _c, **_kw: {
                "answers": {"features": '["A", "C"]'}
            },
        )
    )
    assert result["answers"]["features"] == ["A", "C"]


def test_batch_validation_is_bounded_and_mutually_exclusive():
    too_many = [{"question": str(index)} for index in range(MAX_QUESTIONS + 1)]
    assert "at most" in json.loads(clarify_tool(questions=too_many, callback=lambda *_a: ""))["error"]
    assert "either" in json.loads(
        clarify_tool(question="One?", questions=[{"question": "Two?"}], callback=lambda *_a: "")
    )["error"]


def test_schema_keeps_single_mode_and_adds_bounded_batch_mode():
    properties = CLARIFY_SCHEMA["parameters"]["properties"]
    assert {"question", "choices", "multi_select", "questions"} <= set(properties)
    assert properties["questions"]["maxItems"] == MAX_QUESTIONS
    assert {tuple(item["required"]) for item in CLARIFY_SCHEMA["parameters"]["anyOf"]} == {
        ("question",),
        ("questions",),
    }
