# Pet Feed Law Compliance Ops Engine (`pet-feed-reg-compliance`)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![AAFCO Compliance](https://img.shields.io/badge/AAFCO-2023%20Model%20Regulations-green.svg)](https://www.aafco.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 82/82 Passed](https://img.shields.io/badge/Tests-82%20Passed%20(100%25)-brightgreen.svg)](tests/)

**An autonomous regulatory intelligence and operations engine for indie US pet treat and pet food brands.** Encodes 50-state Department of Agriculture commercial feed registration matrices, performs automated AAFCO/FDA label audits, schedules multi-state renewal calendars with mandatory FDA biennial registrations, and automates high-margin commercial client acquisition.

---

## 1. Problem & Commercial Opportunity

### The Multi-State Regulatory Minefield
In the United States, commercial pet food and pet treat distribution is **not** centrally registered at the federal level. Instead, each individual state's Department of Agriculture (e.g., California CDFA, Texas OTSC, Florida FDACS, Virginia VDACS) exercises independent statutory jurisdiction over animal feed distributed within its borders:
1. **Mandatory Prior Registration:** 49 of 50 states require prior product registration or commercial feed facility licensing before a single bag or pouch can legally be shipped or sold.
2. **Draconian Stop-Sale Orders:** Regulators routinely issue immediate statewide **Stop-Sale, Embargo, and Seizure orders** (e.g., *Virginia Code § 3.2-4804*, *Iowa Code § 198.11*, *Cal. Food & Agric. Code § 15071*) when unregistered products are detected in retail distribution or direct fulfillment centers.
3. **Small-Package (<10 lb) & Tonnage Thresholds:** States enforce divergent fee mechanisms: flat small-package brand fees (often $25–$100/SKU) that exempt products from quarterly tonnage taxes vs. strict 5-lb cutoffs in Texas and North Carolina where products over 5.0 lbs trigger quarterly tonnage affidavits and minimum fees.
4. **FDA Biennial Facility Registration:** Under Section 415 of the FD&C Act (21 U.S.C. § 350d), all animal food processing facilities must renew their federal facility registration between **October 1 and December 31 of even-numbered years** (e.g., 2026, 2028). Failure to renew leads to automatic facility de-registration and federal import/interstate distribution embargo.

### The Incumbent Monopoly & Value Arbitrage
Incumbent regulatory consultancies (such as *PetFoodCompliance.com*) maintain manual, high-friction filing workflows:
- **Incumbent Pricing:** $150–$200 per state for initial registration filings, $175 per state on annual renewals, and $325/hour for label reviews. A brand expanding nationwide faces **$7,500 to $10,000+** in legacy consulting overhead on top of state statutory fees.
- **Our Value Wedge:** We provide a **FREE 3-State Registration-Gap & Label Audit** to uncover immediate stop-sale exposure, followed by an all-inclusive 50-state compliance and renewal retainer for **$300–$500/month**—saving emerging indie brands 50–70% while guaranteeing automated calendar protection.

---

## 2. Clean Architecture & System Design

```
pet-feed-reg-compliance/
├── pet_feed_reg_compliance/
│   ├── data/
│   │   └── states.yaml              # Authoritative 50-state Dept of Ag regulatory matrix
│   ├── rules_engine/
│   │   ├── __init__.py
│   │   ├── models.py                # Pydantic schemas (ProductSpec, FacilitySpec, ClientProfile)
│   │   └── engine.py                # Fee calculator, gap analyzer, and statutory risk scorer
│   ├── label_checker/
│   │   ├── __init__.py
│   │   └── checker.py               # 8-point AAFCO/FDA label compliance & penalty detector
│   ├── calendar_generator/
│   │   ├── __init__.py
│   │   └── calendar_gen.py          # RFC 5545 (.ics) & CSV generator with FDA Biennial window
│   ├── leads/
│   │   ├── verified_leads.json      # 26 verified indie US D2C pet brands (MX-checked)
│   │   └── verified_leads.csv       # Tabular lead export with founder phones and evidence
│   ├── cli.py                       # Unified command-line interface
│   └── __init__.py
├── tests/
│   ├── conftest.py                  # Pytest environment configuration
│   ├── test_states_yaml.py          # 50-state schema & completeness validation
│   ├── test_rules_engine.py         # Statutory fee math, exemptions, and quote auditing
│   ├── test_label_checker.py        # AAFCO PDP, GA sequence, net weight, & treat rules
│   ├── test_calendar_generator.py   # ICS RFC 5545 validation, alarms, & FDA even-year test
│   └── test_cli.py                  # End-to-end CLI integration tests
├── pyproject.toml                   # Standard packaging & dependency specification
└── README.md                        # Production architecture & usage documentation
```

---

## 3. Core Modules & Engine Capabilities

### A. 50-State Rules Engine (`pet_feed_reg_compliance/rules_engine/`)
- Encodes requirements from official state Departments of Agriculture and the 2023 AAFCO Official Publication Summary across all 50 US jurisdictions:
  - **Exempt Jurisdictions:** Correctly identifies Alaska (AK) as having zero state-level commercial feed registration requirements.
  - **Permanent vs. Annual vs. Biennial Cycles:** Encodes North Dakota biennial even-year renewals, Washington July 1 biennial pet food cycles, Texas permanent facility licenses with September 1 renewal windows, and California $500 CDFA licenses.
  - **Small-Package Cutoffs:** Implements divergent thresholds (<=10 lbs in 45 states; strict <=5 lbs in TX, NC, MI).
  - **Tonnage Cadences:** Handles quarterly, semiannual, and annual tonnage affidavits with statutory minimums.

### B. AAFCO & FDA Label Compliance Auditor (`pet_feed_reg_compliance/label_checker/`)
Audits product packaging artwork and text against mandatory federal (21 CFR § 501) and state regulations:
1. **Brand & Product Name (PF2):** Verifies percentage rules (100% rule, 95% rule, 25% Dinner/Recipe rule, 3% With rule, Flavor rule).
2. **Species & Purpose Statement (PF2/PF3):** Ensures clear principal display panel identification ("for dogs", "dog treats", "cat food").
3. **Dual Net Quantity Statement (PF3, 21 CFR § 501.105, FPLA):** Strictly verifies both US Customary (`oz`/`lb`) AND Metric (`g`/`kg`) declarations. Missing metric units is flagged as a MAJOR statutory defect.
4. **Guaranteed Analysis (PF4):** Strictly enforces mandatory statutory ordering:
   - Crude Protein (min)
   - Crude Fat (min)
   - Crude Fiber (max)
   - Moisture (max)
5. **Descending Ingredient Deck (PF5, 21 CFR § 501.4):** Confirms comma-separated descending weight listing using common/usual names.
6. **Manufacturer/Distributor Responsibility (PF6, 21 CFR § 501.5):** Validates "Manufactured for..." qualification and City, State, ZIP.
7. **Directions for Use (PF7):** Validates structured feeding guides for complete diets and caloric limitation disclaimers for treats.
8. **AAFCO Nutritional Adequacy Statement (PF8):** Verifies life-stage formulation claims or the mandatory treat disclaimer: *"This product is intended for intermittent or supplemental feeding only."*

### C. Renewal Calendar Generator (`pet_feed_reg_compliance/calendar_generator/`)
- Generates standard **RFC 5545 iCalendar (`.ics`)** files with pre-configured VALARM reminders (30 days, 14 days, 1 day prior).
- Emits structured **CSV** spreadsheets for Airtable, Excel, or Asana imports.
- Encodes state registration renewals, quarterly/semiannual tonnage filings, and the **FDA Biennial Food Facility Registration (October 1 – December 31 of even years)** under 21 U.S.C. § 350d.

---

## 4. Installation & Quickstart

```bash
# Clone repository
git clone https://github.com/managerytacc81-png/pet-feed-reg-compliance.git
cd pet-feed-reg-compliance

# Install dependencies in virtual environment
pip install -e .
```

### CLI Usage Examples

#### 1. Inspect State Regulatory Rules
```bash
python3 pet_feed_reg_compliance/cli.py audit-state Texas
python3 pet_feed_reg_compliance/cli.py audit-state California
python3 pet_feed_reg_compliance/cli.py list-states
```

#### 2. Audit Product Label for AAFCO Compliance
```bash
python3 pet_feed_reg_compliance/cli.py check-label \
  --name "Organic Duck Chews" \
  --text "Organic Duck Chews for Dogs. Net Wt 8 oz (227 g). Guaranteed Analysis: Crude Protein (min) 20%, Crude Fat (min) 10%, Crude Fiber (max) 3%, Moisture (max) 12%. Ingredients: Duck, Sweet Potato. Feeding Guidelines: Feed as a treat. This product is intended for intermittent or supplemental feeding only. Manufactured for: DuckPups LLC, Austin, TX 78701."
```

#### 3. Run Client Gap-Audit & Price Comparison
```bash
python3 pet_feed_reg_compliance/cli.py audit-client client_sample.json --year 2026
```

#### 4. Generate ICS & CSV Compliance Calendar
```bash
python3 pet_feed_reg_compliance/cli.py generate-calendar client_sample.json \
  --year 2026 \
  --ics-out client_calendar.ics \
  --csv-out client_calendar.csv \
  --all-targets
```

---

## 5. Verification & Pytest Suite

The entire suite of **82 tests** covers all 50 states, label parsing logic, fee edge-cases, calendar RFC 5545 formatting, and CLI interfaces:

```bash
python3 -m pytest tests/ -v
```

```text
======================== 82 passed in 4.47s ========================
- test_calendar_generator.py (4 tests: even-year FDA, odd-year, ICS RFC5545, CSV)
- test_cli.py                (6 tests: help, list, state-audit, label, client, cal)
- test_label_checker.py      (6 tests: compliant, metric missing, GA missing, sequence, species, empty)
- test_rules_engine.py       (9 tests: state normalization, Alaska, CO, TX, VA, quotes, gap audit)
- test_states_yaml.py        (57 tests: 50 states schema validation, metadata, TX/NC/IA specifics)
```

---

## 6. Verified Lead Intelligence & Outbox

The repository includes a curated, fully verified commercial dataset of **26 indie US D2C pet treat & food brands**:
- **Filters:** Founded 2019–2025, <50 employees, active D2C e-commerce + wholesale retail footprint, verified founder/CEO identity, DNS MX-verified corporate email domains, publicly listed phone numbers.
- **Locations:** Stored in [`pet_feed_reg_compliance/leads/verified_leads.json`](pet_feed_reg_compliance/leads/verified_leads.json) and [`verified_leads.csv`](pet_feed_reg_compliance/leads/verified_leads.csv).
- **Outbox Packet:** Located at `~/Desktop/REVENUE_ACTIONS_TONIGHT/pet-feed-reg-compliance_OUTBOX.md` with 1-click `mailto:` links, pre-drafted subject lines, and personalized pitches.

---

## License

MIT License. Designed and executed under the Maximum Autonomous AI Execution Protocol.
