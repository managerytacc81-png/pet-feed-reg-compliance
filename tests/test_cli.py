"""
End-to-end tests for the CLI commands.
"""

import os
import json
import subprocess
import pytest

CLI_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "pet_feed_reg_compliance",
    "cli.py"
)


def run_cli(*args):
    cmd = ["python3", CLI_PATH] + list(args)
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res


def test_cli_help():
    res = run_cli("--help")
    assert res.returncode == 0
    assert "Pet Feed Law Compliance Ops Engine" in res.stdout


def test_cli_list_states():
    res = run_cli("list-states")
    assert res.returncode == 0
    assert "CA" in res.stdout
    assert "TX" in res.stdout
    assert "AK" in res.stdout
    assert "FL" in res.stdout


def test_cli_audit_state():
    res = run_cli("audit-state", "California")
    assert res.returncode == 0
    assert "California (CA) Regulatory Summary" in res.stdout
    assert "Cal. Food & Agric. Code § 15071" in res.stdout


def test_cli_check_label_compliant():
    text = (
        "WagWell Treats for Dogs. NET WT 8 OZ (227 g). "
        "Guaranteed Analysis: Crude Protein (min) 20%, Crude Fat (min) 10%, Crude Fiber (max) 3%, Moisture (max) 12%. "
        "Ingredients: Duck, Sweet Potato. Feeding Guidelines: Feed as a treat. "
        "This product is intended for intermittent or supplemental feeding only. "
        "Manufactured for: WagWell Pets LLC, Denver, CO 80202."
    )
    res = run_cli("check-label", "--name", "WagWell Treats", "--text", text)
    assert res.returncode == 0
    assert "Status:  COMPLIANT" in res.stdout
    assert "Score: 100/100" in res.stdout


def test_cli_audit_client(tmp_path):
    client_data = {
        "client_id": "test-cli-01",
        "company_name": "Test Pet Co",
        "brand_name": "TestPets",
        "contact_name": "Alex Smith",
        "contact_email": "alex@testpets.com",
        "target_states": ["CA", "TX", "VA"],
        "currently_registered_states": ["CA"],
        "products": [
            {
                "sku": "TP-01",
                "name": "Test Treat",
                "brand": "TestPets",
                "package_weight_lbs": 0.5
            }
        ]
    }
    client_json = os.path.join(tmp_path, "client.json")
    with open(client_json, "w") as f:
        json.dump(client_data, f)

    report_out = os.path.join(tmp_path, "report.md")
    res = run_cli("audit-client", client_json, "--output-report", report_out)
    assert res.returncode == 0
    assert os.path.exists(report_out)
    with open(report_out) as f:
        content = f.read()
    assert "TestPets" in content
    assert "PetFoodCompliance.com" in content


def test_cli_generate_calendar(tmp_path):
    client_data = {
        "client_id": "test-cli-02",
        "company_name": "Test Calendar Co",
        "brand_name": "TestCal",
        "contact_name": "Alex Smith",
        "contact_email": "alex@testcal.com",
        "target_states": ["CA", "CO"],
        "currently_registered_states": ["CO"],
        "products": [
            {
                "sku": "TC-01",
                "name": "Cal Treat",
                "brand": "TestCal",
                "package_weight_lbs": 0.5
            }
        ]
    }
    client_json = os.path.join(tmp_path, "client.json")
    with open(client_json, "w") as f:
        json.dump(client_data, f)

    ics_out = os.path.join(tmp_path, "cal.ics")
    csv_out = os.path.join(tmp_path, "cal.csv")
    res = run_cli("generate-calendar", client_json, "--ics-out", ics_out, "--csv-out", csv_out)
    assert res.returncode == 0
    assert os.path.exists(ics_out)
    assert os.path.exists(csv_out)
