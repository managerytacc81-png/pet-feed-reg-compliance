"""
Pet Feed Law Compliance Ops Engine.
50-State pet food & treat registration rules, label compliance checker, and renewal calendar generator.
"""

__version__ = "1.0.0"
__author__ = "Antigravity Autonomous Revenue Agent (Gemini)"

from pet_feed_reg_compliance.rules_engine.engine import PetFeedRulesEngine
from pet_feed_reg_compliance.label_checker.checker import LabelComplianceChecker
from pet_feed_reg_compliance.calendar_generator.calendar_gen import RenewalCalendarGenerator

__all__ = [
    "PetFeedRulesEngine",
    "LabelComplianceChecker",
    "RenewalCalendarGenerator"
]
