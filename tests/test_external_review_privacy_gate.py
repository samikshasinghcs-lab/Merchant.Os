import builtins


def test_hosted_embeddings_are_disabled_without_explicit_privacy_opt_in(monkeypatch):
    from app import merchant_intelligence as mi

    real_import = builtins.__import__

    def import_without_sentence_transformers(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("not installed for test")
        return real_import(name, *args, **kwargs)

    def forbidden_post(*args, **kwargs):
        raise AssertionError("Hosted API must not receive review text without explicit opt-in")

    monkeypatch.setattr(builtins, "__import__", import_without_sentence_transformers)
    monkeypatch.setattr(mi.requests, "post", forbidden_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING", raising=False)
    vectors, method = mi._vectors(["package arrived damaged", "delivery was late"])
    assert method == "tfidf_cosine_fallback"
    assert vectors.shape[0] == 2
