from typing import TypedDict, List, Dict, Any


class DiagnosticState(TypedDict, total=False):
    product_id: str
    user_query: str

    symptoms: Dict[str, Any]
    retrieval_queries: List[str]

    docs: List[Dict[str, Any]]
    retrieval_quality: str

    hypotheses: List[Dict[str, Any]]
    probable_causes: List[Dict[str, Any]]

    questions: List[Dict[str, Any]]
    user_answers: Dict[str, str]

    confidence: float

    inspection_steps: List[Dict[str, Any]]
    corrective_actions: List[Dict[str, Any]]

    citations: List[Dict[str, Any]]
    final_diagnosis: Dict[str, Any]
