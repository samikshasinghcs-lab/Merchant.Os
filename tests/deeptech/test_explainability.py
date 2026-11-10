import pytest

from app.deeptech.research.explainability import (
    PermutationImportance,
    explain_linear_prediction,
    explanation_to_dict,
    top_contributors,
)


def test_linear_explanation_reconstructs_prediction():
    explanation = explain_linear_prediction(
        {"amount": 12, "velocity": 3},
        {"amount": 0.5, "velocity": -2},
        intercept=4,
        baseline_values={"amount": 10, "velocity": 2},
    )
    assert abs(explanation.reconstruction_error) < 1e-12
    assert explanation.prediction == 4
    assert len(top_contributors(explanation, 1)) == 1


def test_explanation_serialization_is_stable_and_json_friendly():
    explanation = explain_linear_prediction({"x": 2}, {"x": 3}, 1)
    result = explanation_to_dict(explanation, precision=4)
    assert result["prediction"] == 7
    assert result["contributions"][0]["feature"] == "x"


def test_linear_explanation_requires_exact_schema():
    with pytest.raises(ValueError):
        explain_linear_prediction({"x": 1, "y": 2}, {"x": 1})


def test_permutation_importance_is_reproducible():
    rows = [{"signal": float(i), "noise": float((i * 7) % 5)} for i in range(20)]
    targets = [row["signal"] * 2 for row in rows]
    predictor = lambda row: row["signal"] * 2
    first = PermutationImportance(repeats=5, seed=9).evaluate(rows, targets, predictor)
    second = PermutationImportance(repeats=5, seed=9).evaluate(rows, targets, predictor)
    assert first == second
    assert first[0].feature == "signal"
    assert first[0].mean_score_drop > 0


def test_importance_rejects_mismatched_data():
    with pytest.raises(ValueError):
        PermutationImportance().evaluate([{"x": 1}], [], lambda row: row["x"])


def test_top_contributors_requires_positive_limit():
    explanation = explain_linear_prediction({"x": 2}, {"x": 1})
    with pytest.raises(ValueError):
        top_contributors(explanation, 0)
