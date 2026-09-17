"""Pydantic schemas that every JSON-producing AI call is validated against."""

from pydantic import BaseModel, Field


class InquiryLineItem(BaseModel):
    part_no: str | None = None
    description: str = ""
    qty: int = 1
    vehicle: str | None = None


class ParsedInquiry(BaseModel):
    customer: str | None = None
    lines: list[InquiryLineItem] = Field(default_factory=list)


class ImageIdentification(BaseModel):
    part_type: str = ""
    part_type_cn: str = ""
    visible_numbers: list[str] = Field(default_factory=list)
    brand: str | None = None
    features: list[str] = Field(default_factory=list)
    description: str = ""


class ColumnMapping(BaseModel):
    mapping: dict[str, str | None] = Field(default_factory=dict)


class ExtractedRow(BaseModel):
    supplier_part_no: str | None = None
    name: str | None = None
    category: str | None = None
    oe_numbers: list[str] = Field(default_factory=list)
    cross_numbers: list[str] = Field(default_factory=list)
    brand: str | None = None
    vehicle: str | None = None
    specs: dict[str, str | float | int] = Field(default_factory=dict)
    cost_price: float | None = None
    currency: str | None = None
    moq: int | None = None
    lead_time_days: int | None = None
    packaging: str | None = None
    weight_kg: float | None = None


class ExtractedRows(BaseModel):
    rows: list[ExtractedRow] = Field(default_factory=list)


class FaqItem(BaseModel):
    q: str
    a: str


class ListingDraft(BaseModel):
    title: str
    keywords: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    description: str = ""
    faq: list[FaqItem] = Field(default_factory=list)


class FieldSuggestion(BaseModel):
    value: str | dict
    reason: str = ""


class FillMissing(BaseModel):
    suggestions: dict[str, FieldSuggestion] = Field(default_factory=dict)
