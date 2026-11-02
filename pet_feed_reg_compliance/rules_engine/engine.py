"""
50-State Pet Feed Regulatory Compliance Rules Engine.
Encodes state Department of Agriculture requirements, fee algorithms, renewal cycles,
and statutory stop-sale risks for commercial pet food, treat, and specialty pet brands.
"""

import os
from typing import Dict, List, Optional, Any, Union
import yaml

from pet_feed_reg_compliance.rules_engine.models import (
    ProductSpec,
    FacilitySpec,
    ClientProfile,
    StateFeeBreakdown,
    PortfolioAuditQuote
)

DEFAULT_YAML_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "states.yaml"
)

INCUMBENT_BENCHMARK_PER_STATE = 175.0  # PetFoodCompliance.com market baseline ($150-$200/state)
OPS_ENGINE_PER_STATE_FEE = 95.0        # Autonomous ops engine pricing


class PetFeedRulesEngine:
    """Core rules engine evaluating multi-state pet food registration and fee compliance."""

    def __init__(self, yaml_path: Optional[str] = None):
        self.yaml_path = yaml_path or DEFAULT_YAML_PATH
        self.states_data: Dict[str, Any] = {}
        self.state_names_to_code: Dict[str, str] = {}
        self.load_rules(self.yaml_path)

    def load_rules(self, path: str) -> None:
        """Load and index state regulations from versioned states.yaml."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"State rules configuration not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.version = data.get("version", "unknown")
        self.last_updated = data.get("last_updated", "unknown")
        self.states_data = data.get("states", {})

        for code, info in self.states_data.items():
            self.state_names_to_code[info["name"].lower()] = code
            self.state_names_to_code[code.lower()] = code

    def get_state_code(self, identifier: str) -> str:
        """Normalize state code or full state name to uppercase 2-letter postal code."""
        clean = identifier.strip().lower()
        if clean in self.state_names_to_code:
            return self.state_names_to_code[clean]
        if clean.upper() in self.states_data:
            return clean.upper()
        raise KeyError(f"Unknown state identifier: '{identifier}'. Must be a valid US state.")

    def get_state_rule(self, identifier: str) -> Dict[str, Any]:
        """Fetch raw state regulatory dictionary by code or name."""
        code = self.get_state_code(identifier)
        return self.states_data[code]

    def list_all_states(self) -> List[str]:
        """Return sorted list of all 50 state codes."""
        return sorted(list(self.states_data.keys()))

    def calculate_state_fees(
        self,
        client: ClientProfile,
        state_identifier: str,
        year: int = 2026
    ) -> StateFeeBreakdown:
        """
        Calculate precise statutory state fees (facility, product registration, tonnage)
        and risk profile for a client in a specific state.
        """
        code = self.get_state_code(state_identifier)
        rule = self.states_data[code]

        if not rule.get("requires_registration", True):
            # Exempt state (e.g. Alaska)
            return StateFeeBreakdown(
                state_code=code,
                state_name=rule["name"],
                requires_registration=False,
                registration_type=rule.get("registration_type", "exempt"),
                cycle=rule.get("cycle", "exempt"),
                renewal_date=rule.get("renewal_date", "None"),
                renewal_month=rule.get("renewal_month"),
                renewal_day=rule.get("renewal_day"),
                facility_fee=0.0,
                product_registration_fee=0.0,
                tonnage_inspection_fee=0.0,
                total_state_fee=0.0,
                tonnage_cadence=rule.get("tonnage_cadence", "none"),
                small_pkg_tonnage_exempt=True,
                stop_sale_authority=rule.get("stop_sale_authority", "None"),
                compliance_notes=rule.get("notes", "State does not regulate commercial feed."),
                is_registered=True,
                is_gap=False,
                risk_level="LOW"
            )

        # 1. Facility License Fee
        facility_fee = 0.0
        has_local_facility = any(f.state.upper() == code for f in client.facilities)
        base_fac_fee = float(rule.get("facility_fee", 0.0))

        if rule.get("registration_type") in ["facility_license", "facility_and_product", "product_and_facility"]:
            if code == "FL":
                # Master registration fee based on tonnage
                total_tons = sum(p.annual_projected_tons for p in client.products)
                if total_tons <= 25.0:
                    facility_fee = 40.0
                elif total_tons <= 50.0:
                    facility_fee = 100.0
                else:
                    facility_fee = 200.0
            elif code == "CA":
                facility_fee = 500.0 if has_local_facility else 500.0
            elif code == "WI":
                facility_fee = 25.0  # out-of-state facility fee
            else:
                facility_fee = base_fac_fee

        # 2. Product Registration Fees
        product_fee_total = 0.0
        threshold_lbs = float(rule.get("small_package_threshold_lbs", 10.0))
        fee_small = float(rule.get("product_fee_small_pkg", 0.0))
        fee_large = float(rule.get("product_fee_large_pkg", 0.0))

        if rule.get("registration_type") in ["product", "facility_and_product", "product_and_facility"]:
            for prod in client.products:
                # State-specific logic
                if code == "OR":
                    # In Oregon, standard dog and cat foods are exempt if distributed by licensed entity
                    if prod.is_specialty_pet:
                        product_fee_total += fee_small
                elif code == "NC":
                    if prod.is_canned:
                        product_fee_total += 12.0
                    elif prod.package_weight_lbs <= 5.0:
                        product_fee_total += 40.0
                    else:
                        product_fee_total += 5.0
                elif code == "ND":
                    # Biennial fee ($100 renewal / $120 new) -> $50/yr equivalent
                    product_fee_total += 50.0
                elif code == "WA":
                    # Washington: pet/specialty pet <=10 lb is biennial $90 ($45/yr), >10 lb is $22/yr
                    if prod.package_weight_lbs <= 10.0:
                        product_fee_total += 45.0
                    else:
                        product_fee_total += 22.0
                else:
                    # General logic based on small vs large package threshold
                    if prod.package_weight_lbs <= threshold_lbs:
                        product_fee_total += fee_small
                    else:
                        product_fee_total += fee_large

        # 3. Tonnage Inspection Fees
        tonnage_fee = 0.0
        tonnage_cadence = rule.get("tonnage_cadence", "none")
        rate_per_ton = float(rule.get("tonnage_fee_per_ton", 0.0))
        min_ton_fee = float(rule.get("tonnage_min_fee", 0.0))
        small_exempt = rule.get("small_pkg_tonnage_exempt", True)

        all_small = all(p.package_weight_lbs <= threshold_lbs for p in client.products) if client.products else True

        if tonnage_cadence != "none" and rate_per_ton > 0.0:
            if all_small and small_exempt:
                # Small package flat fee paid in lieu of tonnage
                tonnage_fee = 0.0
            else:
                # Calculate tonnage for large packages or non-exempt states
                non_exempt_tons = sum(
                    p.annual_projected_tons
                    for p in client.products
                    if not (small_exempt and p.package_weight_lbs <= threshold_lbs)
                )
                calculated_fee = non_exempt_tons * rate_per_ton
                tonnage_fee = max(calculated_fee, min_ton_fee)

        total_state_fee = round(facility_fee + product_fee_total + tonnage_fee, 2)

        # Gap and Risk Evaluation
        is_registered = code in [s.upper() for s in client.currently_registered_states]
        is_target = code in [s.upper() for s in client.target_states]
        is_gap = is_target and not is_registered

        # High-enforcement stop-sale jurisdictions
        critical_enforcement_states = ["VA", "IA", "WV", "CA", "TX", "FL", "NC", "GA", "OH"]
        if is_gap:
            risk_level = "CRITICAL" if code in critical_enforcement_states else "MEDIUM"
        else:
            risk_level = "LOW"

        return StateFeeBreakdown(
            state_code=code,
            state_name=rule["name"],
            requires_registration=True,
            registration_type=rule.get("registration_type", "product"),
            cycle=rule.get("cycle", "annual"),
            renewal_date=rule.get("renewal_date", "January 1"),
            renewal_month=rule.get("renewal_month"),
            renewal_day=rule.get("renewal_day"),
            facility_fee=round(facility_fee, 2),
            product_registration_fee=round(product_fee_total, 2),
            tonnage_inspection_fee=round(tonnage_fee, 2),
            total_state_fee=total_state_fee,
            tonnage_cadence=tonnage_cadence,
            small_pkg_tonnage_exempt=small_exempt,
            stop_sale_authority=rule.get("stop_sale_authority", "State Feed Law"),
            compliance_notes=rule.get("notes", ""),
            is_registered=is_registered,
            is_gap=is_gap,
            risk_level=risk_level
        )

    def calculate_portfolio(
        self,
        client: ClientProfile,
        target_states: Optional[List[str]] = None,
        year: int = 2026
    ) -> PortfolioAuditQuote:
        """
        Evaluate full portfolio compliance across specified target states (or all 50 states).
        Computes statutory fees, commercial benchmark against PetFoodCompliance.com, and client savings.
        """
        states_to_eval = target_states or client.target_states or self.list_all_states()
        states_to_eval = [self.get_state_code(s) for s in states_to_eval]

        breakdowns: Dict[str, StateFeeBreakdown] = {}
        total_statutory = 0.0
        unregistered = []
        critical_states = []

        for st in states_to_eval:
            sb = self.calculate_state_fees(client, st, year=year)
            breakdowns[st] = sb
            total_statutory += sb.total_state_fee
            if sb.is_gap:
                unregistered.append(st)
                if sb.risk_level == "CRITICAL":
                    critical_states.append(st)

        state_count = len(states_to_eval)
        # Commercial benchmarking
        incumbent_benchmark = round(state_count * INCUMBENT_BENCHMARK_PER_STATE, 2)
        ops_engine_fee = round(state_count * OPS_ENGINE_PER_STATE_FEE, 2)
        savings = round(incumbent_benchmark - ops_engine_fee, 2)

        return PortfolioAuditQuote(
            client_name=client.company_name or client.brand_name,
            year=year,
            target_state_count=state_count,
            total_products=len(client.products),
            state_breakdowns=breakdowns,
            total_statutory_state_fees=round(total_statutory, 2),
            incumbent_benchmark_usd=incumbent_benchmark,
            ops_engine_prep_fee_usd=ops_engine_fee,
            client_savings_usd=savings,
            unregistered_target_states=unregistered,
            critical_stop_sale_states=critical_states
        )

    def audit_registration_gaps(self, client: ClientProfile, year: int = 2026) -> Dict[str, Any]:
        """Perform rapid registration gap audit against a client's selling footprint."""
        quote = self.calculate_portfolio(client, year=year)
        gap_breakdowns = [b for b in quote.state_breakdowns.values() if b.is_gap]
        gap_statutory_fees = sum(b.total_state_fee for b in gap_breakdowns)

        return {
            "client_name": client.company_name,
            "brand_name": client.brand_name,
            "target_states_total": len(client.target_states),
            "currently_registered_total": len(client.currently_registered_states),
            "unregistered_gap_count": len(gap_breakdowns),
            "unregistered_states": quote.unregistered_target_states,
            "critical_risk_states": quote.critical_stop_sale_states,
            "statutory_fees_due_usd": round(gap_statutory_fees, 2),
            "incumbent_cost_quote_usd": round(len(gap_breakdowns) * INCUMBENT_BENCHMARK_PER_STATE, 2),
            "free_gap_audit_states_offered": quote.unregistered_target_states[:3],
            "gaps": [
                {
                    "state": b.state_code,
                    "state_name": b.state_name,
                    "statutory_fee": b.total_state_fee,
                    "risk": b.risk_level,
                    "stop_sale_authority": b.stop_sale_authority,
                    "notes": b.compliance_notes
                }
                for b in gap_breakdowns
            ]
        }

    def generate_gap_audit_report(self, client: ClientProfile, year: int = 2026) -> str:
        """Generate executive-ready markdown report for client gap audit."""
        audit = self.audit_registration_gaps(client, year=year)
        lines = [
            f"# State Regulatory Compliance & Registration-Gap Audit",
            f"**Brand:** {client.brand_name} ({client.company_name})  ",
            f"**Contact:** {client.contact_name} ({client.contact_email})  ",
            f"**Audit Date:** November 02, 2026 | **Audit Year:** {year}  ",
            f"**Regulatory Framework:** AAFCO 2023 Model Pet Food Regulations & State Depts of Agriculture  ",
            "",
            "## 1. Executive Summary & Statutory Exposure",
            f"- **Target Selling Footprint:** {audit['target_states_total']} states",
            f"- **Active State Registrations:** {audit['currently_registered_total']} states",
            f"- **Identified Compliance Gaps:** {audit['unregistered_gap_count']} unregistered states",
            f"- **Critical Stop-Sale Exposure Jurisdictions:** {', '.join(audit['critical_risk_states']) if audit['critical_risk_states'] else 'None'}",
            f"- **Total Outstanding Statutory State Fees:** ${audit['statutory_fees_due_usd']:,.2f}",
            "",
            "## 2. Competitive Price Comparison",
            f"| Provider | Scope | Preparation Fee | Statutory State Fees | Total Client Investment |",
            f"| :--- | :--- | :--- | :--- | :--- |",
            f"| **PetFoodCompliance.com (Incumbent)** | {audit['unregistered_gap_count']} States | ${audit['incumbent_cost_quote_usd']:,.2f} ($175/state) | ${audit['statutory_fees_due_usd']:,.2f} | ${(audit['incumbent_cost_quote_usd'] + audit['statutory_fees_due_usd']):,.2f} |",
            f"| **Pet Feed Law Ops Engine** | **First 3 States Free Gap-Audit** + ${OPS_ENGINE_PER_STATE_FEE}/st | ${(max(0, audit['unregistered_gap_count'] - 3) * OPS_ENGINE_PER_STATE_FEE):,.2f} | ${audit['statutory_fees_due_usd']:,.2f} | ${(max(0, audit['unregistered_gap_count'] - 3) * OPS_ENGINE_PER_STATE_FEE + audit['statutory_fees_due_usd']):,.2f} |",
            f"| **Net Client Savings** | | **${(audit['incumbent_cost_quote_usd'] - max(0, audit['unregistered_gap_count'] - 3) * OPS_ENGINE_PER_STATE_FEE):,.2f}** | | **{(1.0 - (max(0, audit['unregistered_gap_count'] - 3) * OPS_ENGINE_PER_STATE_FEE) / max(1, audit['incumbent_cost_quote_usd'])) * 100:.1f}% Savings** |",
            "",
            "## 3. High-Priority State Gaps & Legal Risk",
            "| State | Statutory Fee | Risk Level | Stop-Sale Authority Citation | Regulatory Requirement & Cadence |",
            "| :---: | :---: | :---: | :--- | :--- |"
        ]

        for g in audit["gaps"]:
            lines.append(
                f"| **{g['state']}** | ${g['statutory_fee']:.2f} | `{g['risk']}` | {g['stop_sale_authority']} | {g['notes']} |"
            )

        lines.extend([
            "",
            "## 4. Immediate Recommended Action",
            "1. **Claim Free 3-State Audit Pack:** We immediately prepare and file registration dossiers for your top 3 revenue-generating gap states at zero preparation charge.",
            "2. **Continuous Renewal & Tonnage Retainer:** Lock in 50-state calendar monitoring and quarterly/semiannual tonnage filings for $300-$500/month.",
            "3. **Stop-Sale Immunity:** Protect your D2C fulfillment and wholesale distribution against immediate state embargo orders."
        ])

        return "\n".join(lines)
