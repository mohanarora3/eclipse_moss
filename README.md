# MOSS Product Portal

This repository contains a React + Vite frontend and a FastAPI backend for a product manual ingestion and AI product Q&A experience.

## Project Overview

- Frontend: `src/App.jsx` provides a login flow, company product upload panel, and user-facing product question interface.
- Backend: `ai_agent/api.py` provides the API endpoints for product listing, product registration, product query/chat, and a health check.
- Local product catalog metadata is stored in `product_catalog.json`.
- Uploaded manuals are written into `manual_uploads/`.

## Key Features

- Company role: upload a PDF manual, ingest it, and register a product entry.
- User role: ask questions against ingested product manuals.
- FastAPI backend with CORS enabled for local development.
- Frontend uses `VITE_API_BASE` to point at the backend API.

## What This Project Is About

This repository is a product knowledge and diagnostic platform that turns technical manuals into an AI-powered support experience.

- The company workflow ingests PDF manuals and creates a searchable knowledge base for each product.
- The backend uses MOSS embeddings and a local product catalog to store and retrieve product documentation.
- The user workflow submits natural language questions and receives answers drawn from product manuals.
- The backend AI logic includes document retrieval, prompt construction, and LLM response generation via `ai_agent/qa.py` and `ai_agent/llm.py`.
- There is also a diagnostic agent workflow in `ai_agent/workflow.py` and `ai_agent/nodes.py` that can analyze symptoms, generate follow-up questions, and recommend inspection or corrective actions.
- The repository supports both a browser UI and a CLI diagnostic entry point via `ai_agent/main.py`.

## Folder Structure

- `src/` - React frontend source.
- `ai_agent/` - Python backend application code.
- `manual_uploads/` - Uploaded PDF manuals and photo attachments.
- `product_catalog.json` - Catalog metadata and manual references.
- `requirements.txt` - Python dependencies for the backend.
- `package.json` - Frontend dependencies and Vite scripts.
- `vite.config.js` - Vite configuration.

## Prerequisites

- Node.js / npm
- Python 3.11+ with a virtual environment
- `npm install` for frontend dependencies
- `pip install -r requirements.txt` for backend dependencies

## Backend Setup

1. Activate your Python virtual environment. Example:

```bash
cd /Users/mohanaarora/Desktop/moss\ 2
python3 -m venv venv
source venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Start the FastAPI backend:

```bash
python3 -m uvicorn ai_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

4. Confirm the backend is available:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","backend":"moss_product_qa"}
```

## Frontend Setup

1. Install Node dependencies:

```bash
cd /Users/mohanaarora/Desktop/moss\ 2
npm install
```

2. Run the Vite development server:

```bash
npm run dev
```

3. Open the frontend app in your browser at the URL Vite prints, typically:

```text
http://localhost:4173
```

## Environment Configuration

The project supports configuration through `.env` files and Vite environment variables.

Example environment variables:

- `VITE_API_BASE` — backend API base URL, default `http://localhost:8000`
- `DATABASE_URL` — SQLite DB connection string for backend state
- `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY` — MOSS credentials for AI ingestion
- `LLM_PROVIDER`, `MODEL_NAME` — LLM provider configuration

If you want to change the frontend API target, set `VITE_API_BASE` in a `.env` or `.env.local` file in the project root.

## Login Credentials

Use the built-in sample credentials in the UI:

- Company role:
  - Username: `company`
  - Password: `company123`
- User role:
  - Username: `user`
  - Password: `user123`

## How It Works

- Frontend reads `VITE_API_BASE` and sends requests to `/products`.
- Backend serves `/products` and stores metadata via `ai_agent/moss_client.py`.
- Product upload saves the PDF under `manual_uploads/` and builds a knowledge base.
- User queries go to backend product-specific query/chat endpoints.
- The backend performs document retrieval from MOSS indexes, formats prompt context, and calls the configured LLM provider to generate answers.
- The diagnostic agent workflow can also run a multi-step symptom investigation from command line using `ai_agent/main.py`.

## Troubleshooting

### Frontend cannot load products

- Ensure the backend is running at `http://localhost:8000`.
- Confirm the health endpoint works:

```bash
curl http://127.0.0.1:8000/health
```

- Verify the frontend uses the correct API base:

```js
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
```

### Backend fails to start

- Make sure your Python virtual environment is active.
- Verify `requirements.txt` is installed.
- Check that `ai_agent/api.py` is present and not modified incorrectly.

### PDF upload fails

- Only `application/pdf` files are accepted.
- The product ID and product name are required.
- Uploaded PDF files are saved to `manual_uploads/`.

## Recommended Workflow

1. Start backend first:

```bash
source venv/bin/activate
python3 -m uvicorn ai_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

2. Start frontend next:

```bash
npm run dev
```

3. Open the Vite app in the browser and sign in.

4. Use the Company role to register a product and upload a PDF.

5. Switch to the User role to ask questions about ingested products.

## Notes

- The FastAPI backend allows all CORS origins for local development.
- The frontend and backend are separate processes.
- The backend port must match `VITE_API_BASE` in the frontend.

---

If you want, I can also add a short `backend` script to `package.json` and a `.env.example` update for easier startup.# eclipse_moss
