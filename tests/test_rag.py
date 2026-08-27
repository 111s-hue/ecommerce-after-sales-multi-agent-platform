from pathlib import Path

from app.services.rag import PolicyKnowledgeBase


def test_policy_rag_returns_clause_level_citation() -> None:
    policy_dir = Path(__file__).parents[1] / "data" / "policies"
    knowledge_base = PolicyKnowledgeBase(policy_dir)

    evidence = knowledge_base.search("签收后七天可以无理由退货吗", top_k=2)

    assert evidence
    assert evidence[0].source == "refund_policy.md"
    assert "七天" in evidence[0].section
    assert evidence[0].score > 0
