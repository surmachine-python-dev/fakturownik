from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from fakturownik.config import AppPaths, get_app_paths
from fakturownik.database import session_scope
from fakturownik.models import (
    Attachment,
    Client,
    DEFAULT_SETTLEMENT_TYPE,
    FinalInvoice,
    Product,
    Receipt,
    ReceiptItem,
    SettlementTypeConfig,
)
from fakturownik.services.calculations import calculate_item, calculate_total, to_decimal


@dataclass
class ClientInput:
    company_name: str
    nip: str
    settlement_type: str = DEFAULT_SETTLEMENT_TYPE


@dataclass
class SettlementTypeConfigInput:
    settlement_type: str
    color_hex: str
    original_settlement_type: str | None = None


@dataclass
class ProductInput:
    name: str


@dataclass
class ReceiptItemInput:
    product_name: str
    quantity: int | None
    weight: Decimal | None
    unit_price: Decimal | None
    value: Decimal | None


@dataclass
class ReceiptInput:
    company_name: str
    nip: str
    issue_date: date
    items: list[ReceiptItemInput]
    attachment_paths: list[Path]


@dataclass
class FinalInvoiceInput:
    company_name: str
    nip: str
    issue_date: date
    receipt_ids: list[int]


class DocumentService:
    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or get_app_paths()

    def list_products(self) -> list[Product]:
        with session_scope() as session:
            statement = select(Product).order_by(Product.name.asc(), Product.id.asc())
            return list(session.scalars(statement))

    def save_product(self, payload: ProductInput, product_id: int | None = None) -> Product:
        name = payload.name.strip()
        if not name:
            raise ValueError("Nazwa towaru jest wymagana.")

        normalized_name = name.casefold()

        with session_scope() as session:
            existing_product = session.scalar(
                select(Product).where(func.lower(Product.name) == normalized_name)
            )
            if existing_product is not None and existing_product.id != product_id:
                raise ValueError("Towar o takiej nazwie juz istnieje.")

            if product_id is None:
                product = Product(name=name)
                session.add(product)
            else:
                product = session.get(Product, product_id)
                if product is None:
                    raise ValueError("Nie znaleziono towaru do edycji.")
                product.name = name

            session.flush()
            session.refresh(product)
            return product

    def delete_product(self, product_id: int) -> None:
        with session_scope() as session:
            product = session.get(Product, product_id)
            if product is None:
                raise ValueError("Nie znaleziono towaru do usuniecia.")
            session.delete(product)

    def list_clients(self) -> list[Client]:
        with session_scope() as session:
            statement = select(Client).order_by(Client.company_name.asc(), Client.id.asc())
            return list(session.scalars(statement))

    def list_settlement_type_configs(self) -> list[SettlementTypeConfig]:
        with session_scope() as session:
            statement = select(SettlementTypeConfig).order_by(func.lower(SettlementTypeConfig.settlement_type), SettlementTypeConfig.settlement_type)
            return list(session.scalars(statement))

    def save_settlement_type_config(self, payload: SettlementTypeConfigInput) -> SettlementTypeConfig:
        settlement_type = self._normalize_settlement_type(payload.settlement_type)
        original_settlement_type = self._normalize_optional_settlement_type(payload.original_settlement_type)
        color_hex = self._validate_color_hex(payload.color_hex)

        with session_scope() as session:
            if original_settlement_type is None:
                config = session.get(SettlementTypeConfig, settlement_type)
                if config is None:
                    config = SettlementTypeConfig(settlement_type=settlement_type, color_hex=color_hex)
                    session.add(config)
                else:
                    config.color_hex = color_hex
            else:
                config = session.get(SettlementTypeConfig, original_settlement_type)
                if config is None:
                    raise ValueError("Nie znaleziono typu rozliczenia do edycji.")
                if settlement_type != original_settlement_type:
                    duplicate = session.get(SettlementTypeConfig, settlement_type)
                    if duplicate is not None:
                        raise ValueError("Typ rozliczenia o takiej nazwie juz istnieje.")
                    clients = session.scalars(select(Client).where(Client.settlement_type == original_settlement_type))
                    for client in clients:
                        client.settlement_type = settlement_type
                    config.settlement_type = settlement_type
                config.color_hex = color_hex

            session.flush()
            session.refresh(config)
            return config

    def delete_settlement_type_config(self, settlement_type: str) -> str:
        normalized_type = self._normalize_settlement_type(settlement_type)

        with session_scope() as session:
            configs = list(
                session.scalars(
                    select(SettlementTypeConfig).order_by(
                        func.lower(SettlementTypeConfig.settlement_type),
                        SettlementTypeConfig.settlement_type,
                    )
                )
            )
            if len(configs) <= 1:
                raise ValueError("Musi istniec co najmniej jeden typ rozliczenia.")

            config = session.get(SettlementTypeConfig, normalized_type)
            if config is None:
                raise ValueError("Nie znaleziono typu rozliczenia do usuniecia.")

            replacement = next(item for item in configs if item.settlement_type != normalized_type)
            clients = session.scalars(select(Client).where(Client.settlement_type == normalized_type))
            for client in clients:
                client.settlement_type = replacement.settlement_type

            session.delete(config)
            return replacement.settlement_type

    def get_client_color_map_by_nip(self) -> dict[str, str]:
        with session_scope() as session:
            clients = list(session.scalars(select(Client)))
            color_by_type = {
                config.settlement_type: config.color_hex
                for config in session.scalars(select(SettlementTypeConfig))
            }
            return {
                client.nip: color_by_type[client.settlement_type]
                for client in clients
                if client.settlement_type in color_by_type
            }

    def save_client(self, payload: ClientInput, client_id: int | None = None) -> Client:
        company_name = payload.company_name.strip()
        nip = payload.nip.strip()
        settlement_type = self._normalize_settlement_type(payload.settlement_type)
        if not company_name:
            raise ValueError("Nazwa klienta jest wymagana.")
        if not nip:
            raise ValueError("NIP klienta jest wymagany.")

        with session_scope() as session:
            existing_client = session.scalar(select(Client).where(Client.nip == nip))
            if existing_client is not None and existing_client.id != client_id:
                raise ValueError("Klient z takim NIP juz istnieje.")
            if session.get(SettlementTypeConfig, settlement_type) is None:
                raise ValueError("Wybierz istniejacy typ rozliczenia klienta.")

            if client_id is None:
                client = Client(company_name=company_name, nip=nip, settlement_type=settlement_type)
                session.add(client)
            else:
                client = session.get(Client, client_id)
                if client is None:
                    raise ValueError("Nie znaleziono klienta do edycji.")
                client.company_name = company_name
                client.nip = nip
                client.settlement_type = settlement_type

            session.flush()
            session.refresh(client)
            return client

    def delete_client(self, client_id: int) -> None:
        with session_scope() as session:
            client = session.get(Client, client_id)
            if client is None:
                raise ValueError("Nie znaleziono klienta do usuniecia.")
            session.delete(client)

    def list_receipts(self) -> list[Receipt]:
        with session_scope() as session:
            statement = select(Receipt).options(selectinload(Receipt.items), selectinload(Receipt.attachments)).order_by(Receipt.id.desc())
            return list(session.scalars(statement))

    def get_receipt(self, receipt_id: int) -> Receipt | None:
        with session_scope() as session:
            statement = (
                select(Receipt)
                .options(selectinload(Receipt.items), selectinload(Receipt.attachments))
                .where(Receipt.id == receipt_id)
            )
            return session.scalar(statement)

    def delete_receipt(self, receipt_id: int) -> None:
        with session_scope() as session:
            receipt = session.scalar(
                select(Receipt)
                .options(selectinload(Receipt.attachments))
                .where(Receipt.id == receipt_id)
            )
            if receipt is None:
                raise ValueError("Nie znaleziono rachunku do usuniecia.")
            if receipt.is_locked:
                raise ValueError("Rachunek jest zablokowany. Najpierw go odblokuj.")

            for attachment in list(receipt.attachments):
                target_path = self.paths.attachments_dir / attachment.stored_name
                if target_path.exists():
                    target_path.unlink()

            session.delete(receipt)

    def unlock_receipt(self, receipt_id: int) -> Receipt:
        with session_scope() as session:
            receipt = session.scalar(
                select(Receipt)
                .options(selectinload(Receipt.final_invoice).selectinload(FinalInvoice.receipts))
                .where(Receipt.id == receipt_id)
            )
            if receipt is None:
                raise ValueError("Nie znaleziono rachunku do odblokowania.")
            if not receipt.is_locked or receipt.final_invoice_id is None:
                raise ValueError("Wybrany rachunek nie jest zablokowany.")

            final_invoice = receipt.final_invoice
            receipt.final_invoice_id = None
            receipt.is_locked = False
            session.flush()

            if final_invoice is not None:
                remaining_receipts = [item for item in final_invoice.receipts if item.id != receipt.id]
                if remaining_receipts:
                    final_invoice.total = calculate_total([item.total for item in remaining_receipts])
                else:
                    session.delete(final_invoice)

            session.flush()
            session.refresh(receipt)
            return receipt

    def save_receipt(self, payload: ReceiptInput, receipt_id: int | None = None) -> Receipt:
        self._validate_receipt_payload(payload)

        with session_scope() as session:
            if receipt_id is None:
                receipt = Receipt(
                    company_name=payload.company_name.strip(),
                    nip=payload.nip.strip(),
                    issue_date=payload.issue_date,
                )
                session.add(receipt)
            else:
                receipt = session.get(Receipt, receipt_id)
                if receipt is None:
                    raise ValueError("Nie znaleziono rachunku do edycji.")
                if receipt.is_locked:
                    raise ValueError("Rachunek jest przypisany do faktury koncowej i nie mozna go edytowac.")
                receipt.company_name = payload.company_name.strip()
                receipt.nip = payload.nip.strip()
                receipt.issue_date = payload.issue_date
                receipt.items.clear()
                self._sync_existing_attachments(receipt, payload.attachment_paths)

            resolved_items: list[ReceiptItem] = []
            values: list[Decimal] = []
            for item_payload in payload.items:
                result = calculate_item(
                    quantity=item_payload.quantity,
                    weight=item_payload.weight,
                    unit_price=item_payload.unit_price,
                    value=item_payload.value,
                )
                values.append(result.value)
                resolved_items.append(
                    ReceiptItem(
                        product_name=item_payload.product_name.strip(),
                        quantity=result.quantity,
                        weight=result.weight,
                        unit_price=result.unit_price,
                        value=result.value,
                    )
                )

            receipt.items.extend(resolved_items)
            receipt.total = calculate_total(values)

            existing_stored_names = {attachment.stored_name for attachment in receipt.attachments}
            for source_path in payload.attachment_paths:
                if self._is_managed_attachment(source_path) and source_path.name in existing_stored_names:
                    continue
                stored_name = self._copy_attachment(source_path)
                receipt.attachments.append(
                    Attachment(
                        original_name=source_path.name,
                        stored_name=stored_name,
                    )
                )

            session.flush()
            session.refresh(receipt)
            return receipt

    def create_final_invoice(self, payload: FinalInvoiceInput) -> FinalInvoice:
        if not payload.company_name.strip():
            raise ValueError("Nazwa firmy jest wymagana.")
        if not payload.nip.strip():
            raise ValueError("NIP jest wymagany.")
        if not payload.receipt_ids:
            raise ValueError("Wybierz co najmniej jeden rachunek.")

        with session_scope() as session:
            receipts = list(
                session.scalars(
                    select(Receipt)
                    .options(selectinload(Receipt.items))
                    .where(Receipt.id.in_(payload.receipt_ids))
                    .order_by(Receipt.id)
                )
            )

            if len(receipts) != len(set(payload.receipt_ids)):
                raise ValueError("Nie znaleziono wszystkich wskazanych rachunkow.")
            if any(receipt.final_invoice_id is not None for receipt in receipts):
                raise ValueError("Co najmniej jeden rachunek jest juz przypisany do faktury koncowej.")

            total = calculate_total([receipt.total for receipt in receipts])
            final_invoice = FinalInvoice(
                company_name=payload.company_name.strip(),
                nip=payload.nip.strip(),
                issue_date=payload.issue_date,
                total=total,
            )
            session.add(final_invoice)
            session.flush()

            for receipt in receipts:
                receipt.final_invoice_id = final_invoice.id
                receipt.is_locked = True

            session.flush()
            session.refresh(final_invoice)
            return final_invoice

    def list_available_receipts(self) -> list[Receipt]:
        with session_scope() as session:
            statement = (
                select(Receipt)
                .where(Receipt.final_invoice_id.is_(None))
                .order_by(Receipt.issue_date.desc(), Receipt.id.desc())
            )
            return list(session.scalars(statement))

    def list_final_invoices(self) -> list[FinalInvoice]:
        with session_scope() as session:
            statement = (
                select(FinalInvoice)
                .options(selectinload(FinalInvoice.receipts))
                .order_by(FinalInvoice.id.desc())
            )
            return list(session.scalars(statement))

    def get_final_invoice(self, final_invoice_id: int) -> FinalInvoice | None:
        with session_scope() as session:
            statement = (
                select(FinalInvoice)
                .options(
                    selectinload(FinalInvoice.receipts).selectinload(Receipt.items),
                    selectinload(FinalInvoice.attachments),
                )
                .where(FinalInvoice.id == final_invoice_id)
            )
            return session.scalar(statement)

    def _validate_receipt_payload(self, payload: ReceiptInput) -> None:
        if not payload.company_name.strip():
            raise ValueError("Nazwa firmy jest wymagana.")
        if not payload.nip.strip():
            raise ValueError("NIP jest wymagany.")
        if not payload.items:
            raise ValueError("Rachunek musi miec co najmniej jedna pozycje.")
        for item in payload.items:
            if not item.product_name.strip():
                raise ValueError("Kazda pozycja musi miec nazwe towaru.")

    def _copy_attachment(self, source_path: Path) -> str:
        if not source_path.exists():
            raise ValueError(f"Nie znaleziono zalacznika: {source_path}")
        stored_name = f"{uuid4().hex}_{source_path.name}"
        target_path = self.paths.attachments_dir / stored_name
        shutil.copy2(source_path, target_path)
        return stored_name

    def _sync_existing_attachments(self, receipt: Receipt, attachment_paths: list[Path]) -> None:
        preserved_names = {
            path.name
            for path in attachment_paths
            if self._is_managed_attachment(path)
        }
        attachments_to_remove = [
            attachment
            for attachment in receipt.attachments
            if attachment.stored_name not in preserved_names
        ]
        for attachment in attachments_to_remove:
            target_path = self.paths.attachments_dir / attachment.stored_name
            if target_path.exists():
                target_path.unlink()
            receipt.attachments.remove(attachment)

    def _is_managed_attachment(self, source_path: Path) -> bool:
        try:
            return source_path.resolve().parent == self.paths.attachments_dir.resolve()
        except FileNotFoundError:
            return False

    def _normalize_settlement_type(self, settlement_type: str) -> str:
        normalized_type = settlement_type.strip().lower()
        if not normalized_type:
            raise ValueError("Typ rozliczenia jest wymagany.")
        return normalized_type

    def _normalize_optional_settlement_type(self, settlement_type: str | None) -> str | None:
        if settlement_type is None:
            return None
        return self._normalize_settlement_type(settlement_type)

    def _validate_color_hex(self, color_hex: str) -> str:
        normalized_color = color_hex.strip().upper()
        if len(normalized_color) != 7 or not normalized_color.startswith("#"):
            raise ValueError("Kolor musi miec format #RRGGBB.")
        if any(character not in "0123456789ABCDEF" for character in normalized_color[1:]):
            raise ValueError("Kolor musi miec format #RRGGBB.")
        return normalized_color


def build_receipt_item_input(raw_item: dict[str, object]) -> ReceiptItemInput:
    quantity_value = raw_item.get("quantity")
    weight_value = raw_item.get("weight")
    unit_price_value = raw_item.get("unit_price")
    value_value = raw_item.get("value")

    quantity = int(quantity_value) if quantity_value not in (None, "") else None
    weight = to_decimal(weight_value) if weight_value not in (None, "") else None
    unit_price = to_decimal(unit_price_value) if unit_price_value not in (None, "") else None
    value = to_decimal(value_value) if value_value not in (None, "") else None

    return ReceiptItemInput(
        product_name=str(raw_item.get("product_name", "")),
        quantity=quantity,
        weight=weight,
        unit_price=unit_price,
        value=value,
    )