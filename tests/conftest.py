from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.graph.orchestrator import AfterSalesGraph
from app.infrastructure.repository import InMemorySupportRepository
from app.services.rag import PolicyKnowledgeBase
from app.tools.commerce import CommerceTools


@pytest.fixture
def repository() -> InMemorySupportRepository:
    return InMemorySupportRepository()


@pytest.fixture
def graph(repository: InMemorySupportRepository) -> AfterSalesGraph:
    policy_dir = Path(__file__).parents[1] / "data" / "policies"
    knowledge_base = PolicyKnowledgeBase(policy_dir)
    return AfterSalesGraph(CommerceTools(repository), knowledge_base, InMemorySaver())
