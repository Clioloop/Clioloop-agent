#!/usr/bin/env python3
"""Interactive single and batched clarifying questions.

The tool owns validation and wire-format normalization. Platform layers provide
the UI callback. A batch-capable callback accepts ``questions=...`` and returns
either ``{"answers": {qid: value}}`` or the equivalent JSON string. Older
callbacks remain compatible and are called once per question.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Optional

from tools.registry import registry, tool_error

MAX_CHOICES = 4
MAX_QUESTIONS = 5


def _normalize_choices(value: Any) -> tuple[Optional[list[str]], Optional[str]]:
    if value is None:
        return None, None
    if not isinstance(value, list):
        return None, "choices must be a list of strings."
    choices = [str(item).strip() for item in value if str(item).strip()][:MAX_CHOICES]
    return choices or None, None


def _normalize_questions(value: Any) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
    if value is None:
        return None, None
    if not isinstance(value, list):
        return None, "questions must be a list of question objects."
    if not value:
        return None, "questions must contain at least one question."
    if len(value) > MAX_QUESTIONS:
        return None, f"questions supports at most {MAX_QUESTIONS} items."

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(value):
        if isinstance(raw, str):
            raw = {"question": raw}
        if not isinstance(raw, Mapping):
            return None, f"questions[{index}] must be an object."
        question = str(raw.get("question") or "").strip()
        if not question:
            return None, f"questions[{index}].question is required."
        choices, error = _normalize_choices(raw.get("choices"))
        if error:
            return None, f"questions[{index}].{error}"
        requested_id = str(raw.get("id") or raw.get("qid") or f"q{index}").strip()
        qid = requested_id or f"q{index}"
        if qid in seen_ids:
            return None, f"questions contains duplicate id {qid!r}."
        seen_ids.add(qid)
        normalized.append(
            {
                "qid": qid,
                "id": str(raw.get("id") or "").strip() or None,
                "question": question,
                "choices": choices,
                "multi_select": bool(raw.get("multi_select")) and bool(choices),
            }
        )
    return normalized, None


def _callback_accepts_batch(callback: Callable[..., Any]) -> bool:
    try:
        parameters = inspect.signature(callback).parameters
    except (TypeError, ValueError):
        return False
    return "questions" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


def _decode_batch_answers(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return {"q0": text}
    if isinstance(raw, Mapping):
        answers = raw.get("answers", raw)
        if isinstance(answers, Mapping):
            return {str(key): value for key, value in answers.items()}
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        return {f"q{index}": value for index, value in enumerate(raw)}
    return {}


def _clean_answer(value: Any, *, multi_select: bool) -> Any:
    if multi_select:
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                decoded = [part.strip() for part in value.split(",") if part.strip()]
            value = decoded
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []
    return str(value or "").strip()


def clarify_tool(
    question: str = "",
    choices: Optional[list[str]] = None,
    multi_select: bool = False,
    questions: Optional[list[Any]] = None,
    callback: Optional[Callable[..., Any]] = None,
) -> str:
    """Ask one question or up to five independent questions in one call."""
    normalized_batch, batch_error = _normalize_questions(questions)
    if batch_error:
        return tool_error(batch_error)
    if normalized_batch is not None and str(question or "").strip():
        return tool_error("Use either question/choices or questions, not both.")
    if normalized_batch is None and not str(question or "").strip():
        return tool_error("Question text is required.")
    if callback is None:
        return json.dumps(
            {"error": "Clarify tool is not available in this execution context."},
            ensure_ascii=False,
        )

    if normalized_batch is not None:
        try:
            if _callback_accepts_batch(callback):
                raw_answers = callback("", None, questions=normalized_batch)
                answers = _decode_batch_answers(raw_answers)
            else:
                answers = {
                    item["qid"]: callback(item["question"], item["choices"])
                    for item in normalized_batch
                }
        except Exception as exc:
            return json.dumps({"error": f"Failed to get user input: {exc}"}, ensure_ascii=False)

        responses = []
        ordered_answers: dict[str, Any] = {}
        for item in normalized_batch:
            answer = _clean_answer(
                answers.get(item["qid"]),
                multi_select=item["multi_select"],
            )
            ordered_answers[item["qid"]] = answer
            responses.append(
                {
                    "id": item["id"],
                    "qid": item["qid"],
                    "question": item["question"],
                    "choices_offered": item["choices"],
                    "multi_select": item["multi_select"],
                    "user_response": answer,
                }
            )
        return json.dumps(
            {"questions": normalized_batch, "answers": ordered_answers, "responses": responses},
            ensure_ascii=False,
        )

    normalized_choices, choices_error = _normalize_choices(choices)
    if choices_error:
        return tool_error(choices_error)
    clean_question = str(question).strip()
    try:
        user_response = callback(clean_question, normalized_choices)
    except Exception as exc:
        return json.dumps({"error": f"Failed to get user input: {exc}"}, ensure_ascii=False)
    return json.dumps(
        {
            "question": clean_question,
            "choices_offered": normalized_choices,
            "multi_select": bool(multi_select) and bool(normalized_choices),
            "user_response": _clean_answer(
                user_response,
                multi_select=bool(multi_select) and bool(normalized_choices),
            ),
        },
        ensure_ascii=False,
    )


def check_clarify_requirements() -> bool:
    return True


_QUESTION_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Optional stable question id."},
        "question": {"type": "string", "description": "Question text."},
        "choices": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": MAX_CHOICES,
        },
        "multi_select": {
            "type": "boolean",
            "description": "Allow several choices for this question.",
        },
    },
    "required": ["question"],
}

CLARIFY_SCHEMA = {
    "name": "clarify",
    "description": (
        "Ask the user one question, or batch up to five independent questions. "
        "For one question, provide question and optional choices. For a batch, "
        "provide questions and omit question. Use this only when missing input "
        "materially changes the action; prefer a reasonable default for low-stakes ambiguity."
    ),
    "parameters": {
        "type": "object",
        "anyOf": [{"required": ["question"]}, {"required": ["questions"]}],
        "properties": {
            "question": {"type": "string", "description": "One question to present."},
            "choices": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": MAX_CHOICES,
                "description": "Up to four choices for the single question.",
            },
            "multi_select": {
                "type": "boolean",
                "description": "Allow multiple choices for the single question.",
            },
            "questions": {
                "type": "array",
                "items": _QUESTION_ITEM_SCHEMA,
                "minItems": 1,
                "maxItems": MAX_QUESTIONS,
                "description": "Up to five independent questions shown as one batch.",
            },
        },
    },
}

registry.register(
    name="clarify",
    toolset="clarify",
    schema=CLARIFY_SCHEMA,
    handler=lambda args, **kw: clarify_tool(
        question=args.get("question", ""),
        choices=args.get("choices"),
        multi_select=args.get("multi_select", False),
        questions=args.get("questions"),
        callback=kw.get("callback"),
    ),
    check_fn=check_clarify_requirements,
    emoji="❓",
)
