"""
Data models for the 50-State Pet Feed Regulatory Compliance Rules Engine.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ProductSpec(BaseModel):
    """Specification of a commercial pet food, treat, or specialty pet product."""
    sku: str = Field(..., description="Unique Stock Keeping Unit or item ID")
    name: str = Field(..., description="Full descriptive name of the product")
    brand: str = Field(..., description="Brand name as it appears on label")
    species: str = Field(default="dog", description="Target species: dog, cat, or specialty_pet")
    package_weight_lbs: float = Field(..., description="Net weight in decimal pounds")
    package_type: str = Field(default="pouch", description="Packaging type: pouch, bag, can, tub, box")
    is_specialty_pet: bool = Field(default=False, description="Whether product is for specialty pets (birds, reptiles, rodents)")
    annual_projected_tons: float = Field(default=0.25, description="Projected annual distributed tonnage in target jurisdiction")
    is_canned: bool = Field(default=False, description="Whether product is canned (triggers special rules in NC)")

    @property
    def is_small_package(self) -> bool:
        """Standard AAFCO small package rule threshold is 10 lbs or less."""
        return self.package_weight_lbs <= 10.0

    @property
    def is_under_5_lbs(self) -> bool:
        """Strict small package threshold used in TX, NC, MI (5 lbs or less)."""
        return self.package_weight_lbs <= 5.0


class FacilitySpec(BaseModel):
    """Physical manufacturing, blending, or commercial distribution facility."""
    facility_id: str = Field(..., description="Unique facility identifier")
    facility_name: str = Field(..., description="Company or facility legal name")
    state: str = Field(..., description="Two-letter US state code where facility is situated")
    address: str = Field(default="", description="Physical street address")
    is_manufacturing: bool = Field(default=True, description="Whether facility processes or manufactures feed")
    is_distribution: bool = Field(default=True, description="Whether facility distributes feed into commerce")


class ClientProfile(BaseModel):
    """Client profile containing brand footprint, products, facilities, and active state registrations."""
    client_id: str = Field(..., description="Unique client identifier")
    company_name: str = Field(..., description="Legal company name")
    brand_name: str = Field(..., description="Customer-facing commercial brand name")
    contact_name: str = Field(..., description="Primary founder, CEO, or regulatory lead")
    contact_email: str = Field(..., description="Verified corporate email address")
    phone: str = Field(default="", description="Contact phone number if listed")
    website: str = Field(default="", description="Corporate D2C website")
    products: List[ProductSpec] = Field(default_factory=list, description="Portfolio of registered/unregistered products")
    facilities: List[FacilitySpec] = Field(default_factory=list, description="List of physical operating facilities")
    target_states: List[str] = Field(default_factory=list, description="List of 2-letter states where products are sold or shipped")
    currently_registered_states: List[str] = Field(default_factory=list, description="List of states with currently active registrations")


class StateFeeBreakdown(BaseModel):
    """Detailed fee breakdown and regulatory requirements for a single state."""
    state_code: str
    state_name: str
    requires_registration: bool
    registration_type: str
    cycle: str
    renewal_date: str
    renewal_month: Optional[int]
    renewal_day: Optional[int]
    facility_fee: float = 0.0
    product_registration_fee: float = 0.0
    tonnage_inspection_fee: float = 0.0
    total_state_fee: float = 0.0
    tonnage_cadence: str
    small_pkg_tonnage_exempt: bool
    stop_sale_authority: str
    compliance_notes: str
    is_registered: bool = False
    is_gap: bool = False
    risk_level: str = "LOW"  # LOW, MEDIUM, CRITICAL


class PortfolioAuditQuote(BaseModel):
    """Comprehensive commercial and regulatory compliance quote across target jurisdictions."""
    client_name: str
    year: int
    target_state_count: int
    total_products: int
    state_breakdowns: Dict[str, StateFeeBreakdown]
    total_statutory_state_fees: float
    incumbent_benchmark_usd: float  # Benchmarked against PetFoodCompliance.com $175/state
    ops_engine_prep_fee_usd: float  # Discounted / value-anchored execution fee
    client_savings_usd: float
    unregistered_target_states: List[str]
    critical_stop_sale_states: List[str]
