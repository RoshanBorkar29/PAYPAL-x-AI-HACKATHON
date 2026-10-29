"""Pydantic schemas and data models for Agent Wallet."""

from typing import Optional, Literal, Union
from datetime import datetime
from pydantic import BaseModel, Field


class Payment(BaseModel):
    """Payment request submitted by an AI agent."""
    agent_id: Union[str, int] = Field(
        ...,
        description="Unique identifier for the calling agent (e.g. 'agent-researcher-01' or 101)"
    )
    vendor: str = Field(
        ...,
        min_length=1,
        description="Name of the vendor/recipient to be paid (e.g. 'Tavily Search API')"
    )
    amount: float = Field(
        ...,
        gt=0,
        description="Amount to be paid (must be greater than 0)"
    )
    currency: str = Field(
        default="USD",
        description="Currency code (e.g. 'USD', 'EUR', 'GBP')"
    )
    recipient_email: Optional[str] = Field(
        default=None,
        description="Recipient's PayPal email address for Payouts"
    )
    reason: str = Field(
        ...,
        min_length=3,
        description="Business rationale and justification for the expense"
    )
    vendor_description: Optional[str] = Field(
        default=None,
        description="Optional context or description of the vendor and service"
    )


# Alias so both Payment and PaymentRequest can be used interchangeably
PaymentRequest = Payment


class Decision(BaseModel):
    """Gateway policy decision returned to agent, supervisor, or API client."""
    status: Literal["approve", "deny", "escalate"] = Field(
        ...,
        description="Outcome of the policy evaluation ('approve', 'deny', or 'escalate')"
    )
    reason: str = Field(
        ...,
        description="Explanation or justification for the policy decision"
    )
    risk_score: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Assessed risk score from 0.0 (safest) to 1.0 (highest risk)"
    )
    payout_id: Optional[str] = Field(
        default=None,
        description="PayPal Sandbox payout batch ID if approved and disbursed"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Tracked database ID for this payment request"
    )
    evaluated_by: Optional[str] = Field(
        default="policy_engine",
        description="Component that finalized the decision ('hard_limits', 'groq_policy_judge', 'supervisor')"
    )


class RequestRecord(BaseModel):
    """Database record for an audited payment request."""
    id: str
    agent_id: str
    vendor: str
    amount: float
    currency: str
    recipient_email: Optional[str] = None
    reason: str
    vendor_description: Optional[str] = None
    status: str
    decision_reason: Optional[str] = None
    risk_score: float = 0.0
    evaluated_by: Optional[str] = None
    paypal_payout_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SupervisorAction(BaseModel):
    """Action payload for human supervisors reviewing escalated requests."""
    action: Literal["approve", "deny"] = Field(
        ...,
        description="Supervisor decision: 'approve' to disburse, 'deny' to cancel"
    )
    note: Optional[str] = Field(
        default=None,
        description="Optional human supervisor note or rationale"
    )


class SettingItem(BaseModel):
    """Configurable system spending cap or policy rule."""
    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[str] = None


class SettingUpdate(BaseModel):
    """Payload to update a gateway setting."""
    value: str = Field(..., description="New value for the configuration key")


class VendorRecord(BaseModel):
    """Registered vendor with trust rating and whitelisting status."""
    id: str
    name: str
    category: Optional[str] = None
    trust_score: float = 1.0
    status: Literal["allowed", "blocked", "flagged"] = "allowed"
    created_at: Optional[str] = None


class DashboardStats(BaseModel):
    """High-level metrics for the gateway dashboard."""
    total_processed_usd: float = 0.0
    total_requests: int = 0
    approved_count: int = 0
    denied_count: int = 0
    escalated_count: int = 0
    auto_payout_enabled: bool = False


class HealthResponse(BaseModel):
    """Gateway service health check."""
    status: str = "ok"
    database: str = "connected"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
