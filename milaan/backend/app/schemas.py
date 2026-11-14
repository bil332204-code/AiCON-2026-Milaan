from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Register(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    display_name: str = Field(min_length=1, max_length=100)
    session_mode: Literal["bearer", "cookie"] = "bearer"

class Login(Strict):
    session_mode: Literal["bearer", "cookie"] = "bearer"
    remember_me: bool = False
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

class BatchCreate(Strict):
    name: str = Field(min_length=1, max_length=150)

class OrderInput(Strict):
    order_ref: str = Field(min_length=1, max_length=100)
    customer_name: str = Field(min_length=1, max_length=150)
    amount_due: str = Field(max_length=30)
    account_id: str = Field(min_length=1, max_length=100)
    currency: Literal["PKR"] = "PKR"

class OrderUpdate(OrderInput):
    expected_revision: int = Field(ge=1)

class ExtractionFields(Strict):
    is_payment_receipt: bool = True
    provider_app: str = Field(default="unknown", max_length=100)
    amount_pkr: str | None = Field(default=None, max_length=30)
    datetime_local: str | None = Field(default=None, max_length=50)
    transaction_id: str | None = Field(default=None, max_length=150)
    sender_name: str | None = Field(default=None, max_length=150)
    receiver_hint: str | None = Field(default=None, max_length=150)
    status_text: str | None = Field(default=None, max_length=100)
    unreadable_fields: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("unreadable_fields")
    @classmethod
    def limit_names(cls, v):
        if any(len(x) > 100 for x in v): raise ValueError("Field name is too long")
        return v

class ClaimUpdate(Strict):
    expected_version: int = Field(ge=1)
    fields: ExtractionFields
    confirmed: bool = False

class Decision(Strict):
    expected_version: int = Field(ge=1)
    decision: Literal["ship", "hold", "review"]
    statement_line_id: str | None = None
    reason: str = Field(min_length=5, max_length=1000)

class Reset(Strict):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=500)

class ExtractionRequest(Strict):
    consent_to_cloud: bool = False

class RetryExtraction(Strict):
    expected_version: int = Field(ge=1)

class ContentWrite(Strict):
    expected_version: int = Field(ge=0)
    value: dict

class VerifyEmail(Strict):
    session_mode: Literal["bearer", "cookie"] = "bearer"
    challenge_id: str = Field(min_length=32, max_length=64)
    code: str = Field(pattern=r"^[0-9]{6}$")

class ResendEmail(Strict):
    challenge_id: str = Field(min_length=32, max_length=64)

class ImportProvenance(Strict):
    """Client-declared source identity, not a proof of authenticity."""
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mapping: dict[str, str] = Field(max_length=7)
    timezone: Literal["+05:00", "Z"] = "+05:00"

    @field_validator("mapping")
    @classmethod
    def safe_mapping(cls, value):
        allowed = {"order_ref", "customer_name", "amount_due", "account_id", "currency",
                   "posted_at", "direction", "amount", "counterparty", "transaction_id"}
        if any(k not in allowed or len(v) > 200 for k, v in value.items()):
            raise ValueError("Unsupported import mapping")
        return value


class AllocationPart(Strict):
    statement_line_id: str = Field(min_length=1, max_length=36)
    claim_id: str = Field(min_length=1, max_length=36)
    amount_pkr: str = Field(min_length=1, max_length=30)

class AllocationOrder(Strict):
    match_id: str = Field(min_length=1, max_length=36)
    expected_version: int = Field(ge=1)
    parts: list[AllocationPart] = Field(max_length=20)

class AllocationPlan(Strict):
    expected_revision: int = Field(ge=1)
    orders: list[AllocationOrder] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=5, max_length=1000)
    confirmed_relationships: bool = False


class ResetRequest(Strict):
    email: EmailStr

class ResetPassword(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    token: str = Field(min_length=40, max_length=128)
    password: str = Field(min_length=10, max_length=256)


class DeleteAccount(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    password: str = Field(min_length=1, max_length=256)
    confirm: Literal["DELETE"]


class TotpCode(Strict):
    code: str = Field(pattern=r"^[0-9]{6}$")


class TotpLogin(Strict):
    challenge_id: str = Field(min_length=32, max_length=96)
    code: str = Field(pattern=r"^[0-9]{6}$")
