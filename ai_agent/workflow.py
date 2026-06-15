from typing import Callable, Awaitable, Dict, Any, List
from .state import DiagnosticState
from .nodes import (
    symptom_understanding_node,
    query_regenerator_node,
    moss_retrieval_node,
    grade_documents_node,
    hypothesis_generator_node,
    rank_causes_node,
    question_generation_node,
    elimination_node,
    testing_node,
    corrective_action_node,
    citation_node,
)

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph = None
    END = None


def _build_graph() -> Any:
    if StateGraph is None:
        return None

    graph = StateGraph(DiagnosticState)
    graph.set_entry_point("symptom_understanding")
    graph.add_node("symptom_understanding", symptom_understanding_node)
    graph.add_node("query_regenerator", query_regenerator_node)
    graph.add_node("moss_retrieval", moss_retrieval_node)
    graph.add_node("grade_documents", grade_documents_node)
    graph.add_node("hypothesis_generator", hypothesis_generator_node)
    graph.add_node("rank_causes", rank_causes_node)
    graph.add_node("question_generation", question_generation_node)
    graph.add_node("elimination", elimination_node)
    graph.add_node("testing", testing_node)
    graph.add_node("corrective_action", corrective_action_node)
    graph.add_node("citation", citation_node)

    graph.add_edge("symptom_understanding", "query_regenerator")
    graph.add_edge("query_regenerator", "moss_retrieval")
    graph.add_edge("moss_retrieval", "grade_documents")
    graph.add_edge("grade_documents", "hypothesis_generator")
    graph.add_edge("hypothesis_generator", "rank_causes")
    graph.add_edge("rank_causes", "question_generation")
    graph.add_edge("question_generation", "elimination")
    graph.add_edge("elimination", "testing")
    graph.add_edge("testing", "corrective_action")
    graph.add_edge("corrective_action", "citation")
    graph.add_edge("citation", END)

    return graph.compile()


compiled_graph = _build_graph()


class DiagnosticAgent:
    def __init__(self):
        self.graph = compiled_graph

    async def run(
        self,
        product_id: str,
        user_query: str,
        answer_provider: Callable[[List[Dict[str, Any]]], Awaitable[Dict[str, str]]],
        max_rounds: int = 3,
    ) -> DiagnosticState:
        state: DiagnosticState = {
            "product_id": product_id,
            "user_query": user_query,
            "symptoms": {},
            "retrieval_queries": [],
            "docs": [],
            "retrieval_quality": "poor",
            "hypotheses": [],
            "probable_causes": [],
            "questions": [],
            "user_answers": {},
            "confidence": 0.0,
            "inspection_steps": [],
            "corrective_actions": [],
            "citations": [],
            "final_diagnosis": {},
        }

        state = await symptom_understanding_node(state)
        state = await query_regenerator_node(state)

        for _ in range(3):
            state = await moss_retrieval_node(state)
            state = await grade_documents_node(state)
            if state["retrieval_quality"] == "good":
                break
            state = await query_regenerator_node(state)

        state = await hypothesis_generator_node(state)
        state = await rank_causes_node(state)

        round_count = 0
        while state["confidence"] < 0.80 and round_count < max_rounds:
            state = await question_generation_node(state)
            answers = await answer_provider(state["questions"])
            state["user_answers"] = answers
            state = await elimination_node(state)
            state = await rank_causes_node(state)
            round_count += 1

        state = await testing_node(state)
        state = await corrective_action_node(state)
        state = await citation_node(state)
        return state
