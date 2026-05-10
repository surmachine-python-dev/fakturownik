from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


Money = Numeric(12, 2)
WeightValue = Numeric(12, 3)
DEFAULT_SETTLEMENT_TYPE = "inne"
DEFAULT_SETTLEMENT_TYPE_COLORS = {
    "mix": "#FFF4CC",
    "faktura zbiorcza": "#DDEBFF",
    "inne": "#ECECEC",
}


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("nip", name="uq_clients_nip"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nip: Mapped[str] = mapped_column(String(32), nullable=False)
    settlement_type: Mapped[str] = mapped_column(String(64), nullable=False, default=DEFAULT_SETTLEMENT_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class SettlementTypeConfig(Base):
    __tablename__ = "settlement_type_configs"

    settlement_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("name", name="uq_products_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nip: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0.00"))
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    final_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("final_invoices.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items: Mapped[list[ReceiptItem]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="ReceiptItem.id",
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="Attachment.id",
    )
    final_invoice: Mapped[FinalInvoice | None] = relationship(back_populates="receipts")


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    __table_args__ = (
        CheckConstraint(
            "((quantity IS NOT NULL AND weight IS NULL) OR (quantity IS NULL AND weight IS NOT NULL))",
            name="ck_receipt_item_measure_choice",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(WeightValue, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    value: Mapped[Decimal] = mapped_column(Money, nullable=False)

    receipt: Mapped[Receipt] = relationship(back_populates="items")


class FinalInvoice(Base):
    __tablename__ = "final_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nip: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    receipts: Mapped[list[Receipt]] = relationship(back_populates="final_invoice")
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="final_invoice",
        cascade="all, delete-orphan",
        order_by="Attachment.id",
    )


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "((receipt_id IS NOT NULL AND final_invoice_id IS NULL) OR (receipt_id IS NULL AND final_invoice_id IS NOT NULL))",
            name="ck_attachment_document_owner",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"), nullable=True)
    final_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("final_invoices.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    receipt: Mapped[Receipt | None] = relationship(back_populates="attachments")
    final_invoice: Mapped[FinalInvoice | None] = relationship(back_populates="attachments")