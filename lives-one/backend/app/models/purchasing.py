"""Customer purchasing data. Deliberately separate from MDM setup requests."""
from datetime import date, datetime

from sqlalchemy import JSON, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._common import created_at_col

# Customer purchasing event types (never MDM setup requests — those live in mdm_requests).
EVENT_TYPES = ("ENQUIRY", "PURCHASE_REQUEST", "PURCHASE_ORDER")


class Customer(Base):
    """A source-system customer record, as keyed by one business entity. May be an alias."""
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    source_entity: Mapped[str] = mapped_column(ForeignKey("business_entities.code"))
    name: Mapped[str] = mapped_column(String(200))
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    segment: Mapped[str] = mapped_column(String(30))  # HOSPITAL | LABORATORY | CLINIC | RESEARCH
    account_owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    family: Mapped[str] = mapped_column(String(1), index=True)  # A | B | C
    category: Mapped[str] = mapped_column(String(40))
    purchase_pattern: Mapped[str] = mapped_column(String(20))  # RECURRING | PERIODIC
    unit: Mapped[str] = mapped_column(String(20))
    registered_countries: Mapped[list] = mapped_column(JSON, default=list)


class PurchasingEvent(Base):
    """Raw purchasing signal as ingested (one row per line). Never mutated by analytics."""
    __tablename__ = "purchasing_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_txn_id: Mapped[str] = mapped_column(String(40), index=True)
    line_no: Mapped[int] = mapped_column(Integer, default=1)
    event_type: Mapped[str] = mapped_column(String(20), index=True)
    # PURCHASE_ORDER: CONFIRMED | FULFILLED | CANCELLED | RETURNED | INCOMPLETE
    # PURCHASE_REQUEST: OPEN | CONVERTED | LAPSED | PENDING_MDM_SETUP;  ENQUIRY: OPEN | CLOSED
    status: Mapped[str] = mapped_column(String(20))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    raw_customer_name: Mapped[str] = mapped_column(String(200))
    product_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    raw_country: Mapped[str] = mapped_column(String(40))
    entity_code: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    linked_mdm_request_id: Mapped[int | None] = mapped_column(ForeignKey("mdm_requests.id"), nullable=True)
    ingested_at: Mapped[datetime] = created_at_col()

    customer: Mapped[Customer | None] = relationship(lazy="joined")
