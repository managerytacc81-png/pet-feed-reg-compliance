"""
AAFCO & State-Mandated Commercial Pet Food & Treat Label Compliance Checker.
Evaluates label text against AAFCO Model Pet Food Regulations (PF1 - PF10)
and FDA Title 21 CFR Part 501 food labeling mandates.
"""

import re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class LabelViolation(BaseModel):
    """Specific label compliance deficiency or regulatory infraction."""
    severity: str = Field(..., description="Severity level: CRITICAL, MAJOR, MINOR")
    element: str = Field(..., description="Mandatory label element name")
    citation: str = Field(..., description="AAFCO Model Regulation or 21 CFR section")
    issue: str = Field(..., description="Description of non-compliance identified")
    recommended_fix: str = Field(..., description="Exact textual or formatting remediation")


class LabelAuditResult(BaseModel):
    """Comprehensive compliance evaluation result for a product label."""
    product_name: str
    product_type: str  # treat, complete_food, supplement, specialty_pet
    is_compliant: bool
    score: int = Field(..., ge=0, le=100, description="Compliance score (0 to 100)")
    passed_checks: List[str] = Field(default_factory=list)
    violations: List[LabelViolation] = Field(default_factory=list)
    extracted_elements: Dict[str, Any] = Field(default_factory=dict)
    summary: str


class LabelComplianceChecker:
    """Automated regulatory auditor for pet food and pet treat product labels."""

    # Regex patterns for Guaranteed Analysis
    PROTEIN_REGEX = re.compile(
        r'crude\s+protein\s*(\(min\)|min\.?|minimum)?\s*[:\s-]*\s*(\d+(?:\.\d+)?)\s*%',
        re.IGNORECASE
    )
    FAT_REGEX = re.compile(
        r'crude\s+fat\s*(\(min\)|min\.?|minimum)?\s*[:\s-]*\s*(\d+(?:\.\d+)?)\s*%',
        re.IGNORECASE
    )
    FIBER_REGEX = re.compile(
        r'crude\s+fiber\s*(\(max\)|max\.?|maximum)?\s*[:\s-]*\s*(\d+(?:\.\d+)?)\s*%',
        re.IGNORECASE
    )
    MOISTURE_REGEX = re.compile(
        r'moisture\s*(\(max\)|max\.?|maximum)?\s*[:\s-]*\s*(\d+(?:\.\d+)?)\s*%',
        re.IGNORECASE
    )

    # Net quantity regex (dual declaration check)
    NET_WT_US_REGEX = re.compile(
        r'(?:net\s+(?:wt|weight|contents)?\.?\s*:?\s*)?(\d+(?:\.\d+)?)\s*(?:oz|ounce|ounces|lb|lbs|pound|pounds)',
        re.IGNORECASE
    )
    NET_WT_METRIC_REGEX = re.compile(
        r'(\d+(?:\.\d+)?)\s*(?:g|gram|grams|kg|kilogram|kilograms)',
        re.IGNORECASE
    )

    # Target species regex
    SPECIES_REGEX = re.compile(
        r'\b(dog|dogs|canine|puppy|puppies|cat|cats|feline|kitten|kittens|ferret|rabbit|bird|parrot)\b',
        re.IGNORECASE
    )

    # Treat vs complete food statement
    TREAT_PURPOSE_REGEX = re.compile(
        r'\b(treat|treats|biscuit|biscuits|chew|chews|snack|snacks|supplement|topper)\b',
        re.IGNORECASE
    )
    COMPLETE_FOOD_REGEX = re.compile(
        r'\b(complete\s+(?:and|&)\s+balanced|adult\s+maintenance|all\s+life\s+stages|daily\s+food|kibble|canned\s+food)\b',
        re.IGNORECASE
    )

    # AAFCO Nutritional adequacy regex
    AAFCO_FORMULATION_REGEX = re.compile(
        r'formulated\s+to\s+meet\s+the\s+nutritional\s+levels\s+established\s+by\s+(?:the\s+)?aafco',
        re.IGNORECASE
    )
    AAFCO_FEEDING_TRIAL_REGEX = re.compile(
        r'animal\s+feeding\s+tests\s+using\s+aafco\s+procedures',
        re.IGNORECASE
    )
    AAFCO_INTERMITTENT_REGEX = re.compile(
        r'intended\s+for\s+intermittent\s+or\s+supplemental\s+feeding\s+only',
        re.IGNORECASE
    )

    # Manufacturer / distributor regex
    MFR_DIST_REGEX = re.compile(
        r'(?:manufactured\s+by|manufactured\s+for|distributed\s+by|packed\s+for|distributed\s+exclusively\s+by)',
        re.IGNORECASE
    )
    CITY_STATE_ZIP_REGEX = re.compile(
        r'[A-Za-z\s\.\-]+,\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)'
    )

    def check_label(
        self,
        label_text: str,
        product_name: str = "Unknown Product",
        expected_type: str = "treat"
    ) -> LabelAuditResult:
        """
        Execute comprehensive 8-point AAFCO/FDA regulatory audit on product label text.
        """
        violations: List[LabelViolation] = []
        passed_checks: List[str] = []
        extracted: Dict[str, Any] = {}
        score = 100

        text = label_text.strip()
        if not text:
            return LabelAuditResult(
                product_name=product_name,
                product_type=expected_type,
                is_compliant=False,
                score=0,
                passed_checks=[],
                violations=[
                    LabelViolation(
                        severity="CRITICAL",
                        element="Full Label",
                        citation="AAFCO Model Pet Food Regulations",
                        issue="Empty label text provided for analysis.",
                        recommended_fix="Provide valid OCR or extracted text from packaging artwork."
                    )
                ],
                summary="Audit failed: No label text provided."
            )

        # -------------------------------------------------------------
        # 1. Product Name & Brand Name (PF2)
        # -------------------------------------------------------------
        has_prod_name = False
        if product_name and product_name.lower() in text.lower():
            has_prod_name = True
            extracted["product_name"] = product_name
        elif len(text.splitlines()) > 0 and len(text.splitlines()[0].strip()) > 3:
            has_prod_name = True
            extracted["product_name"] = text.splitlines()[0].strip()

        if has_prod_name:
            passed_checks.append("Brand and Product Name identified")
        else:
            score -= 10
            violations.append(
                LabelViolation(
                    severity="MAJOR",
                    element="Product Name",
                    citation="AAFCO Model Regulation PF2",
                    issue="Product name or brand name cannot be clearly verified on the principal display panel.",
                    recommended_fix=f"Clearly state the brand and product title (e.g. '{product_name}') at top of Principal Display Panel."
                )
            )

        # -------------------------------------------------------------
        # 2. Species & Purpose Identification (PF2, PF3)
        # -------------------------------------------------------------
        species_match = self.SPECIES_REGEX.search(text)
        is_treat = bool(self.TREAT_PURPOSE_REGEX.search(text)) or expected_type == "treat"
        is_complete = bool(self.COMPLETE_FOOD_REGEX.search(text)) or expected_type == "complete_food"

        if species_match:
            species_found = species_match.group(1).lower()
            extracted["target_species"] = "dog" if "dog" in species_found or "puppy" in species_found or "canine" in species_found else "cat"
            passed_checks.append(f"Target Species clearly declared: '{species_found}'")
        else:
            score -= 20
            violations.append(
                LabelViolation(
                    severity="CRITICAL",
                    element="Species Statement",
                    citation="AAFCO Model Regulation PF2(a)",
                    issue="Product fails to explicitly identify the target animal species (e.g. 'for dogs' or 'for cats') on the front panel.",
                    recommended_fix="Add explicit statement: 'Dog Treats', 'All-Natural Treats for Dogs', or 'Complete Food for Adult Cats'."
                )
            )

        # -------------------------------------------------------------
        # 3. Net Quantity Statement (PF3, 21 CFR § 501.105, FPLA)
        # -------------------------------------------------------------
        us_wt_match = self.NET_WT_US_REGEX.search(text)
        metric_wt_match = self.NET_WT_METRIC_REGEX.search(text)

        if us_wt_match and metric_wt_match:
            extracted["net_quantity_us"] = us_wt_match.group(0).strip()
            extracted["net_quantity_metric"] = metric_wt_match.group(0).strip()
            passed_checks.append("Dual Net Quantity Statement verified (US Customary and Metric)")
        elif us_wt_match and not metric_wt_match:
            score -= 15
            extracted["net_quantity_us"] = us_wt_match.group(0).strip()
            violations.append(
                LabelViolation(
                    severity="MAJOR",
                    element="Net Quantity (Dual Declaration)",
                    citation="21 CFR § 501.105 & Fair Packaging and Labeling Act (FPLA)",
                    issue=f"Net weight includes US Customary units ({us_wt_match.group(0).strip()}) but is missing mandatory metric equivalent (grams/kilograms).",
                    recommended_fix="Update Net Weight statement to dual format: e.g. 'NET WT 6 OZ (170 g)' or 'NET WT 16 OZ (454 g)'."
                )
            )
        elif metric_wt_match and not us_wt_match:
            score -= 15
            violations.append(
                LabelViolation(
                    severity="MAJOR",
                    element="Net Quantity (Dual Declaration)",
                    citation="21 CFR § 501.105 & FPLA",
                    issue="Net weight includes Metric units but is missing US Customary units (oz/lbs).",
                    recommended_fix="Update Net Weight to include US ounces/pounds alongside metric units."
                )
            )
        else:
            score -= 25
            violations.append(
                LabelViolation(
                    severity="CRITICAL",
                    element="Net Quantity Statement",
                    citation="AAFCO Model Regulation PF3 & 21 CFR § 501.105",
                    issue="No net quantity statement found on the product label.",
                    recommended_fix="Add prominent net weight statement on lower 30% of Principal Display Panel (e.g. 'NET WT 8 OZ (227 g)')."
                )
            )

        # -------------------------------------------------------------
        # 4. Guaranteed Analysis (PF4)
        # -------------------------------------------------------------
        prot_match = self.PROTEIN_REGEX.search(text)
        fat_match = self.FAT_REGEX.search(text)
        fiber_match = self.FIBER_REGEX.search(text)
        moist_match = self.MOISTURE_REGEX.search(text)

        ga_elements = {}
        if prot_match:
            ga_elements["crude_protein_min"] = float(prot_match.group(2))
        if fat_match:
            ga_elements["crude_fat_min"] = float(fat_match.group(2))
        if fiber_match:
            ga_elements["crude_fiber_max"] = float(fiber_match.group(2))
        if moist_match:
            ga_elements["moisture_max"] = float(moist_match.group(2))

        extracted["guaranteed_analysis"] = ga_elements

        missing_ga = []
        if not prot_match:
            missing_ga.append("Crude Protein (min)")
        if not fat_match:
            missing_ga.append("Crude Fat (min)")
        if not fiber_match:
            missing_ga.append("Crude Fiber (max)")
        if not moist_match:
            missing_ga.append("Moisture (max)")

        if not missing_ga:
            # Check order of appearance
            p_pos = prot_match.start()
            f_pos = fat_match.start()
            fib_pos = fiber_match.start()
            m_pos = moist_match.start()

            if p_pos < f_pos < fib_pos < m_pos:
                passed_checks.append("Guaranteed Analysis complete with correct mandatory AAFCO sequence")
            else:
                score -= 10
                violations.append(
                    LabelViolation(
                        severity="MAJOR",
                        element="Guaranteed Analysis Sequence",
                        citation="AAFCO Model Regulation PF4(a)",
                        issue="Guaranteed analysis nutrients are out of statutory order. AAFCO mandates Protein, Fat, Fiber, Moisture sequence.",
                        recommended_fix="Re-order Guaranteed Analysis strictly: 1. Crude Protein (min), 2. Crude Fat (min), 3. Crude Fiber (max), 4. Moisture (max)."
                    )
                )
        else:
            score -= min(40, len(missing_ga) * 10)
            violations.append(
                LabelViolation(
                    severity="CRITICAL",
                    element="Guaranteed Analysis",
                    citation="AAFCO Model Regulation PF4",
                    issue=f"Guaranteed Analysis is incomplete. Missing mandatory guarantees: {', '.join(missing_ga)}.",
                    recommended_fix="Include full 4-point Guaranteed Analysis box with exact percentage values for Crude Protein (min), Crude Fat (min), Crude Fiber (max), Moisture (max)."
                )
            )

        # -------------------------------------------------------------
        # 5. Descending Ingredient List (PF5, 21 CFR § 501.4)
        # -------------------------------------------------------------
        ing_header = re.search(r'(?:ingredients|ingredients\s*:)', text, re.IGNORECASE)
        if ing_header:
            passed_checks.append("Ingredient List heading identified")
            # Extract ingredient snippet
            snippet = text[ing_header.end(): ing_header.end() + 250].strip()
            extracted["ingredients_snippet"] = snippet.split("\n")[0]
            # Check if comma-separated
            if "," in snippet or len(snippet.split()) > 1:
                passed_checks.append("Ingredient listing formatted as descending list")
            else:
                score -= 10
                violations.append(
                    LabelViolation(
                        severity="MAJOR",
                        element="Ingredient List Format",
                        citation="AAFCO Model Regulation PF5 & 21 CFR § 501.4",
                        issue="Ingredient statement appears truncated or lacks standard comma-separated descending composition.",
                        recommended_fix="List all ingredients in descending order of predominance by weight separated by commas."
                    )
                )
        else:
            score -= 30
            violations.append(
                LabelViolation(
                    severity="CRITICAL",
                    element="Ingredient List",
                    citation="AAFCO Model Regulation PF5 & 21 CFR § 501.4",
                    issue="No 'Ingredients:' declaration found on the label text.",
                    recommended_fix="Add an explicit 'Ingredients:' section listing all single or compound ingredients in descending order of predominance."
                )
            )

        # -------------------------------------------------------------
        # 6. Manufacturer / Distributor Name and Address (PF6, 21 CFR § 501.5)
        # -------------------------------------------------------------
        mfr_relation = self.MFR_DIST_REGEX.search(text)
        city_state_zip = self.CITY_STATE_ZIP_REGEX.search(text)

        if mfr_relation and city_state_zip:
            extracted["manufacturer_relation"] = mfr_relation.group(0).strip()
            extracted["city_state_zip"] = city_state_zip.group(0).strip()
            passed_checks.append("Manufacturer/Distributor identity and geographic location verified")
        elif city_state_zip:
            extracted["city_state_zip"] = city_state_zip.group(0).strip()
            score -= 5
            violations.append(
                LabelViolation(
                    severity="MINOR",
                    element="Manufacturer Responsibility Statement",
                    citation="AAFCO Model Regulation PF6 & 21 CFR § 501.5",
                    issue="City, State, and Zip code found, but lacks clear 'Manufactured for' or 'Distributed by' qualification.",
                    recommended_fix="Precede company name and address with 'Manufactured for [Brand Name]' or 'Distributed by [Brand Name]'."
                )
            )
        else:
            score -= 15
            violations.append(
                LabelViolation(
                    severity="MAJOR",
                    element="Manufacturer / Distributor Name & Address",
                    citation="AAFCO Model Regulation PF6 & 21 CFR § 501.5",
                    issue="Missing complete manufacturer or distributor identity with City, State, and ZIP code.",
                    recommended_fix="Add guarantor block: 'Manufactured for: [Company Name], [City, ST ZIP]'."
                )
            )

        # -------------------------------------------------------------
        # 7. Directions for Use & Feeding Guidelines (PF7)
        # -------------------------------------------------------------
        feeding_directions = re.search(
            r'(?:feeding\s+(?:directions|guidelines|instructions)|daily\s+feeding\s+guide|feed\s+as\s+a\s+treat)',
            text,
            re.IGNORECASE
        )

        if feeding_directions:
            passed_checks.append("Directions for Use / Feeding Instructions present")
        else:
            if is_treat:
                score -= 10
                violations.append(
                    LabelViolation(
                        severity="MAJOR",
                        element="Treat Feeding Directions",
                        citation="AAFCO Model Regulation PF7(b)",
                        issue="Treat label missing explicit feeding directions or treat caloric limitation statement.",
                        recommended_fix="Add statement: 'Feeding Guidelines: Feed as a treat or reward. Treats should not exceed 10% of daily caloric intake. Always provide fresh water.'"
                    )
                )
            else:
                score -= 20
                violations.append(
                    LabelViolation(
                        severity="CRITICAL",
                        element="Feeding Instructions (Complete Food)",
                        citation="AAFCO Model Regulation PF7(a)",
                        issue="Complete pet food lacks mandatory daily feeding guide table based on animal weight.",
                        recommended_fix="Add structured daily feeding table detailing portion cups/grams per dog body weight range."
                    )
                )

        # -------------------------------------------------------------
        # 8. Nutritional Adequacy / AAFCO Statement (PF8)
        # -------------------------------------------------------------
        has_formulation = bool(self.AAFCO_FORMULATION_REGEX.search(text))
        has_feeding_trial = bool(self.AAFCO_FEEDING_TRIAL_REGEX.search(text))
        has_intermittent = bool(self.AAFCO_INTERMITTENT_REGEX.search(text))

        if is_treat:
            if has_intermittent or "intermittent or supplemental" in text.lower():
                passed_checks.append("AAFCO Intermittent or Supplemental Feeding Disclaimer verified")
            elif has_formulation or has_feeding_trial:
                passed_checks.append("Complete & Balanced Nutritional Adequacy Statement present")
            else:
                score -= 15
                violations.append(
                    LabelViolation(
                        severity="MAJOR",
                        element="Nutritional Adequacy Statement",
                        citation="AAFCO Model Regulation PF8(a)",
                        issue="Treat product lacks mandatory AAFCO nutritional adequacy disclaimer.",
                        recommended_fix="Add statement: 'This product is intended for intermittent or supplemental feeding only.'"
                    )
                )
        else:
            if has_formulation or has_feeding_trial:
                passed_checks.append("Complete & Balanced AAFCO Nutritional Adequacy Statement present")
            elif has_intermittent:
                score -= 15
                violations.append(
                    LabelViolation(
                        severity="MAJOR",
                        element="Nutritional Adequacy Mismatch",
                        citation="AAFCO Model Regulation PF8",
                        issue="Complete food labeled as 'intermittent or supplemental feeding only'.",
                        recommended_fix="Provide standard AAFCO formulation or feeding trial claim substantiating Life Stage."
                    )
                )
            else:
                score -= 25
                violations.append(
                    LabelViolation(
                        severity="CRITICAL",
                        element="AAFCO Statement",
                        citation="AAFCO Model Regulation PF8",
                        issue="Complete food missing statutory AAFCO Nutritional Adequacy Statement.",
                        recommended_fix="Add statement: '[Product Name] is formulated to meet the nutritional levels established by the AAFCO Dog Food Nutrient Profiles for All Life Stages.'"
                    )
                )

        # Final Score & Status Compilation
        score = max(0, min(100, score))
        critical_violations = [v for v in violations if v.severity == "CRITICAL"]
        major_violations = [v for v in violations if v.severity == "MAJOR"]
        is_compliant = len(critical_violations) == 0 and len(major_violations) == 0 and score >= 85

        if is_compliant:
            summary = f"PASSED: Label meets AAFCO and FDA compliance standards (Score: {score}/100)."
        else:
            summary = f"FLAGGED: {len(critical_violations)} Critical and {len(major_violations)} Major compliance issues identified (Score: {score}/100)."

        return LabelAuditResult(
            product_name=product_name,
            product_type="treat" if is_treat else "complete_food",
            is_compliant=is_compliant,
            score=score,
            passed_checks=passed_checks,
            violations=violations,
            extracted_elements=extracted,
            summary=summary
        )
