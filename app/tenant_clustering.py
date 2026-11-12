"""Tenant-scoped complaint clustering with local TF-IDF and optional embeddings.

The caller must supply only reviews from one authenticated tenant. External
embedding calls are disabled unless the merchant explicitly opts in.
"""
from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from typing import Iterable


def _connected_components(similarity, threshold: float) -> list[list[int]]:
    n = len(similarity)
    adjacency = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if float(similarity[i][j]) >= threshold:
                adjacency[i].add(j)
                adjacency[j].add(i)
    seen: set[int] = set()
    groups: list[list[int]] = []
    for start in range(n):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        group = []
        while stack:
            current = stack.pop()
            group.append(current)
            for nxt in sorted(adjacency[current], reverse=True):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        groups.append(sorted(group))
    return sorted(groups, key=lambda group: (-len(group), group[0]))


def _vectors(texts: list[str]):
    """Return a cosine-similarity matrix and truthful method label."""
    if os.getenv("MERCHANTOS_LOCAL_EMBEDDINGS", "false").lower() in {"1", "true", "yes"}:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            model_name = os.getenv("MERCHANTOS_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            vectors = SentenceTransformer(model_name).encode(texts, normalize_embeddings=True)
            return np.asarray(vectors) @ np.asarray(vectors).T, "local_embeddings:" + model_name
        except Exception:
            # Fall through to local TF-IDF; never label a failed embedding attempt as embeddings.
            pass

    # Hosted embedding processing requires an explicit privacy opt-in.
    if os.getenv("OPENAI_API_KEY") and os.getenv("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING", "false").lower() in {"1", "true", "yes"}:
        try:
            import requests
            import numpy as np
            base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            model = os.getenv("MERCHANTOS_EMBEDDING_API_MODEL", "text-embedding-3-small")
            response = requests.post(
                base + "/embeddings",
                headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                json={"model": model, "input": texts}, timeout=30,
            )
            response.raise_for_status()
            rows = sorted(response.json()["data"], key=lambda item: item["index"])
            matrix = np.asarray([row["embedding"] for row in rows], dtype=float)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            matrix = matrix / np.maximum(norms, 1e-12)
            return matrix @ matrix.T, "api_embeddings:" + model
        except Exception:
            pass

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    try:
        matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1, sublinear_tf=True).fit_transform(texts)
        return cosine_similarity(matrix), "tfidf_cosine_fallback"
    except ValueError:
        # Empty-vocabulary input must not crash or invent similarity; keep each
        # complaint as an isolated singleton cluster.
        return np.zeros((len(texts), len(texts)), dtype=float), "tfidf_empty_vocabulary_singletons"


def cluster_reviews(reviews: Iterable[dict], threshold: float = 0.28) -> dict:
    rows = [dict(row) for row in reviews if str(row.get("text") or "").strip()]
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if not rows:
        return {"review_count": 0, "clusters": [], "method": "none", "threshold": threshold,
                "caveat": "Similarity groups are exploratory signals, not proof of a shared root cause."}
    texts = [str(row.get("text") or "")[:10000] for row in rows]
    similarities, method = _vectors(texts)
    groups = _connected_components(similarities, threshold)
    clusters = []
    for group in groups:
        members = [rows[index] for index in group]
        ids = sorted(str(row.get("id") or "") for row in members)
        cluster_id = "TEN-" + hashlib.sha256("|".join(ids).encode()).hexdigest()[:12].upper()
        terms = Counter(
            word for row in members
            for word in re.findall(r"[a-z]{4,}", str(row.get("text") or "").lower())
            if word not in {"with", "this", "that", "from", "have", "very", "just", "they", "them", "were", "when", "your", "product", "order"}
        )
        ratings = [int(row["rating"]) for row in members if row.get("rating") is not None]
        clusters.append({
            "cluster_id": cluster_id,
            "count": len(members),
            "review_ids": ids,
            "keywords": [word for word, _ in terms.most_common(6)],
            "examples": [str(row.get("text") or "")[:240] for row in members[:3]],
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "method": method,
        })
    return {"review_count": len(rows), "clusters": clusters, "method": method,
            "threshold": threshold,
            "caveat": "Similarity groups are exploratory signals, not proof of a shared root cause. Clusters do not establish causation."}
