import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .moss_client import (
    build_moss_knowledge_base,
    register_product,
    list_products,
    product_index_exists,
)
from .pdf_utils import extract_text_from_pdf
from .qa import answer_product_question, chat_with_product

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR.parent / "manual_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="MOSS Product Q&A API",
    description="Product onboarding and user Q&A endpoints for technical manuals.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {"status": "ok", "backend": "moss_product_qa"}


@app.get("/products")
async def api_list_products() -> List[Dict[str, Any]]:
    return await list_products()


@app.post("/products")
async def api_register_product(
    product_id: str = Form(...),
    product_name: str = Form(...),
    pdf_manual: UploadFile = File(...),
) -> Dict[str, Any]:
    if not product_id.strip() or not product_name.strip():
        raise HTTPException(status_code=400, detail="product_id and product_name are required.")

    if pdf_manual.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF manuals are accepted.")

    target_path = UPLOAD_DIR / f"{product_id}.pdf"
    try:
        with target_path.open("wb") as out_file:
            shutil.copyfileobj(pdf_manual.file, out_file)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save PDF: {exc}")

    try:
        pdf_text = extract_text_from_pdf(str(target_path))
        await build_moss_knowledge_base(product_id, pdf_text, images=[], tables=[])
        register_product(product_id, product_name, manual_path=str(target_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to ingest product manual: {exc}")

    return {
        "product_id": product_id,
        "product_name": product_name,
        "manual_path": str(target_path),
        "status": "ingested",
    }


@app.post("/products/{product_id}/query")
async def api_query_product(product_id: str, question: Dict[str, str]) -> JSONResponse:
    user_query = question.get("query")
    if not user_query:
        raise HTTPException(status_code=400, detail="Missing query text.")

    try:
        result = await answer_product_question(product_id, user_query)
        return JSONResponse(content=result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")


@app.post("/products/{product_id}/chat")
async def api_chat_product(product_id: str, conversation: Dict[str, Any]) -> JSONResponse:
    messages = conversation.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="Invalid conversation payload.")

    try:
        result = await chat_with_product(product_id, messages)
        return JSONResponse(content=result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat query failed: {exc}")


@app.post("/products/{product_id}/chat/photo")
async def api_chat_product_with_photo(
    product_id: str,
    messages: str = Form(...),
    product_image: UploadFile = File(...),
) -> JSONResponse:
    try:
        conversation = json.loads(messages)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid messages payload: {exc}")

    if not isinstance(conversation, list) or not conversation:
        raise HTTPException(status_code=400, detail="Invalid conversation payload.")

    target_dir = UPLOAD_DIR / "photos"
    target_dir.mkdir(parents=True, exist_ok=True)
    image_path = target_dir / product_image.filename
    try:
        with image_path.open("wb") as out_file:
            shutil.copyfileobj(product_image.file, out_file)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {exc}")

    try:
        result = await chat_with_product(
            product_id,
            conversation,
            image_attachment={"filename": product_image.filename, "path": str(image_path)},
        )
        return JSONResponse(content=result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat query failed: {exc}")


@app.get("/products/{product_id}/exists")
async def api_product_exists(product_id: str) -> Dict[str, Any]:
    exists = await product_index_exists(product_id)
    return {"product_id": product_id, "exists": exists}
