import asyncio
from typing import Any, Dict, List, Optional

from .llm import LLMClient
from .moss_client import retrieve_moss_contexts, load_product_catalog
from .prompts import product_qa_prompt, product_chat_prompt
from .utils import parse_json_response


def _format_document_summary(documents: List[Dict[str, Any]]) -> str:
    lines = []
    for document in documents:
        page = document.get("page", "?")
        score = document.get("score", 0.0)
        text = document.get("text", "").strip().replace("\n", " ")
        if len(text) > 500:
            text = text[:500].rstrip() + "..."
        lines.append(f"Page {page} score={score:.3f}\n{text}")
    return "\n\n".join(lines)


async def answer_product_question(product_id: str, user_query: str) -> Dict[str, Any]:
    catalog = load_product_catalog()
    product_info = catalog.get(product_id)
    if not product_info:
        raise ValueError(f"Product '{product_id}' is not registered.")

    docs = await retrieve_moss_contexts(product_id, [user_query], top_k=6)
    if not docs:
        return {
            "product_id": product_id,
            "product_name": product_info.get("product_name", ""),
            "query": user_query,
            "answer": "No documentation is currently available for this product.",
            "documents": [],
        }

    doc_summary = _format_document_summary(docs)
    llm = LLMClient()
    messages = product_qa_prompt.format_prompt(
        product_id=product_id,
        product_name=product_info.get("product_name", ""),
        user_query=user_query,
        doc_summary=doc_summary,
    ).to_messages()
    answer_text = await llm.generate(messages)

    return {
        "product_id": product_id,
        "product_name": product_info.get("product_name", ""),
        "query": user_query,
        "answer": answer_text.strip(),
        "documents": docs,
    }


async def chat_with_product(
    product_id: str,
    messages: List[Dict[str, str]],
    image_attachment: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    catalog = load_product_catalog()
    product_info = catalog.get(product_id)
    if not product_info:
        raise ValueError(f"Product '{product_id}' is not registered.")

    if not messages or messages[-1].get("role") != "user":
        raise ValueError("Conversation must end with a user message.")

    conversation_lines = []
    for message in messages:
        role = message.get("role", "user").capitalize()
        content = message.get("content", "").strip()
        if content:
            conversation_lines.append(f"{role}: {content}")
    conversation = "\n".join(conversation_lines)

    docs = await retrieve_moss_contexts(product_id, [messages[-1]["content"]], top_k=6)
    doc_summary = _format_document_summary(docs)
    llm = LLMClient()

    image_note = ""
    if image_attachment:
        image_note = (
            "The user attached an image file with the product damage. "
            f"Image filename: {image_attachment.get('filename', 'unknown')}. "
            "Use this attachment to reason about visible damage and ask follow-up questions if you need more detail. "
            "If you do not have direct access to the image content, be explicit about what you need the user to describe."
        )

    prompt_messages = product_chat_prompt.format_prompt(
        product_id=product_id,
        product_name=product_info.get("product_name", ""),
        conversation=conversation,
        doc_summary=doc_summary,
        image_note=image_note,
    ).to_messages()
    response_text = await llm.generate(prompt_messages)

    assistant_response = response_text.strip()
    citations: List[Dict[str, Any]] = []

    try:
        parsed = parse_json_response(response_text)
        if isinstance(parsed, dict):
            if "assistant_response" in parsed:
                assistant_response = str(parsed.get("assistant_response", assistant_response)).strip()
            raw_citations = parsed.get("citations", [])
            if isinstance(raw_citations, dict):
                citations = [raw_citations]
            elif isinstance(raw_citations, list):
                citations = raw_citations
    except Exception:
        pass

    return {
        "product_id": product_id,
        "product_name": product_info.get("product_name", ""),
        "assistant": assistant_response,
        "citations": citations,
        "documents": docs,
    }
