"""
Unit tests for the AAFCO & FDA label compliance checker.
"""

import pytest
from pet_feed_reg_compliance.label_checker.checker import LabelComplianceChecker


@pytest.fixture
def checker():
    return LabelComplianceChecker()


def test_compliant_treat_label(checker):
    text = """
    Artisan Hound Beef & Cranberry Dog Treats
    All Natural Treats for Dogs
    NET WT 8 OZ (227 g)

    Guaranteed Analysis:
    Crude Protein (min): 24.0%
    Crude Fat (min): 12.0%
    Crude Fiber (max): 3.5%
    Moisture (max): 10.0%

    Ingredients: Beef, Cranberries, Organic Flaxseed, Mixed Tocopherols.

    Feeding Directions: Feed as a healthy reward or training aid.
    This product is intended for intermittent or supplemental feeding only.

    Manufactured for: Artisan Hound LLC, Seattle, WA 98101
    """
    res = checker.check_label(text, product_name="Artisan Hound Beef & Cranberry Dog Treats", expected_type="treat")
    assert res.is_compliant is True
    assert res.score >= 90
    assert len(res.violations) == 0
    assert res.extracted_elements["target_species"] == "dog"
    assert res.extracted_elements["guaranteed_analysis"]["crude_protein_min"] == 24.0


def test_missing_metric_units_flagged(checker):
    # Only Net Wt 8 oz, missing (227 g)
    text = """
    Artisan Hound Beef & Cranberry Dog Treats
    For Dogs
    NET WT 8 OZ

    Guaranteed Analysis:
    Crude Protein (min): 24.0%
    Crude Fat (min): 12.0%
    Crude Fiber (max): 3.5%
    Moisture (max): 10.0%

    Ingredients: Beef, Cranberries.
    Feeding Directions: Feed as a treat.
    This product is intended for intermittent or supplemental feeding only.
    Manufactured for: Artisan Hound LLC, Seattle, WA 98101
    """
    res = checker.check_label(text, product_name="Artisan Hound", expected_type="treat")
    assert res.is_compliant is False
    net_violation = next((v for v in res.violations if "Net Quantity" in v.element), None)
    assert net_violation is not None
    assert net_violation.severity == "MAJOR"
    assert "FPLA" in net_violation.citation or "501.105" in net_violation.citation


def test_missing_guaranteed_analysis_flagged(checker):
    text = """
    Healthy Paws Crunchies for Dogs
    NET WT 10 OZ (283 g)
    Ingredients: Chicken, Oats, Blueberries.
    Manufactured for: Healthy Paws, Austin, TX 78701
    Feeding Guidelines: Feed as a snack.
    This product is intended for intermittent or supplemental feeding only.
    """
    res = checker.check_label(text, product_name="Healthy Paws Crunchies", expected_type="treat")
    assert res.is_compliant is False
    ga_violation = next((v for v in res.violations if "Guaranteed Analysis" in v.element), None)
    assert ga_violation is not None
    assert ga_violation.severity == "CRITICAL"


def test_inverted_guaranteed_analysis_order(checker):
    # Fiber listed before Fat
    text = """
    Pup Snack for Dogs
    NET WT 6 OZ (170 g)

    Guaranteed Analysis:
    Crude Protein (min): 20.0%
    Crude Fiber (max): 4.0%
    Crude Fat (min): 10.0%
    Moisture (max): 12.0%

    Ingredients: Turkey, Rice.
    Feeding Guidelines: Feed as a treat.
    This product is intended for intermittent or supplemental feeding only.
    Manufactured for: Pup Snack LLC, Chicago, IL 60601
    """
    res = checker.check_label(text, product_name="Pup Snack", expected_type="treat")
    assert res.is_compliant is False
    seq_violation = next((v for v in res.violations if "Sequence" in v.element), None)
    assert seq_violation is not None
    assert seq_violation.severity == "MAJOR"


def test_missing_species_statement(checker):
    # No mention of dog or cat
    text = """
    Wild Salmon Crunch Bites
    NET WT 4 OZ (113 g)
    Guaranteed Analysis:
    Crude Protein (min): 30.0%
    Crude Fat (min): 15.0%
    Crude Fiber (max): 2.0%
    Moisture (max): 10.0%
    Ingredients: Wild Salmon.
    Feeding Guidelines: Feed as a reward.
    This product is intended for intermittent or supplemental feeding only.
    Manufactured for: Salmon Pups, Portland, OR 97201
    """
    res = checker.check_label(text, product_name="Wild Salmon Crunch Bites", expected_type="treat")
    assert res.is_compliant is False
    species_violation = next((v for v in res.violations if "Species" in v.element), None)
    assert species_violation is not None
    assert species_violation.severity == "CRITICAL"


def test_empty_label_text(checker):
    res = checker.check_label("", product_name="Empty Label", expected_type="treat")
    assert res.is_compliant is False
    assert res.score == 0
    assert len(res.violations) == 1
    assert res.violations[0].severity == "CRITICAL"
