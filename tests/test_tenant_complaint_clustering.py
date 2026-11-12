import os


def test_tfidf_clustering_groups_similar_complaints_and_keeps_singletons(monkeypatch):
    monkeypatch.setenv("MERCHANTOS_LOCAL_EMBEDDINGS", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING", "false")
    from app.tenant_clustering import cluster_reviews

    result = cluster_reviews([
        {"id": "r1", "text": "The parcel arrived late and delivery was delayed", "rating": 1},
        {"id": "r2", "text": "Delivery was delayed and the parcel arrived late", "rating": 2},
        {"id": "r3", "text": "The blue ceramic mug is beautiful and sturdy", "rating": 5},
    ], threshold=0.25)

    assert result["review_count"] == 3
    assert result["method"] == "tfidf_cosine_fallback"
    assert sorted(cluster["count"] for cluster in result["clusters"]) == [1, 2]
    assert all(cluster["cluster_id"].startswith("TEN-") for cluster in result["clusters"])
    assert "not proof" in result["caveat"]


def test_tenant_clustering_is_deterministic(monkeypatch):
    monkeypatch.setenv("MERCHANTOS_LOCAL_EMBEDDINGS", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.tenant_clustering import cluster_reviews
    rows = [{"id": "a", "text": "Broken item arrived damaged"},
            {"id": "b", "text": "Item arrived damaged and broken"}]
    first = cluster_reviews(rows)
    second = cluster_reviews(rows)
    assert first["clusters"] == second["clusters"]


def test_tenant_clustering_empty_input_is_safe():
    from app.tenant_clustering import cluster_reviews
    result = cluster_reviews([])
    assert result["review_count"] == 0
    assert result["clusters"] == []
    assert result["method"] == "none"


def test_tenant_clustering_rejects_invalid_threshold():
    import pytest
    from app.tenant_clustering import cluster_reviews
    with pytest.raises(ValueError):
        cluster_reviews([], threshold=1.1)


def test_tfidf_empty_vocabulary_keeps_reviews_as_singletons(monkeypatch):
    monkeypatch.setenv("MERCHANTOS_LOCAL_EMBEDDINGS", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.tenant_clustering import cluster_reviews
    result = cluster_reviews([{"id": "x", "text": "the and of"}, {"id": "y", "text": "and the to"}])
    assert result["method"] == "tfidf_empty_vocabulary_singletons"
    assert sorted(group["count"] for group in result["clusters"]) == [1, 1]
