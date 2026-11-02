"""
Command-Line Interface for Pet Feed Law Compliance Ops Engine.
"""

import sys
import os

# Ensure package root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
from typing import List

from pet_feed_reg_compliance.rules_engine.engine import PetFeedRulesEngine
from pet_feed_reg_compliance.rules_engine.models import ClientProfile, ProductSpec, FacilitySpec
from pet_feed_reg_compliance.label_checker.checker import LabelComplianceChecker
from pet_feed_reg_compliance.calendar_generator.calendar_gen import RenewalCalendarGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Pet Feed Law Compliance Ops Engine (50-State Rules, Label Auditor, Calendar Generator)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: audit-state
    p_state = subparsers.add_parser("audit-state", help="Inspect single state feed regulations & fee structure")
    p_state.add_argument("state", help="2-letter postal code or full state name (e.g. CA, Texas)")

    # Command: list-states
    subparsers.add_parser("list-states", help="List all 50 states and their registration types")

    # Command: check-label
    p_label = subparsers.add_parser("check-label", help="Audit product label text for AAFCO/FDA compliance")
    p_label.add_argument("--file", help="Path to text file containing label text")
    p_label.add_argument("--text", help="Raw label text string")
    p_label.add_argument("--name", default="Sample Product", help="Product name")
    p_label.add_argument("--type", choices=["treat", "complete_food"], default="treat", help="Product category")

    # Command: audit-client
    p_client = subparsers.add_parser("audit-client", help="Run 50-state or target-state gap audit on client JSON")
    p_client.add_argument("client_json", help="Path to ClientProfile JSON specification")
    p_client.add_argument("--year", type=int, default=2026, help="Audit year")
    p_client.add_argument("--output-report", help="Save markdown gap report to file")

    # Command: generate-calendar
    p_cal = subparsers.add_parser("generate-calendar", help="Generate ICS and CSV renewal calendar for client")
    p_cal.add_argument("client_json", help="Path to ClientProfile JSON specification")
    p_cal.add_argument("--year", type=int, default=2026, help="Calendar year")
    p_cal.add_argument("--ics-out", default="renewal_calendar.ics", help="Output path for .ics calendar")
    p_cal.add_argument("--csv-out", default="renewal_calendar.csv", help="Output path for .csv calendar")
    p_cal.add_argument("--all-targets", action="store_true", help="Include all target states, not just registered")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    engine = PetFeedRulesEngine()

    if args.command == "list-states":
        print(f"{'CODE':<6} | {'STATE NAME':<20} | {'REG TYPE':<22} | {'CYCLE':<12} | {'RENEWAL':<15} | {'TONNAGE'}")
        print("-" * 95)
        for code in engine.list_all_states():
            r = engine.get_state_rule(code)
            print(f"{code:<6} | {r['name']:<20} | {r['registration_type']:<22} | {r['cycle']:<12} | {r['renewal_date']:<15} | {r['tonnage_cadence']}")

    elif args.command == "audit-state":
        try:
            rule = engine.get_state_rule(args.state)
            print(f"=== {rule['name']} ({rule['state_code']}) Regulatory Summary ===")
            print(f"Agency:                 {rule['agency']}")
            print(f"Website:                {rule['website']}")
            print(f"Requires Registration:  {rule['requires_registration']}")
            print(f"Registration Type:      {rule['registration_type']}")
            print(f"Cycle:                  {rule['cycle']} (Renewal: {rule['renewal_date']})")
            print(f"Facility License Fee:   ${rule['facility_fee']:.2f}")
            print(f"Product Fee (<=10 lb):  ${rule['product_fee_small_pkg']:.2f}")
            print(f"Product Fee (>10 lb):   ${rule['product_fee_large_pkg']:.2f}")
            print(f"Small Package Rule:     {rule['small_package_rule']}")
            print(f"Tonnage Cadence:        {rule['tonnage_cadence']} (Rate: ${rule['tonnage_fee_per_ton']:.2f}/ton, Min: ${rule['tonnage_min_fee']:.2f})")
            print(f"Small Pkg Tonnage Exmpt:{rule['small_pkg_tonnage_exempt']}")
            print(f"Stop-Sale Authority:    {rule['stop_sale_authority']}")
            print(f"Notes:                  {rule['notes']}")
        except KeyError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "check-label":
        label_text = ""
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                label_text = f.read()
        elif args.text:
            label_text = args.text
        else:
            print("Error: Provide --file or --text", file=sys.stderr)
            sys.exit(1)

        checker = LabelComplianceChecker()
        result = checker.check_label(label_text, product_name=args.name, expected_type=args.type)
        print(f"\n=== Label Audit: {result.product_name} ===")
        print(f"Status:  {'COMPLIANT' if result.is_compliant else 'DEFICIENT'} (Score: {result.score}/100)")
        print(f"Summary: {result.summary}\n")

        print("--- Passed Elements ---")
        for p in result.passed_checks:
            print(f"  ✓ {p}")

        if result.violations:
            print("\n--- Identified Infractions & Deficiencies ---")
            for v in result.violations:
                print(f"  [{v.severity}] {v.element} (Ref: {v.citation}):")
                print(f"    Issue: {v.issue}")
                print(f"    Fix:   {v.recommended_fix}")

    elif args.command == "audit-client":
        with open(args.client_json, "r", encoding="utf-8") as f:
            c_data = json.load(f)
        client = ClientProfile(**c_data)
        report = engine.generate_gap_audit_report(client, year=args.year)
        if args.output_report:
            with open(args.output_report, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"[OK] Report written to: {args.output_report}")
        else:
            print(report)

    elif args.command == "generate-calendar":
        with open(args.client_json, "r", encoding="utf-8") as f:
            c_data = json.load(f)
        client = ClientProfile(**c_data)
        cal_gen = RenewalCalendarGenerator(engine)
        events = cal_gen.generate_events_for_client(
            client,
            year=args.year,
            include_unregistered=args.all_targets
        )
        cal_gen.export_ics(events, args.ics_out, calendar_name=f"{client.brand_name} Pet Feed Deadlines {args.year}")
        cal_gen.export_csv(events, args.csv_out, client_name=client.brand_name)
        print(f"[OK] Generated {len(events)} compliance events for {client.brand_name} ({args.year}).")
        print(f"  ICS Calendar: {args.ics_out}")
        print(f"  CSV Schedule: {args.csv_out}")


if __name__ == "__main__":
    main()
