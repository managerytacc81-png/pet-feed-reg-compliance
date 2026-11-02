"""
Unit tests for the 50-state pet food registration rules engine.
"""

import pytest
from pet_feed_reg_compliance.rules_engine.engine import PetFeedRulesEngine, INCUMBENT_BENCHMARK_PER_STATE
from pet_feed_reg_compliance.rules_engine.models import ClientProfile, ProductSpec, FacilitySpec


@pytest.fixture
def engine():
    return PetFeedRulesEngine()


@pytest.fixture
def sample_client():
    return ClientProfile(
        client_id="brand-test",
        company_name="Boulder Bark Bites LLC",
        brand_name="Boulder Bark Bites",
        contact_name="Sarah Miller",
        contact_email="sarah@boulderbarkbites.com",
        target_states=["CA", "CO", "TX", "FL", "NY", "VA", "AK"],
        currently_registered_states=["CO"],
        products=[
            ProductSpec(sku="BBB-01", name="Organic Beef Jerky Treats", brand="Boulder Bark Bites", package_weight_lbs=0.5),
            ProductSpec(sku="BBB-02", name="Peanut Butter Crunch", brand="Boulder Bark Bites", package_weight_lbs=1.0),
        ],
        facilities=[
            FacilitySpec(facility_id="FAC-01", facility_name="Boulder Kitchen", state="CO")
        ]
    )


def test_normalize_state_code(engine):
    assert engine.get_state_code("tx") == "TX"
    assert engine.get_state_code("Texas") == "TX"
    assert engine.get_state_code("california") == "CA"
    assert engine.get_state_code("NY") == "NY"


def test_invalid_state_code(engine):
    with pytest.raises(KeyError):
        engine.get_state_code("XYZ")


def test_exempt_state_alaska(engine, sample_client):
    breakdown = engine.calculate_state_fees(sample_client, "AK")
    assert breakdown.requires_registration is False
    assert breakdown.total_state_fee == 0.0
    assert breakdown.is_gap is False
    assert breakdown.risk_level == "LOW"


def test_registered_state_colorado(engine, sample_client):
    breakdown = engine.calculate_state_fees(sample_client, "CO")
    assert breakdown.requires_registration is True
    assert breakdown.is_registered is True
    assert breakdown.is_gap is False
    # CO: $75 company fee + 2 products * $25 = $125
    assert breakdown.total_state_fee == 125.0
    assert breakdown.risk_level == "LOW"


def test_unregistered_gap_texas(engine, sample_client):
    breakdown = engine.calculate_state_fees(sample_client, "TX")
    assert breakdown.is_registered is False
    assert breakdown.is_gap is True
    assert breakdown.risk_level == "CRITICAL"
    # TX: $75 facility + 2 products * $50 = $175
    assert breakdown.total_state_fee == 175.0


def test_unregistered_gap_virginia(engine, sample_client):
    breakdown = engine.calculate_state_fees(sample_client, "VA")
    assert breakdown.is_registered is False
    assert breakdown.is_gap is True
    assert breakdown.risk_level == "CRITICAL"
    # VA: $50 facility + 2 brands/products * $50 = $150
    assert breakdown.total_state_fee == 150.0


def test_portfolio_quote_calculation(engine, sample_client):
    quote = engine.calculate_portfolio(sample_client)
    assert quote.target_state_count == 7
    assert quote.total_products == 2
    assert "AK" not in quote.unregistered_target_states  # AK is exempt
    assert "CO" not in quote.unregistered_target_states  # CO is already registered
    assert set(quote.unregistered_target_states) == {"CA", "TX", "FL", "NY", "VA"}
    assert "TX" in quote.critical_stop_sale_states
    assert "VA" in quote.critical_stop_sale_states

    # Commercial benchmark check
    expected_benchmark = round(7 * INCUMBENT_BENCHMARK_PER_STATE, 2)
    assert quote.incumbent_benchmark_usd == expected_benchmark
    assert quote.client_savings_usd > 0


def test_audit_registration_gaps_summary(engine, sample_client):
    audit = engine.audit_registration_gaps(sample_client)
    assert audit["unregistered_gap_count"] == 5
    assert len(audit["free_gap_audit_states_offered"]) == 3
    assert audit["statutory_fees_due_usd"] > 0


def test_generate_gap_audit_report(engine, sample_client):
    report = engine.generate_gap_audit_report(sample_client)
    assert "# State Regulatory Compliance & Registration-Gap Audit" in report
    assert "Boulder Bark Bites" in report
    assert "PetFoodCompliance.com" in report
    assert "Free Gap-Audit" in report
    assert "Va. Code Ann. § 3.2-4804" in report
