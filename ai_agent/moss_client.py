import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from moss import MossClient, QueryOptions, DocumentInfo

BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = BASE_DIR.parent / "product_catalog.json"
ROOT_ENV = BASE_DIR.parent / ".env"
LOCAL_ENV = BASE_DIR / ".env"
if ROOT_ENV.exists():
    load_dotenv(ROOT_ENV)
elif LOCAL_ENV.exists():
    load_dotenv(LOCAL_ENV)
else:
    load_dotenv()

MOSS_PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")

if not MOSS_PROJECT_ID or not MOSS_PROJECT_KEY:
    raise ValueError("Missing MOSS_PROJECT_ID or MOSS_PROJECT_KEY in .env file")

client = MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY)


def index_name_for_product(product_id: str) -> str:
    return f"product_kb_{product_id}"


def load_product_catalog() -> Dict[str, Dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return {}
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as catalog_file:
            return json.load(catalog_file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_product_catalog(catalog: Dict[str, Dict[str, Any]]) -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_PATH, "w", encoding="utf-8") as catalog_file:
        json.dump(catalog, catalog_file, indent=2, ensure_ascii=False)


def register_product(product_id: str, product_name: str, manual_path: Optional[str] = None) -> None:
    if not product_id:
        raise ValueError("product_id is required")

    catalog = load_product_catalog()
    entry = catalog.get(product_id, {})
    entry.update(
        {
            "product_name": product_name.strip(),
            "manual_path": manual_path or entry.get("manual_path", ""),
            "ingested_at": datetime.utcnow().isoformat() + "Z",
        }
    )
    catalog[product_id] = entry
    save_product_catalog(catalog)


async def list_products() -> List[Dict[str, Any]]:
    product_ids = await list_product_ids()
    catalog = load_product_catalog()
    products = []
    for product_id in product_ids:
        metadata = catalog.get(product_id, {})
        products.append(
            {
                "product_id": product_id,
                "product_name": metadata.get("product_name", ""),
                "manual_path": metadata.get("manual_path", ""),
                "ingested_at": metadata.get("ingested_at", ""),
            }
        )
    return sorted(products, key=lambda item: item["product_id"])


async def list_product_ids() -> List[str]:
    indexes = await client.list_indexes()
    prefix = "product_kb_"
    product_ids = [idx.name[len(prefix) :] for idx in indexes if idx.name.startswith(prefix)]
    return sorted(product_ids)


async def product_index_exists(product_id: str) -> bool:
    index_name = index_name_for_product(product_id)
    return any(idx.name == index_name for idx in await client.list_indexes())


async def delete_product_index(product_id: str) -> bool:
    index_name = index_name_for_product(product_id)
    if await product_index_exists(product_id):
        return await client.delete_index(index_name)
    return False


async def ensure_index_loaded(product_id: str) -> str:
    index_name = index_name_for_product(product_id)
    try:
        await client.load_index(index_name)
    except RuntimeError as exc:
        if "Index not found" in str(exc):
            raise RuntimeError(
                f"MOSS index '{index_name}' does not exist. "
                "Create it first by passing --pdf /path/to/manual.pdf or ingesting the product manual into MOSS."
            ) from exc
        raise
    return index_name


async def build_moss_knowledge_base(
    product_id: str,
    markdown_text: str,
    images: List[Dict[str, Any]],
    tables: List[Dict[str, Any]],
    chunk_size: int = 1000,
) -> str:
    from .utils import normalize_query_text

    text_chunks = []
    paragraph_candidates = [paragraph.strip() for paragraph in markdown_text.split("\n\n") if paragraph.strip()]
    current = ""
    for paragraph in paragraph_candidates:
        if len(current) + len(paragraph) + 1 <= chunk_size:
            current = f"{current}\n\n{paragraph}" if current else paragraph
        else:
            text_chunks.append(current)
            current = paragraph
    if current:
        text_chunks.append(current)

    image_map: Dict[int, List[str]] = {}
    for item in images:
        image_map.setdefault(int(item.get("page", 0)), []).append(item.get("path", ""))

    table_map: Dict[int, List[str]] = {}
    for item in tables:
        table_map.setdefault(int(item.get("page", 0)), []).append(item.get("path", ""))

    documents_to_index: List[DocumentInfo] = []
    for idx, chunk in enumerate(text_chunks):
        page = (idx // 4) + 1
        content_type = "diagnostic" if any(keyword in chunk.lower() for keyword in ["troubleshoot", "fault", "error", "fail", "silent", "dead"]) else "general"
        chunk_path = f"product_{product_id}_chunk_{idx}"

        metadata = {
            "product_id": str(product_id),
            "page": str(page),
            "source_path": chunk_path,
            "content_type": content_type,
            "images": ",".join(image_map.get(page, [])),
            "tables": ",".join(table_map.get(page, [])),
        }

        documents_to_index.append(
            DocumentInfo(
                id=f"{product_id}_{idx}",
                text=chunk,
                metadata=metadata,
            )
        )

    index_name = index_name_for_product(product_id)
    await client.create_index(index_name, documents_to_index)
    await client.load_index(index_name)
    return index_name


async def retrieve_moss_contexts(
    product_id: str,
    queries: List[str],
    top_k: int = 6,
    alpha: float = 0.7,
) -> List[Dict[str, Any]]:
    index_name = await ensure_index_loaded(product_id)
    tasks = []
    for query in queries:
        options = QueryOptions(top_k=top_k, alpha=alpha)
        tasks.append(client.query(index_name, query, options))

    results = await asyncio.gather(*tasks)
    merged: Dict[str, Dict[str, Any]] = {}

    for query, result in zip(queries, results):
        for doc in result.docs:
            doc_id = getattr(doc, "id", None) or getattr(doc, "metadata", {}).get("source_path", None) or doc.text[:80]
            if doc_id not in merged or doc.score > merged[doc_id]["score"]:
                metadata = getattr(doc, "metadata", {}) or {}
                merged[doc_id] = {
                    "id": doc_id,
                    "text": getattr(doc, "text", ""),
                    "score": getattr(doc, "score", 0),
                    "query": query,
                    "page": metadata.get("page"),
                    "images": metadata.get("images", "").split(",") if metadata.get("images") else [],
                    "tables": metadata.get("tables", "").split(",") if metadata.get("tables") else [],
                    "videos": metadata.get("videos", "").split(",") if metadata.get("videos") else [],
                    "source_path": metadata.get("source_path"),
                    "content_type": metadata.get("content_type"),
                }

    return sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:top_k]
