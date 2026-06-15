import argparse
import asyncio
from typing import Dict, List

from .workflow import DiagnosticAgent
from .moss_client import build_moss_knowledge_base
from .pdf_utils import extract_text_from_pdf as extract_pdf_text


async def prompt_async(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def answer_provider(questions: List[Dict[str, str]]) -> Dict[str, str]:
    answers: Dict[str, str] = {}
    for question_record in questions:
        question_text = question_record.get("question") if isinstance(question_record, dict) else str(question_record)
        response = await prompt_async(f"{question_text}\nAnswer: ")
        answers[question_text] = response.strip()
    return answers


async def run_diagnostic(product_id: str, user_query: str, pdf_path: str | None = None) -> None:
    if pdf_path:
        print(f"\n[PDF Ingestion] Loading manual from: {pdf_path}")
        pdf_text = extract_pdf_text(pdf_path)
        await build_moss_knowledge_base(product_id, pdf_text, images=[], tables=[])
        print("[PDF Ingestion] Knowledge repository updated from PDF.")

    agent = DiagnosticAgent()
    print(f"\n[Diagnostic Assistant] Starting investigation for product '{product_id}'...")
    state = await agent.run(product_id, user_query, answer_provider)

    print("\n=== FINAL DIAGNOSIS ===")
    print(f"Root cause: {state['final_diagnosis'].get('root_cause', 'unknown')}")
    print(f"Confidence: {state['final_diagnosis'].get('confidence', state.get('confidence', 0.0)):.2f}")

    print("\n=== RECOMMENDED INSPECTION ===")
    for idx, step in enumerate(state.get("inspection_steps", []), start=1):
        print(f"{idx}. {step}")

    print("\n=== CORRECTIVE ACTIONS ===")
    for idx, action in enumerate(state.get("corrective_actions", []), start=1):
        print(f"{idx}. {action}")

    print("\n=== CITATIONS ===")
    for citation in state.get("citations", []):
        print(f"- {citation}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the product diagnostic assistant.")
    parser.add_argument("--product-id", required=True, help="Target product identifier for MOSS retrieval")
    parser.add_argument("--query", required=True, help="User symptom description")
    parser.add_argument("--pdf", required=False, help="Optional PDF manual path to ingest before diagnosis")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_diagnostic(args.product_id, args.query, args.pdf))


if __name__ == "__main__":
    main()
