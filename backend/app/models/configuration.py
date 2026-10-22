"""Configuration: form/field definitions, validation rules, application settings."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from ._common import updated_at_col


class FormDefinition(Base):
    __tablename__ = "form_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(255), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = updated_at_col()

    fields: Mapped[list["FieldDefinition"]] = relationship(
        back_populates="form", cascade="all, delete-orphan", order_by="FieldDefinition.display_order", lazy="selectin"
    )


class FieldDefinition(Base):
    __tablename__ = "field_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form_definitions.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(120))
    field_type: Mapped[str] = mapped_column(String(20))  # text | textarea | email | phone | select | date | number
    section: Mapped[str] = mapped_column(String(60), default="Details")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    required_when: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    visible_when: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pattern: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pattern_message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    help_text: Mapped[str] = mapped_column(Text, default="")
    sensitivity: Mapped[str] = mapped_column(String(20), default="NONE")  # NONE | FINANCIAL
    is_identifier: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    form: Mapped[FormDefinition] = relationship(back_populates="fields")


class ValidationRule(Base):
    __tablename__ = "validation_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(20), index=True)
    rule_key: Mapped[str] = mapped_column(String(60), unique=True)
    rule_type: Mapped[str] = mapped_column(String(30))  # REQUIRED_ATTACHMENT | FUTURE_DATE
    field_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    condition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachment_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApplicationSetting(Base):
    __tablename__ = "application_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | float | int | str | bool] = mapped_column(JSON)
    description: Mapped[str] = mapped_column(Text, default="")
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = updated_at_col()
