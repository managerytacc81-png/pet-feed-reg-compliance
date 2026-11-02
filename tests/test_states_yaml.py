"""
Unit tests for states.yaml configuration and 50-state schema integrity.
"""

import os
import yaml
import pytest

from pet_feed_reg_compliance.rules_engine.engine import DEFAULT_YAML_PATH, PetFeedRulesEngine

REQUIRED_STATE_KEYS = [
    "state_code",
    "name",
    "agency",
    "website",
    "requires_registration",
    "registration_type",
    "cycle",
    "renewal_date",
    "facility_fee",
    "product_fee_small_pkg",
    "product_fee_large_pkg",
    "small_package_threshold_lbs",
    "small_package_rule",
    "tonnage_cadence",
    "tonnage_fee_per_ton",
    "tonnage_min_fee",
    "small_pkg_tonnage_exempt",
    "stop_sale_authority",
    "notes"
]

ALL_50_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]


def test_states_yaml_exists():
    assert os.path.exists(DEFAULT_YAML_PATH), f"states.yaml missing at {DEFAULT_YAML_PATH}"


def test_states_yaml_metadata():
    with open(DEFAULT_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "version" in data
    assert "last_updated" in data
    assert "states" in data
    assert len(data["states"]) == 50


def test_all_50_states_present():
    with open(DEFAULT_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    states = data["states"]
    for code in ALL_50_STATES:
        assert code in states, f"State {code} missing from states.yaml"


@pytest.mark.parametrize("state_code", ALL_50_STATES)
def test_state_schema_completeness(state_code):
    with open(DEFAULT_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rule = data["states"][state_code]
    for key in REQUIRED_STATE_KEYS:
        assert key in rule, f"State {state_code} missing required field '{key}'"

    assert rule["state_code"] == state_code
    assert isinstance(rule["requires_registration"], bool)
    assert rule["registration_type"] in ["product", "facility_license", "facility_and_product", "product_and_facility", "exempt"]
    assert rule["cycle"] in ["annual", "biennial", "permanent", "exempt"]
    assert rule["tonnage_cadence"] in ["quarterly", "semiannual", "annual", "none"]
    assert isinstance(rule["facility_fee"], (int, float))
    assert isinstance(rule["product_fee_small_pkg"], (int, float))
    assert isinstance(rule["product_fee_large_pkg"], (int, float))


def test_alaska_is_exempt():
    engine = PetFeedRulesEngine()
    ak = engine.get_state_rule("AK")
    assert ak["requires_registration"] is False
    assert ak["registration_type"] == "exempt"
    assert ak["cycle"] == "exempt"


def test_texas_specific_rules():
    engine = PetFeedRulesEngine()
    tx = engine.get_state_rule("TX")
    assert tx["small_package_threshold_lbs"] == 5.0
    assert tx["product_fee_small_pkg"] == 50.0
    assert tx["facility_fee"] == 75.0
    assert "141.121" in tx["stop_sale_authority"]


def test_north_carolina_specific_rules():
    engine = PetFeedRulesEngine()
    nc = engine.get_state_rule("NC")
    assert nc["small_package_threshold_lbs"] == 5.0
    assert nc["product_fee_small_pkg"] == 40.0
    assert nc["tonnage_cadence"] == "quarterly"


def test_iowa_stop_sale_citation():
    engine = PetFeedRulesEngine()
    ia = engine.get_state_rule("IA")
    assert "198.11" in ia["stop_sale_authority"]
    assert ia["product_fee_small_pkg"] == 50.0
