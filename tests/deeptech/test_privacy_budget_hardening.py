import math
import random
import pytest

from app.deeptech.research.privacy_budget import (
    BasicPrivacyAccountant,
    GaussianMechanism,
    PrivacyRelease,
)


def test_gaussian_calibration_requires_classical_epsilon_range():
    release = GaussianMechanism().calibrate(1.0, 0.5, 1e-5)
    assert release.noise_sigma > 0
    with pytest.raises(ValueError):
        GaussianMechanism().calibrate(1.0, 2.0, 1e-5)


@pytest.mark.parametrize("values", [
    (float("nan"), 0.5, 1e-5),
    (1.0, float("inf"), 1e-5),
    (1.0, 0.5, float("nan")),
])
def test_gaussian_calibration_rejects_non_finite_parameters(values):
    with pytest.raises(ValueError):
        GaussianMechanism().calibrate(*values)


def test_accountant_rejects_negative_spend():
    accountant = BasicPrivacyAccountant(1.0, 1e-4)
    with pytest.raises(ValueError):
        accountant.can_spend(-0.1, 0.0)


def test_accountant_composes_and_rejects_over_budget_release():
    accountant = BasicPrivacyAccountant(1.0, 1e-4)
    release = GaussianMechanism().calibrate(1.0, 0.6, 4e-5)
    accountant.record(release)
    assert accountant.spent() == pytest.approx((0.6, 4e-5))
    with pytest.raises(RuntimeError):
        accountant.record(release)


def test_accountant_rejects_invalid_release_object():
    accountant = BasicPrivacyAccountant(1.0, 1e-4)
    bad = PrivacyRelease("gaussian", -1.0, 0.0, 1.0, 1.0)
    with pytest.raises(ValueError):
        accountant.record(bad)


def test_gaussian_noise_uses_supplied_rng():
    release = GaussianMechanism().calibrate(1.0, 0.5, 1e-5)
    rng = random.Random(7)
    first = GaussianMechanism().add_noise(10.0, release, rng)
    second = GaussianMechanism().add_noise(10.0, release, random.Random(7))
    assert first == second
    assert math.isfinite(first)
