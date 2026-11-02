"""
Unit tests for the Renewal Calendar Generator (ICS & CSV generation).
"""

import os
import csv
import pytest
from datetime import date
from icalendar import Calendar

from pet_feed_reg_compliance.calendar_generator.calendar_gen import RenewalCalendarGenerator
from pet_feed_reg_compliance.rules_engine.models import ClientProfile, ProductSpec, FacilitySpec


@pytest.fixture
def sample_client():
    return ClientProfile(
        client_id="test-cal-01",
        company_name="Neo Bites LLC",
        brand_name="Neo Bites",
        contact_name="Wesley Cooper",
        contact_email="wesley@neobites.com",
        target_states=["CA", "CO", "TX", "FL", "WA", "ND"],
        currently_registered_states=["CO", "CA"],
        products=[
            ProductSpec(sku="NB-01", name="Insect Protein Functional Treat", brand="Neo Bites", package_weight_lbs=0.4),
        ]
    )


def test_calendar_events_generation_even_year(sample_client):
    gen = RenewalCalendarGenerator()
    events = gen.generate_events_for_client(sample_client, year=2026, include_unregistered=True)
    assert len(events) > 0

    # Verify FDA Biennial Food Facility Registration included in even years (2026)
    fda_events = [e for e in events if e.jurisdiction == "US-FDA"]
    assert len(fda_events) == 1
    fda = fda_events[0]
    assert fda.due_date == date(2026, 12, 31)
    assert fda.window_open_date == date(2026, 10, 1)
    assert fda.priority == "CRITICAL"
    assert "Section 415" in fda.statutory_authority


def test_calendar_events_generation_odd_year(sample_client):
    gen = RenewalCalendarGenerator()
    # In odd year (2027), FDA Biennial renewal is NOT triggered
    events = gen.generate_events_for_client(sample_client, year=2027, include_unregistered=True)
    fda_events = [e for e in events if e.jurisdiction == "US-FDA"]
    assert len(fda_events) == 0


def test_ics_export_valid_rfc5545(tmp_path, sample_client):
    gen = RenewalCalendarGenerator()
    events = gen.generate_events_for_client(sample_client, year=2026, include_unregistered=True)
    ics_file = os.path.join(tmp_path, "test.ics")
    gen.export_ics(events, ics_file, calendar_name="Neo Bites Compliance 2026")

    assert os.path.exists(ics_file)
    with open(ics_file, "rb") as f:
        cal = Calendar.from_ical(f.read())

    assert cal["prodid"] == "-//Pet Feed Reg Compliance Ops Engine//EN"
    assert cal["version"] == "2.0"
    vevents = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(vevents) == len(events)

    # Check alarms
    first_event = vevents[0]
    valarms = [c for c in first_event.walk() if c.name == "VALARM"]
    assert len(valarms) == 3  # 30d, 14d, 1d


def test_csv_export_structure(tmp_path, sample_client):
    gen = RenewalCalendarGenerator()
    events = gen.generate_events_for_client(sample_client, year=2026, include_unregistered=True)
    csv_file = os.path.join(tmp_path, "test.csv")
    gen.export_csv(events, csv_file, client_name="Neo Bites")

    assert os.path.exists(csv_file)
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    assert len(reader) == len(events) + 1  # header + data
    headers = reader[0]
    assert "Client Name" in headers
    assert "Jurisdiction" in headers
    assert "Due Date" in headers
    assert "Statutory Fee USD" in headers
    assert "Priority" in headers
