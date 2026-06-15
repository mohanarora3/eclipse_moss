import json
import re
from typing import Any, Dict, List


def parse_json_response(raw: str) -> Any:
    if not raw or not raw.strip():
        raise ValueError("LLM returned empty response")

    cleaned = raw.strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()

    list_start = cleaned.find("[")
    list_end = cleaned.rfind("]")
    obj_start = cleaned.find("{")
    obj_end = cleaned.rfind("}")

    candidate = None
    if list_start != -1 and list_end != -1 and list_end > list_start:
        candidate = cleaned[list_start:list_end + 1]
    elif obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidate = cleaned[obj_start:obj_end + 1]
    else:
        candidate = cleaned

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        if candidate != cleaned:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
        raise ValueError(
            f"Unable to parse JSON response.\nOriginal:\n{raw}\nCandidate:\n{candidate}"
        ) from exc


def normalize_query_text(query: str) -> str:
    return query.strip().replace("\n", " ").replace("  ", " ")


def merge_document_contexts(documents: List[Dict[str, Any]], top_k: int = 6) -> List[Dict[str, Any]]:
    unique_docs: Dict[str, Dict[str, Any]] = {}
    for doc in documents:
        doc_id = doc.get("id") or doc.get("source_path") or doc.get("text", "")[:80]
        existing = unique_docs.get(doc_id)
        if existing is None or doc.get("score", 0) > existing.get("score", 0):
            unique_docs[doc_id] = doc

    sorted_docs = sorted(unique_docs.values(), key=lambda x: x.get("score", 0), reverse=True)
    return sorted_docs[:top_k]
