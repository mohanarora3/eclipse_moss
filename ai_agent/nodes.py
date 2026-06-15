from typing import Any, Dict, List
from .state import DiagnosticState
from .llm import LLMClient
from .prompts import (
    symptom_understanding_prompt,
    query_regenerator_prompt,
    relevance_grader_prompt,
    hypothesis_prompt,
    question_generation_prompt,
    testing_prompt,
    corrective_action_prompt,
    citation_prompt,
)
from .utils import parse_json_response
from .moss_client import retrieve_moss_contexts


async def _render_prompt(prompt_template, **kwargs) -> str:
    llm = LLMClient()
    messages = prompt_template.format_prompt(**kwargs).to_messages()
    return await llm.generate(messages)


async def symptom_understanding_node(state: DiagnosticState) -> DiagnosticState:
    response = await _render_prompt(symptom_understanding_prompt, user_query=state["user_query"])
    state["symptoms"] = parse_json_response(response)
    return state


async def query_regenerator_node(state: DiagnosticState) -> DiagnosticState:
    response = await _render_prompt(query_regenerator_prompt, symptoms=state["symptoms"])
    output = parse_json_response(response)
    if isinstance(output, list):
        state["retrieval_queries"] = output
    elif isinstance(output, dict):
        state["retrieval_queries"] = output.get("queries", [])
    else:
        state["retrieval_queries"] = []
    return state


def _summarize_docs(docs: List[Dict[str, Any]]) -> str:
    lines = []
    for doc in docs[:6]:
        snippet = doc.get('text', '')[:250].replace('\n', ' ')
        lines.append(
            f"- page={doc.get('page')} score={doc.get('score'):.3f} source={doc.get('source_path')}\n  {snippet}"
        )
    return "\n".join(lines)


def _normalized_list_output(output: Any, key: str) -> List[Any]:
    if isinstance(output, dict):
        return output.get(key, []) if output.get(key, []) is not None else []
    if isinstance(output, list):
        return output
    return []


def _to_probability(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return 0.0
    if text.endswith("%"):
        try:
            return max(0.0, min(1.0, float(text[:-1].strip()) / 100.0))
        except ValueError:
            return 0.0
    try:
        return max(0.0, min(1.0, float(text)))
    except ValueError:
        pass
    keywords = {
        "certain": 1.0,
        "very likely": 0.95,
        "likely": 0.8,
        "possible": 0.6,
        "maybe": 0.5,
        "uncertain": 0.25,
        "unlikely": 0.2,
        "low": 0.15,
        "medium": 0.5,
        "high": 0.8,
        "very low": 0.1,
        "almost certain": 0.98,
        "probable": 0.75,
        "strong": 0.85,
        "weak": 0.2,
    }
    for keyword, score in keywords.items():
        if keyword in text:
            return score
    return 0.0


async def moss_retrieval_node(state: DiagnosticState) -> DiagnosticState:
    if not state.get("retrieval_queries"):
        state["retrieval_queries"] = []
    state["docs"] = await retrieve_moss_contexts(state["product_id"], state["retrieval_queries"])
    return state


async def grade_documents_node(state: DiagnosticState) -> DiagnosticState:
    if not state.get("docs"):
        state["retrieval_quality"] = "poor"
        return state

    doc_summary = _summarize_docs(state["docs"])
    response = await _render_prompt(
        relevance_grader_prompt,
        user_query=state["user_query"],
        doc_summary=doc_summary,
    )
    output = parse_json_response(response)
    quality = output.get("quality", "poor").lower()
    state["retrieval_quality"] = "good" if quality == "good" else "poor"
    return state


async def hypothesis_generator_node(state: DiagnosticState) -> DiagnosticState:
    response = await _render_prompt(
        hypothesis_prompt,
        symptoms=state["symptoms"],
        doc_summary=_summarize_docs(state["docs"]),
    )
    output = parse_json_response(response)
    state["hypotheses"] = _normalized_list_output(output, "hypotheses")
    return state


async def rank_causes_node(state: DiagnosticState) -> DiagnosticState:
    hypotheses = state.get("hypotheses", [])
    ranked = sorted(
        [
            {
                "cause": item.get("cause", "unknown"),
                "probability": _to_probability(item.get("probability", 0.0)),
                "reason": item.get("reason", ""),
            }
            for item in hypotheses
        ],
        key=lambda item: item["probability"],
        reverse=True,
    )
    if ranked and ranked[0]["probability"] > 1.0:
        total = sum(item["probability"] for item in ranked)
        for item in ranked:
            item["probability"] /= total
    state["probable_causes"] = ranked
    state["confidence"] = ranked[0]["probability"] if ranked else 0.0
    return state


async def question_generation_node(state: DiagnosticState) -> DiagnosticState:
    response = await _render_prompt(
        question_generation_prompt,
        probable_causes=state.get("probable_causes", []),
        doc_summary=_summarize_docs(state["docs"]),
    )
    output = parse_json_response(response)
    state["questions"] = _normalized_list_output(output, "questions")
    return state


def _bayesian_adjustment(question: str, answer: str, cause: str) -> float:
    normalized = answer.strip().lower()
    base = 1.0
    if "headlight" in question.lower() and "battery" in cause.lower():
        base *= 0.5 if normalized in {"yes", "y", "true"} else 1.2
    if "completely silent" in question.lower() and "fuse" in cause.lower():
        base *= 1.3 if normalized in {"yes", "y", "true"} else 0.8
    if "suddenly" in question.lower() and "wear" in cause.lower():
        base *= 0.8 if normalized in {"yes", "y", "true"} else 1.1
    if "electrical" in question.lower() and "wiring" in cause.lower():
        base *= 1.2 if normalized in {"yes", "y", "true"} else 0.85
    if normalized in {"yes", "y", "true"}:
        base *= 1.15
    elif normalized in {"no", "n", "false"}:
        base *= 0.85
    return base


async def elimination_node(state: DiagnosticState) -> DiagnosticState:
    answers = state.get("user_answers", {})
    updated = []
    for cause in state.get("probable_causes", []):
        score = cause["probability"]
        for question, answer in answers.items():
            score *= _bayesian_adjustment(question, answer, cause["cause"])
        updated.append({**cause, "probability": max(score, 1e-6)})

    total = sum(item["probability"] for item in updated) or 1.0
    normalized = [
        {**item, "probability": item["probability"] / total}
        for item in updated
    ]
    state["probable_causes"] = sorted(normalized, key=lambda item: item["probability"], reverse=True)
    state["confidence"] = state["probable_causes"][0]["probability"] if state["probable_causes"] else 0.0
    return state


async def testing_node(state: DiagnosticState) -> DiagnosticState:
    response = await _render_prompt(
        testing_prompt,
        current_cause=state.get("probable_causes", [])[0] if state.get("probable_causes") else {"cause": "unknown"},
        doc_summary=_summarize_docs(state["docs"]),
    )
    output = parse_json_response(response)
    state["inspection_steps"] = _normalized_list_output(output, "steps")
    return state


async def corrective_action_node(state: DiagnosticState) -> DiagnosticState:
    response = await _render_prompt(
        corrective_action_prompt,
        current_cause=state.get("probable_causes", [])[0] if state.get("probable_causes") else {"cause": "unknown"},
        doc_summary=_summarize_docs(state["docs"]),
    )
    output = parse_json_response(response)
    state["final_diagnosis"] = output
    state["corrective_actions"] = output.get("repair_steps", [])
    return state


async def citation_node(state: DiagnosticState) -> DiagnosticState:
    doc_metadata = "\n".join(
        [
            f"manual={doc.get('source_path')} page={doc.get('page')} figure={doc.get('figure','unknown')}"
            for doc in state.get("docs", [])
        ]
    )
    response = await _render_prompt(
        citation_prompt,
        doc_metadata=doc_metadata,
    )
    output = parse_json_response(response)
    state["citations"] = _normalized_list_output(output, "citations")
    return state
