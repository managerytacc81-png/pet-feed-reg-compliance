"""
Commercial Pet Feed Compliance Renewal Calendar Generator.
Emits standard RFC 5545 (.ics) and tabular (.csv) calendars per client
for all 50-state Department of Agriculture renewal deadlines, tonnage reporting schedules,
and the mandatory FDA Biennial Food Facility Registration window (Oct 1 - Dec 31 of even years).
"""

import os
import csv
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Optional, Any
from icalendar import Calendar, Event, Alarm

from pet_feed_reg_compliance.rules_engine.models import ClientProfile, StateFeeBreakdown
from pet_feed_reg_compliance.rules_engine.engine import PetFeedRulesEngine


class ComplianceCalendarEvent:
    """Discrete compliance deadline event."""

    def __init__(
        self,
        event_id: str,
        title: str,
        due_date: date,
        window_open_date: date,
        jurisdiction: str,
        deadline_type: str,  # "Product Renewal", "Facility License", "Tonnage Filing", "FDA Biennial"
        fee_usd: float,
        portal_url: str,
        statutory_authority: str,
        description: str,
        priority: str = "HIGH"  # CRITICAL, HIGH, MEDIUM
    ):
        self.event_id = event_id
        self.title = title
        self.due_date = due_date
        self.window_open_date = window_open_date
        self.jurisdiction = jurisdiction
        self.deadline_type = deadline_type
        self.fee_usd = fee_usd
        self.portal_url = portal_url
        self.statutory_authority = statutory_authority
        self.description = description
        self.priority = priority


class RenewalCalendarGenerator:
    """Generates RFC 5545 (.ics) and CSV compliance calendars for pet food brands."""

    def __init__(self, engine: Optional[PetFeedRulesEngine] = None):
        self.engine = engine or PetFeedRulesEngine()

    def generate_events_for_client(
        self,
        client: ClientProfile,
        year: int = 2026,
        include_unregistered: bool = False
    ) -> List[ComplianceCalendarEvent]:
        """
        Compile all state deadlines, tonnage filings, and FDA registrations for a client.
        """
        events: List[ComplianceCalendarEvent] = []
        states_to_include = (
            client.target_states if include_unregistered else
            (client.currently_registered_states or client.target_states)
        )

        for st_code in states_to_include:
            code = self.engine.get_state_code(st_code)
            rule = self.engine.get_state_rule(code)
            if not rule.get("requires_registration", True):
                continue

            breakdown = self.engine.calculate_state_fees(client, code, year=year)

            # 1. State Registration / Renewal Deadline
            m = rule.get("renewal_month")
            d = rule.get("renewal_day")
            window_days = rule.get("renewal_window_days", 45)

            if m and d:
                # Handle leap year Feb 28/29
                due_d = d
                if m == 2 and d > 28:
                    due_d = 29 if year % 4 == 0 else 28
                due_dt = date(year, m, due_d)
                open_dt = due_dt - timedelta(days=window_days)

                # Check biennial odd/even rules
                biennial_rule = rule.get("biennial_rule", "none")
                skip_registration = False
                if biennial_rule == "even_year_renewal" and year % 2 != 0:
                    skip_registration = True
                elif biennial_rule == "odd_year_renewal" and year % 2 == 0:
                    skip_registration = True

                if not skip_registration:
                    events.append(
                        ComplianceCalendarEvent(
                            event_id=f"reg-{code}-{year}-{client.client_id}",
                            title=f"[{code}] Pet Food Registration Renewal: {rule['name']}",
                            due_date=due_dt,
                            window_open_date=open_dt,
                            jurisdiction=code,
                            deadline_type="Product Registration & License",
                            fee_usd=breakdown.total_state_fee,
                            portal_url=rule.get("website", ""),
                            statutory_authority=rule.get("stop_sale_authority", ""),
                            description=(
                                f"Annual/Biennial registration renewal for {client.brand_name}.\n"
                                f"Agency: {rule['agency']}\n"
                                f"Statutory Fee: ${breakdown.total_state_fee:,.2f}\n"
                                f"Renewal Window: {open_dt.strftime('%b %d')} to {due_dt.strftime('%b %d, %Y')}\n"
                                f"Statutory Citation: {rule.get('stop_sale_authority')}\n"
                                f"Online Portal: {rule.get('website')}"
                            ),
                            priority="CRITICAL" if breakdown.risk_level == "CRITICAL" else "HIGH"
                        )
                    )

            # 2. Tonnage Reporting Schedule
            cadence = rule.get("tonnage_cadence", "none")
            small_exempt = rule.get("small_pkg_tonnage_exempt", True)
            all_small = all(p.is_small_package for p in client.products) if client.products else True

            if cadence != "none" and not (all_small and small_exempt):
                # Client must report tonnage
                if cadence == "quarterly":
                    quarters = [
                        ("Q1", date(year, 4, 30), date(year, 4, 1)),
                        ("Q2", date(year, 7, 31), date(year, 7, 1)),
                        ("Q3", date(year, 10, 31), date(year, 10, 1)),
                        ("Q4", date(year + 1, 1, 31), date(year + 1, 1, 1)),
                    ]
                    for q_name, q_due, q_open in quarters:
                        events.append(
                            ComplianceCalendarEvent(
                                event_id=f"tonnage-{code}-{q_name}-{year}-{client.client_id}",
                                title=f"[{code}] {q_name} Tonnage Affidavit & Fee: {rule['name']}",
                                due_date=q_due,
                                window_open_date=q_open,
                                jurisdiction=code,
                                deadline_type="Tonnage Filing",
                                fee_usd=rule.get("tonnage_min_fee", 0.0),
                                portal_url=rule.get("website", ""),
                                statutory_authority=rule.get("stop_sale_authority", ""),
                                description=(
                                    f"Quarterly commercial feed tonnage distribution report ({q_name} {year}).\n"
                                    f"Rate: ${rule.get('tonnage_fee_per_ton', 0.0)}/ton (Min: ${rule.get('tonnage_min_fee', 0.0)}).\n"
                                    f"Agency: {rule['agency']}\n"
                                    f"Portal: {rule.get('website')}"
                                ),
                                priority="MEDIUM"
                            )
                        )
                elif cadence == "semiannual":
                    halves = [
                        ("H1 (Jan-Jun)", date(year, 7, 31), date(year, 7, 1)),
                        ("H2 (Jul-Dec)", date(year + 1, 1, 31), date(year + 1, 1, 1)),
                    ]
                    for h_name, h_due, h_open in halves:
                        events.append(
                            ComplianceCalendarEvent(
                                event_id=f"tonnage-{code}-{h_name[:2]}-{year}-{client.client_id}",
                                title=f"[{code}] {h_name} Tonnage Report: {rule['name']}",
                                due_date=h_due,
                                window_open_date=h_open,
                                jurisdiction=code,
                                deadline_type="Tonnage Filing",
                                fee_usd=rule.get("tonnage_min_fee", 0.0),
                                portal_url=rule.get("website", ""),
                                statutory_authority=rule.get("stop_sale_authority", ""),
                                description=(
                                    f"Semiannual commercial feed tonnage distribution report ({h_name}).\n"
                                    f"Agency: {rule['agency']}\n"
                                    f"Portal: {rule.get('website')}"
                                ),
                                priority="MEDIUM"
                            )
                        )
                elif cadence == "annual":
                    ann_due = date(year + 1, 1, 31)
                    ann_open = date(year + 1, 1, 1)
                    events.append(
                        ComplianceCalendarEvent(
                            event_id=f"tonnage-{code}-ANNUAL-{year}-{client.client_id}",
                            title=f"[{code}] Annual Tonnage Summary & Fee: {rule['name']}",
                            due_date=ann_due,
                            window_open_date=ann_open,
                            jurisdiction=code,
                            deadline_type="Tonnage Filing",
                            fee_usd=rule.get("tonnage_min_fee", 0.0),
                            portal_url=rule.get("website", ""),
                            statutory_authority=rule.get("stop_sale_authority", ""),
                            description=(
                                f"Annual commercial feed tonnage distribution report for {year}.\n"
                                f"Agency: {rule['agency']}\n"
                                f"Portal: {rule.get('website')}"
                            ),
                            priority="MEDIUM"
                        )
                    )

        # 3. Mandatory FDA Biennial Food Facility Registration (Oct 1 - Dec 31 Even Years)
        # 21 CFR § 1.230 - 1.235 (Section 415 of FD&C Act)
        if year % 2 == 0:
            fda_open = date(year, 10, 1)
            fda_due = date(year, 12, 31)
            events.append(
                ComplianceCalendarEvent(
                    event_id=f"fda-biennial-{year}-{client.client_id}",
                    title=f"[FEDERAL] FDA Biennial Food Facility Registration Renewal ({year})",
                    due_date=fda_due,
                    window_open_date=fda_open,
                    jurisdiction="US-FDA",
                    deadline_type="FDA Biennial Registration",
                    fee_usd=0.0,  # FDA registration itself has zero statutory fee
                    portal_url="https://www.access.fda.gov/",
                    statutory_authority="Section 415 of FD&C Act [21 U.S.C. § 350d]; 21 CFR Part 1, Subpart H",
                    description=(
                        f"MANDATORY FDA BIENNIAL REGISTRATION RENEWAL ({year}).\n"
                        f"All domestic and foreign animal food/feed manufacturing and processing facilities "
                        f"must renew their registration between October 1 and December 31 of even-numbered years.\n"
                        f"Failure to renew results in immediate cancellation of facility registration and "
                        f"import detention or commercial distribution prohibition under federal law.\n"
                        f"Portal: FDA Industry Systems (FIS) - https://www.access.fda.gov/"
                    ),
                    priority="CRITICAL"
                )
            )

        # Sort chronological by due date
        events.sort(key=lambda x: (x.due_date, x.jurisdiction))
        return events

    def export_ics(self, events: List[ComplianceCalendarEvent], output_path: str, calendar_name: str = "Pet Feed Compliance Deadlines") -> str:
        """Export events to standard RFC 5545 iCalendar (.ics) format."""
        cal = Calendar()
        cal.add("prodid", "-//Pet Feed Reg Compliance Ops Engine//EN")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("x-wr-calname", calendar_name)
        cal.add("x-wr-timezone", "UTC")

        now = datetime.now(timezone.utc)

        for ev in events:
            event = Event()
            event.add("summary", ev.title)
            event.add("uid", f"{ev.event_id}@{uuid.uuid4().hex[:8]}")
            event.add("dtstamp", now)
            event.add("dtstart", ev.due_date)
            # Full day event end date in iCalendar is non-inclusive day after
            event.add("dtend", ev.due_date + timedelta(days=1))
            event.add("description", ev.description)
            event.add("location", ev.portal_url or ev.jurisdiction)
            event.add("status", "CONFIRMED")
            event.add("categories", [ev.deadline_type, "Regulatory Compliance", ev.priority])

            # Alarms: 30 days, 14 days, 1 day prior
            for days_prior in [30, 14, 1]:
                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("description", f"REMINDER: {ev.title} due in {days_prior} days")
                alarm.add("trigger", -timedelta(days=days_prior))
                event.add_component(alarm)

            cal.add_component(event)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(cal.to_ical())

        return output_path

    def export_csv(self, events: List[ComplianceCalendarEvent], output_path: str, client_name: str = "Client") -> str:
        """Export events to structured tabular CSV format."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        headers = [
            "Client Name",
            "Jurisdiction",
            "Deadline Type",
            "Title",
            "Due Date",
            "Window Opens",
            "Statutory Fee USD",
            "Priority",
            "Statutory Authority",
            "Portal URL",
            "Description"
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for ev in events:
                writer.writerow([
                    client_name,
                    ev.jurisdiction,
                    ev.deadline_type,
                    ev.title,
                    ev.due_date.isoformat(),
                    ev.window_open_date.isoformat(),
                    f"{ev.fee_usd:.2f}",
                    ev.priority,
                    ev.statutory_authority,
                    ev.portal_url,
                    ev.description.replace("\n", " | ")
                ])

        return output_path
