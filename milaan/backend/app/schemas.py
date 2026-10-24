from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Register(Strict):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    display_name: str = Field(min_length=1, max_length=100)

class Login(Strict):
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
    challenge_id: str = Field(min_length=32, max_length=64)
    code: str = Field(pattern=r"^[0-9]{6}$")

class ResendEmail(Strict):
    challenge_id: str = Field(min_length=32, max_length=64)

class ProductCreate(Strict):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    sku: str = Field(min_length=1, max_length=100)
    category: str = Field(default="General", min_length=1, max_length=100)
    purchase_price: str = Field(max_length=30)
    selling_price: str = Field(max_length=30)
    stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    is_active: bool = True
    image_url: str | None = Field(default=None, max_length=500)

class ProductUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    purchase_price: str | None = Field(default=None, max_length=30)
    selling_price: str | None = Field(default=None, max_length=30)
    stock_quantity: int | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    image_url: str | None = Field(default=None, max_length=500)

class StockUpdate(Strict):
    stock_quantity: int = Field(ge=0)

class CartItemAdd(Strict):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(default=1, ge=1)

class CartItemUpdate(Strict):
    quantity: int = Field(ge=1)

class CheckoutRequest(Strict):
    customer_name: str = Field(min_length=1, max_length=150)
    customer_email: EmailStr
    customer_phone: str | None = Field(default=None, max_length=30)
    shipping_address: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=500)

class OrderStatusUpdate(Strict):
    status: Literal["Pending", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"]



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
