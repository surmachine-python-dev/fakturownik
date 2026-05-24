from __future__ import annotations

from html import escape
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QIcon, QPageLayout, QPageSize, QPainter, QPainterPath, QPalette, QPdfWriter, QPen, QPixmap, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QColorDialog,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fakturownik.config import get_app_paths
from fakturownik.database import init_database
from fakturownik.models import DEFAULT_SETTLEMENT_TYPE_COLORS, FinalInvoice
from fakturownik.services.backup import export_backup, import_backup
from fakturownik.services.calculations import calculate_item, money, to_decimal
from fakturownik.services.documents import (
    ClientInput,
    DocumentService,
    FinalInvoiceInput,
    ProductInput,
    ReceiptInput,
    SettlementTypeConfigInput,
    build_receipt_item_input,
)


BRAND_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "app_icon.ico"
RECEIPT_WARNING_TOTAL = Decimal("14500.00")


def decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{money(value):.2f} zł"


def measure_text(quantity: int | None, weight: Decimal | None) -> str:
    if quantity is not None:
        return str(quantity)
    if weight is not None:
        return f"{weight:.3f}"
    return ""


def aggregate_measure_text(quantity: int | None, weight: Decimal | None) -> str:
    parts: list[str] = []
    if quantity is not None:
        parts.append(str(quantity))
    if weight is not None:
        parts.append(f"{weight:.3f}")
    return " / ".join(parts)


def weight_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value:.3f} kg"


def infer_price_driver(
    quantity: int | None,
    weight: Decimal | None,
    unit_price: Decimal | None,
    value: Decimal | None,
) -> str:
    if unit_price is None:
        return "value"
    if value is None:
        return "unit_price"

    measure = Decimal(quantity) if quantity is not None else weight
    if measure is None:
        return "unit_price"

    return "unit_price" if money(measure * unit_price) == money(value) else "value"


def build_brand_logo(size: int = 36) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    background_rect = QRectF(2, 2, size - 4, size - 4)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#0f766e"))
    painter.drawRoundedRect(background_rect, 10, 10)

    fold_path = QPainterPath()
    fold_path.moveTo(size * 0.62, size * 0.16)
    fold_path.lineTo(size * 0.82, size * 0.16)
    fold_path.lineTo(size * 0.82, size * 0.36)
    fold_path.closeSubpath()
    painter.setBrush(QColor("#99f6e4"))
    painter.drawPath(fold_path)

    painter.setPen(QPen(QColor("white"), 2.2, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(size * 0.22, size * 0.40), QPointF(size * 0.78, size * 0.40))
    painter.drawLine(QPointF(size * 0.22, size * 0.54), QPointF(size * 0.78, size * 0.54))
    painter.drawLine(QPointF(size * 0.22, size * 0.68), QPointF(size * 0.52, size * 0.68))

    painter.setBrush(QColor("#f59e0b"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(size * 0.56, size * 0.58, size * 0.18, size * 0.18))

    painter.end()
    return pixmap


def load_brand_icon() -> QIcon:
    if BRAND_ICON_PATH.exists():
        icon = QIcon(str(BRAND_ICON_PATH))
        if not icon.isNull():
            return icon
    return QIcon(build_brand_logo(64))


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1e1f22"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#2b2d30"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#25272b"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2b2d30"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2b2d30"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0f766e"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#a1a1aa"))
    palette.setColor(QPalette.ColorRole.Light, QColor("#3b3d41"))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#313338"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#1a1b1e"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#232428"))
    palette.setColor(QPalette.ColorRole.Shadow, QColor("#111214"))
    palette.setColor(QPalette.Disabled, QPalette.ColorRole.Text, QColor("#7c7f86"))
    palette.setColor(QPalette.Disabled, QPalette.ColorRole.ButtonText, QColor("#7c7f86"))
    palette.setColor(QPalette.Disabled, QPalette.ColorRole.WindowText, QColor("#7c7f86"))
    app.setPalette(palette)


class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value=None) -> None:
        super().__init__(text)
        self.sort_value = text if sort_value is None else sort_value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        other_sort_value = getattr(other, "sort_value", other.text())
        return self.sort_value < other_sort_value


def settlement_type_label(value: str) -> str:
    if not value:
        return ""
    return value[:1].upper() + value[1:]


def _contrast_color(background: QColor) -> QColor:
    luminance = (background.red() * 299 + background.green() * 587 + background.blue() * 114) / 1000
    return QColor("#111111") if luminance >= 160 else QColor("#ffffff")


def apply_background_to_table_row(table: QTableWidget, row: int, color_hex: str) -> None:
    background = QColor(color_hex)
    if not background.isValid():
        return
    foreground = _contrast_color(background)
    for column in range(table.columnCount()):
        item = table.item(row, column)
        if item is None:
            continue
        item.setBackground(background)
        item.setForeground(foreground)


def apply_background_to_list_item(item: QListWidgetItem, color_hex: str) -> None:
    background = QColor(color_hex)
    if not background.isValid():
        return
    item.setBackground(background)
    item.setForeground(_contrast_color(background))


class FinalInvoicePreviewDialog(QDialog):
        PREVIEW_PAGE_WIDTH = 794

        def __init__(self, final_invoice: FinalInvoice, parent: QWidget | None = None) -> None:
                super().__init__(parent)
                self.final_invoice = final_invoice
                self.setWindowTitle(f"Podglad faktury koncowej #{final_invoice.id}")
                self.resize(1120, 820)

                layout = QVBoxLayout(self)
                self.preview = QTextBrowser()
                self.preview.setOpenExternalLinks(False)
                self.preview.setStyleSheet(
                        "QTextBrowser {"
                    "background: #ffffff;"
                        "border: none;"
                    "padding: 18px;"
                    "selection-background-color: #dbeafe;"
                        "}"
                )
                self.preview.document().setDocumentMargin(0)
                self.preview.setHtml(self._build_preview_html())
                layout.addWidget(self.preview)

                actions = QHBoxLayout()
                self.export_pdf_button = QPushButton("Eksportuj do PDF")
                self.print_button = QPushButton("Drukuj")
                self.close_button = QPushButton("Zamknij")
                actions.addStretch(1)
                actions.addWidget(self.export_pdf_button)
                actions.addWidget(self.print_button)
                actions.addWidget(self.close_button)
                layout.addLayout(actions)

                self.export_pdf_button.clicked.connect(self.export_pdf)
                self.print_button.clicked.connect(self.print_document)
                self.close_button.clicked.connect(self.accept)

        def export_pdf(self) -> None:
                default_path = Path.cwd() / f"faktura_koncowa_{self.final_invoice.id}.pdf"
                file_name, _ = QFileDialog.getSaveFileName(self, "Eksportuj PDF", str(default_path), "PDF (*.pdf)")
                if not file_name:
                        return

                output_path = Path(file_name)
                if output_path.suffix.lower() != ".pdf":
                        output_path = output_path.with_suffix(".pdf")
                output_path.parent.mkdir(parents=True, exist_ok=True)

                writer = QPdfWriter(str(output_path))
                writer.setResolution(300)
                writer.setPageSize(QPageSize(QPageSize.A4))
                writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Millimeter)

                document = self._build_document(self._paint_area_size(writer))
                document.print_(writer)
                del writer

                if not output_path.exists() or output_path.stat().st_size == 0:
                        QMessageBox.warning(self, "PDF", "Nie udalo sie zapisac pliku PDF we wskazanej lokalizacji.")
                        return

                QMessageBox.information(self, "PDF", f"Zapisano PDF do:\n{output_path}")

        def print_document(self) -> None:
                printer = QPrinter(QPrinter.HighResolution)
                printer.setPageSize(QPageSize(QPageSize.A4))
                printer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Millimeter)
                dialog = QPrintDialog(printer, self)
                if dialog.exec() != QDialog.Accepted:
                        return
                document = self._build_document(self._paint_area_size(printer))
                document.print_(printer)

        def _paint_area_size(self, device) -> QSizeF:
                return QSizeF(device.pageLayout().paintRectPixels(device.resolution()).size())

        def _build_document(self, page_size: QSizeF | None = None) -> QTextDocument:
                document = QTextDocument(self)
                document.setDocumentMargin(0)
                document.setHtml(self._build_print_html())
                if page_size is not None:
                        document.setPageSize(page_size)
                        document.setTextWidth(page_size.width())
                return document

        def _build_preview_html(self) -> str:
                content = self._build_invoice_body_html(summary_background="#ffffff", table_header_background="#ffffff")
                return f"""
                <html>
                    <head>
                        <meta charset='utf-8'>
                        <style>
                            body {{
                                margin: 0;
                                padding: 0;
                                background: #ffffff;
                                font-family: 'Segoe UI', sans-serif;
                            }}
                            .preview-wrap {{
                                padding: 0 0 18px 0;
                            }}
                            .sheet {{
                                width: {self.PREVIEW_PAGE_WIDTH}px;
                                margin: 0 auto;
                                background: #ffffff;
                                border: 1px solid #d9dde3;
                                padding: 54px 56px 60px 56px;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class='preview-wrap'>
                            <div class='sheet'>
                                {content}
                            </div>
                        </div>
                    </body>
                </html>
                """

        def _build_print_html(self) -> str:
                content = self._build_invoice_body_html(summary_background="#ffffff", table_header_background="#ffffff")
                return f"""
                <html>
                    <head>
                        <meta charset='utf-8'>
                        <style>
                            body {{
                                margin: 0;
                                padding: 0;
                                font-family: 'Segoe UI', sans-serif;
                                color: #111111;
                            }}
                        </style>
                    </head>
                    <body>
                        {content}
                    </body>
                </html>
                """

        def _build_invoice_body_html(self, summary_background: str, table_header_background: str) -> str:
                receipt_sections: list[str] = []
                aggregated_items: dict[str, dict[str, Decimal | int | bool]] = {}
                for receipt in self.final_invoice.receipts:
                        item_rows = "".join(
                                (
                                        "<tr>"
                                        f"<td class='col-name'>{escape(item.product_name)}</td>"
                                        f"<td class='col-measure'>{escape(measure_text(item.quantity, item.weight))}</td>"
                                        f"<td class='col-money'>{escape(decimal_text(item.unit_price))}</td>"
                                        f"<td class='col-money'>{escape(decimal_text(item.value))}</td>"
                                        "</tr>"
                                )
                                for item in receipt.items
                        )
                        for item in receipt.items:
                                aggregated_item = aggregated_items.setdefault(
                                        item.product_name,
                                        {
                                                "quantity": 0,
                                                "weight": Decimal("0.000"),
                                                "has_quantity": False,
                                                "has_weight": False,
                                        },
                                )
                                if item.quantity is not None:
                                        aggregated_item["quantity"] = int(aggregated_item["quantity"] or 0) + item.quantity
                                        aggregated_item["has_quantity"] = True
                                if item.weight is not None:
                                        aggregated_item["weight"] = Decimal(aggregated_item["weight"] or Decimal("0.000")) + item.weight
                                        aggregated_item["has_weight"] = True
                        receipt_sections.append(
                                "<div class='receipt-block'>"
                                f"<div class='receipt-header'><span class='receipt-title'>Rachunek #{receipt.id}</span><span>Data: {escape(receipt.issue_date.isoformat())}</span><span>Razem: {escape(decimal_text(receipt.total))}</span></div>"
                                "<table class='items-table'>"
                                "<thead><tr><th>Pozycja</th><th>Ilosc / waga</th><th>Cena jedn.</th><th>Wartosc</th></tr></thead>"
                                f"<tbody>{item_rows}</tbody>"
                                "</table>"
                                "</div>"
                        )

                receipts_count = len(self.final_invoice.receipts)
                aggregated_rows = "".join(
                        (
                            "<tr>"
                            f"<td class='col-name'>{escape(product_name)}</td>"
                            f"<td class='col-measure'>{escape(aggregate_measure_text(data['quantity'] if data['has_quantity'] else None, data['weight'] if data['has_weight'] else None))}</td>"
                            "</tr>"
                        )
                        for product_name, data in aggregated_items.items()
                    )
                aggregated_html = (
                        "<div class='receipt-block aggregate-block'>"
                        "<div class='receipt-header'><span class='receipt-title'>Suma towarow</span></div>"
                        "<table class='items-table aggregate-table'>"
                        "<thead><tr><th>Towar</th><th>Ilosc / waga</th></tr></thead>"
                        f"<tbody>{aggregated_rows}</tbody>"
                        "</table>"
                        "</div>"
                    ) if aggregated_rows else ""
                receipts_html = "".join(receipt_sections) or "<p class='empty'>Brak powiazanych rachunkow.</p>"
                intro_text = "Dokument zbiorczy wygenerowany na podstawie rachunkow zarejestrowanych w systemie."
                return f"""
                <style>
                    .document {{ color: #111111; }}
                    .document * {{ color: #111111; }}
                    .document {{ font-family: 'Segoe UI', sans-serif; }}
                    .doc-title {{
                        margin: 0 0 6px 0;
                        font-size: 21pt;
                        font-weight: 700;
                        letter-spacing: 0.2px;
                    }}
                    .doc-subtitle {{
                        margin: 0 0 24px 0;
                        font-size: 9.5pt;
                        color: #444444;
                    }}
                    .header-table {{
                        width: 100%;
                        border-collapse: separate;
                        border-spacing: 0;
                        margin-bottom: 18px;
                    }}
                    .header-cell-left {{
                        width: 62%;
                        padding-right: 10px;
                        vertical-align: top;
                    }}
                    .header-cell-right {{
                        width: 38%;
                        vertical-align: top;
                    }}
                    .box {{
                        border: 1px solid #cdd5df;
                        background: #ffffff;
                        padding: 14px 16px 13px 16px;
                    }}
                    .box-title {{
                        margin: 0 0 9px 0;
                        font-size: 8pt;
                        font-weight: 700;
                        text-transform: uppercase;
                        letter-spacing: 0.8px;
                        color: #5b6470;
                    }}
                    .box-line {{
                        margin: 0 0 4px 0;
                        font-size: 10pt;
                        line-height: 1.45;
                    }}
                    .summary-table {{
                        width: 100%;
                        border-collapse: collapse;
                        margin-bottom: 26px;
                    }}
                    .summary-table td {{
                        border: 1px solid #2f3640;
                        padding: 10px 11px;
                        font-size: 10pt;
                    }}
                    .summary-label {{
                        width: 35%;
                        background: {summary_background};
                        font-weight: 700;
                    }}
                    .receipt-block {{
                        margin-top: 18px;
                        page-break-inside: avoid;
                    }}
                    .receipt-header {{
                        margin: 0 0 9px 0;
                        padding-top: 10px;
                        border-top: 1px solid #d9dee5;
                        font-size: 10pt;
                        font-weight: 600;
                    }}
                    .receipt-header span {{
                        margin-right: 18px;
                    }}
                    .receipt-title {{
                        font-weight: 700;
                    }}
                    .items-table {{
                        width: 100%;
                        border-collapse: collapse;
                        table-layout: fixed;
                    }}
                    .items-table th, .items-table td {{
                        border: 1px solid #3b434c;
                        padding: 7px 9px;
                        font-size: 9.3pt;
                    }}
                    .items-table th {{
                        background: {table_header_background};
                        font-weight: 700;
                        text-align: left;
                    }}
                    .aggregate-block {{
                        margin-bottom: 26px;
                    }}
                    .aggregate-table .col-name {{ width: 70%; }}
                    .aggregate-table .col-measure {{ width: 30%; }}
                    .col-name {{ width: 46%; }}
                    .col-measure {{ width: 16%; text-align: center; }}
                    .col-money {{ width: 19%; text-align: right; }}
                    .empty {{
                        font-size: 10pt;
                        color: #444444;
                    }}
                </style>
                <div class='document'>
                    <h1 class='doc-title'>Faktura koncowa #{self.final_invoice.id}</h1>
                    <p class='doc-subtitle'>{escape(intro_text)}</p>

                    <table class='header-table'>
                        <tr>
                            <td class='header-cell-left'>
                                <div class='box'>
                                    <p class='box-title'>Nabywca</p>
                                    <p class='box-line'><strong>{escape(self.final_invoice.company_name)}</strong></p>
                                    <p class='box-line'>NIP: {escape(self.final_invoice.nip)}</p>
                                </div>
                            </td>
                            <td class='header-cell-right'>
                                <div class='box'>
                                    <p class='box-title'>Dane dokumentu</p>
                                    <p class='box-line'>Numer: #{self.final_invoice.id}</p>
                                    <p class='box-line'>Data wystawienia: {escape(self.final_invoice.issue_date.isoformat())}</p>
                                </div>
                            </td>
                        </tr>
                    </table>

                    <table class='summary-table'>
                        <tr>
                            <td class='summary-label'>Liczba rachunkow</td>
                            <td>{receipts_count}</td>
                        </tr>
                        <tr>
                            <td class='summary-label'>Razem</td>
                            <td><strong>{escape(decimal_text(self.final_invoice.total))}</strong></td>
                        </tr>
                    </table>

                    {aggregated_html}
                    {receipts_html}
                </div>
                """


class ReceiptEditor(QWidget):
    def __init__(self, service: DocumentService, refresh_callback) -> None:
        super().__init__()
        self.service = service
        self.refresh_callback = refresh_callback
        self.current_receipt_id: int | None = None
        self.current_locked = False
        self.attachment_paths: list[Path] = []
        self._building_form = False
        self.last_price_driver = "unit_price"
        self.clients_cache: dict[int, tuple[str, str]] = {}
        self.products_cache: dict[int, str] = {}
        self.hide_locked_receipts = False

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        form_panel = self._build_form_panel()
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QScrollArea.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form_scroll.setWidget(form_panel)
        splitter.addWidget(form_scroll)
        splitter.addWidget(self._build_list_panel())
        splitter.setSizes([700, 500])
        layout.addWidget(splitter)

        self.refresh_receipts()
        self.reset_form()

    def _build_form_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 12, 0)

        top_actions = QHBoxLayout()
        self.new_button = QPushButton("Nowy rachunek")
        self.save_button = QPushButton("Zapisz rachunek")
        top_actions.addWidget(self.new_button)
        top_actions.addWidget(self.save_button)
        top_actions.addStretch(1)
        layout.addLayout(top_actions)

        header_group = QGroupBox("Rachunek")
        header_form = QFormLayout(header_group)
        self.client_select = QComboBox()
        self.client_select.setEditable(True)
        self.client_select.setInsertPolicy(QComboBox.NoInsert)
        self.client_select.setPlaceholderText("Szukaj po nazwie klienta lub NIP")
        client_completer = self.client_select.completer()
        if client_completer is not None:
            client_completer.setCaseSensitivity(Qt.CaseInsensitive)
            client_completer.setFilterMode(Qt.MatchContains)
            client_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.client_select.currentIndexChanged.connect(self._on_client_changed)
        self.client_select.editTextChanged.connect(self._on_client_text_changed)
        self.company_name_input = QLineEdit()
        self.company_name_input.setReadOnly(True)
        self.nip_input = QLineEdit()
        self.nip_input.setReadOnly(True)
        self.issue_date_input = QDateEdit()
        self.issue_date_input.setCalendarPopup(True)
        self.issue_date_input.setDate(date.today())
        header_form.addRow("Klient", self.client_select)
        header_form.addRow("Nazwa firmy", self.company_name_input)
        header_form.addRow("NIP", self.nip_input)
        header_form.addRow("Data wystawienia", self.issue_date_input)
        layout.addWidget(header_group)

        item_group = QGroupBox("Pozycja rachunku")
        item_layout = QGridLayout(item_group)
        self.product_name_input = QComboBox()
        self.product_name_input.setEditable(True)
        self.product_name_input.setInsertPolicy(QComboBox.NoInsert)
        self.product_name_input.setPlaceholderText("Szukaj towaru po nazwie")
        product_completer = self.product_name_input.completer()
        if product_completer is not None:
            product_completer.setCaseSensitivity(Qt.CaseInsensitive)
            product_completer.setFilterMode(Qt.MatchContains)
            product_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.product_name_input.currentIndexChanged.connect(self._on_product_changed)
        self.product_name_input.editTextChanged.connect(self._on_product_text_changed)
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(0, 1_000_000)
        self.weight_input = QDoubleSpinBox()
        self.weight_input.setDecimals(3)
        self.weight_input.setRange(0, 1_000_000)
        self.unit_price_input = QDoubleSpinBox()
        self.unit_price_input.setDecimals(2)
        self.unit_price_input.setRange(0, 1_000_000)
        self.value_input = QDoubleSpinBox()
        self.value_input.setDecimals(2)
        self.value_input.setRange(0, 1_000_000)
        self.item_message = QLabel()
        self.item_message.setStyleSheet("color: #8b0000;")

        item_layout.addWidget(QLabel("Nazwa towaru"), 0, 0)
        item_layout.addWidget(self.product_name_input, 0, 1, 1, 3)
        item_layout.addWidget(QLabel("Ilosc"), 1, 0)
        item_layout.addWidget(self.quantity_input, 1, 1)
        item_layout.addWidget(QLabel("Waga"), 1, 2)
        item_layout.addWidget(self.weight_input, 1, 3)
        item_layout.addWidget(QLabel("Cena jednostkowa"), 2, 0)
        item_layout.addWidget(self.unit_price_input, 2, 1)
        item_layout.addWidget(QLabel("Wartosc"), 2, 2)
        item_layout.addWidget(self.value_input, 2, 3)
        item_layout.addWidget(self.item_message, 3, 0, 1, 4)

        item_buttons = QHBoxLayout()
        self.add_item_button = QPushButton("Dodaj pozycje")
        self.remove_item_button = QPushButton("Usun zaznaczona pozycje")
        item_buttons.addWidget(self.add_item_button)
        item_buttons.addWidget(self.remove_item_button)
        item_layout.addLayout(item_buttons, 4, 0, 1, 4)
        layout.addWidget(item_group)

        products_group = QGroupBox("Pozycje rachunku")
        products_layout = QVBoxLayout(products_group)
        self.items_table = QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(["Towar", "Ilosc", "Waga", "Cena jedn.", "Wartosc"])
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.setMinimumHeight(260)
        products_layout.addWidget(self.items_table)
        layout.addWidget(products_group, 1)

        attachments_group = QGroupBox("Zalaczniki")
        attachments_group_layout = QVBoxLayout(attachments_group)
        self.attachments_toggle_button = QToolButton()
        self.attachments_toggle_button.setText("Pokaz zalaczniki")
        self.attachments_toggle_button.setCheckable(True)
        self.attachments_toggle_button.setChecked(False)
        self.attachments_toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.attachments_toggle_button.setArrowType(Qt.RightArrow)
        attachments_group_layout.addWidget(self.attachments_toggle_button)

        self.attachments_panel = QWidget()
        attachment_layout = QVBoxLayout(self.attachments_panel)
        attachment_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_list = QListWidget()
        self.attachments_list.setMinimumHeight(90)
        attachment_buttons = QHBoxLayout()
        self.add_attachment_button = QPushButton("Dodaj pliki")
        self.remove_attachment_button = QPushButton("Usun zaznaczony plik")
        attachment_buttons.addWidget(self.add_attachment_button)
        attachment_buttons.addWidget(self.remove_attachment_button)
        attachment_layout.addWidget(self.attachments_list)
        attachment_layout.addLayout(attachment_buttons)
        self.attachments_panel.setVisible(False)
        attachments_group_layout.addWidget(self.attachments_panel)
        layout.addWidget(attachments_group)

        footer = QHBoxLayout()
        self.total_label = QLabel(f"Razem: {decimal_text(Decimal('0.00'))}")
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #8b0000;")
        footer.addWidget(self.total_label)
        footer.addStretch(1)
        footer.addWidget(self.status_label)
        layout.addLayout(footer)

        self.quantity_input.valueChanged.connect(self._recalculate_item_preview)
        self.weight_input.valueChanged.connect(self._recalculate_item_preview)
        self.unit_price_input.valueChanged.connect(self._on_unit_price_changed)
        self.value_input.valueChanged.connect(self._on_value_changed)
        self.add_item_button.clicked.connect(self.add_item)
        self.remove_item_button.clicked.connect(self.remove_selected_item)
        self.items_table.itemDoubleClicked.connect(self.edit_item)
        self.add_attachment_button.clicked.connect(self.add_attachments)
        self.remove_attachment_button.clicked.connect(self.remove_attachment)
        self.attachments_toggle_button.toggled.connect(self._toggle_attachments_panel)
        self.new_button.clicked.connect(self.reset_form)
        self.save_button.clicked.connect(self.save_receipt)

        return container

    def refresh_products(self) -> None:
        products = self.service.list_products()
        current_product_id = self.product_name_input.currentData()
        self.product_name_input.blockSignals(True)
        self.product_name_input.clear()
        self.products_cache = {}

        if not products:
            self.product_name_input.addItem("Brak towarow - dodaj towar w osobnej zakladce", None)
            self.product_name_input.setEnabled(False)
        else:
            self.product_name_input.setEnabled(True)
            for product in products:
                self.product_name_input.addItem(product.name, product.id)
                self.products_cache[product.id] = product.name

            if current_product_id in self.products_cache:
                self.product_name_input.setCurrentIndex(self.product_name_input.findData(current_product_id))
            else:
                self.product_name_input.setCurrentIndex(-1)
                self.product_name_input.setEditText("")

        self.product_name_input.blockSignals(False)

    def refresh_clients(self) -> None:
        clients = self.service.list_clients()
        current_client_id = self.client_select.currentData()
        self.client_select.blockSignals(True)
        self.client_select.clear()
        self.clients_cache = {}

        if not clients:
            self.client_select.addItem("Brak klientow - dodaj klienta w osobnej zakladce", None)
            self.client_select.setEnabled(False)
            self.company_name_input.clear()
            self.nip_input.clear()
        else:
            self.client_select.setEnabled(True)
            for client in clients:
                label = f"{client.company_name} | {client.nip}"
                self.client_select.addItem(label, client.id)
                self.clients_cache[client.id] = (client.company_name, client.nip)

            if current_client_id in self.clients_cache:
                self.client_select.setCurrentIndex(self.client_select.findData(current_client_id))
            else:
                self.client_select.setCurrentIndex(0)
            self._apply_selected_client()

        self.client_select.blockSignals(False)

    def _build_list_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Istniejace rachunki"))
        self.receipts_search_input = QLineEdit()
        self.receipts_search_input.setPlaceholderText("Szukaj po nazwie klienta lub NIP")
        self.receipts_search_input.textChanged.connect(self.refresh_receipts)
        layout.addWidget(self.receipts_search_input)
        actions = QHBoxLayout()
        self.hide_locked_button = QPushButton("Ukryj zablokowane")
        self.hide_locked_button.setCheckable(True)
        self.unlock_receipt_button = QPushButton("Odblokuj rachunek")
        self.delete_receipt_button = QPushButton("Usun rachunek")
        self.unlock_receipt_button.setEnabled(False)
        self.delete_receipt_button.setEnabled(False)
        actions.addWidget(self.hide_locked_button)
        actions.addStretch(1)
        actions.addWidget(self.unlock_receipt_button)
        actions.addWidget(self.delete_receipt_button)
        layout.addLayout(actions)
        self.receipts_table = QTableWidget(0, 6)
        self.receipts_table.setHorizontalHeaderLabels(["ID", "Firma", "NIP", "Data", "Razem", "Status"])
        self.receipts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.receipts_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.receipts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.receipts_table.horizontalHeader().setStretchLastSection(True)
        self.receipts_table.setSortingEnabled(True)
        self.receipts_table.itemSelectionChanged.connect(self.load_selected_receipt)
        layout.addWidget(self.receipts_table)

        self.hide_locked_button.toggled.connect(self._toggle_hide_locked_receipts)
        self.unlock_receipt_button.clicked.connect(self.unlock_selected_receipt)
        self.delete_receipt_button.clicked.connect(self.delete_selected_receipt)
        return container

    def _on_unit_price_changed(self) -> None:
        if not self._building_form:
            self.last_price_driver = "unit_price"
        self._recalculate_item_preview()

    def _on_product_changed(self) -> None:
        if self.product_name_input.currentData() in self.products_cache:
            self.status_label.clear()

    def _on_product_text_changed(self, text: str) -> None:
        normalized_text = text.strip().casefold()
        if not normalized_text:
            return

        matched_index = -1
        for index in range(self.product_name_input.count()):
            label = self.product_name_input.itemText(index).strip().casefold()
            if label == normalized_text:
                matched_index = index
                break

        if matched_index >= 0 and matched_index != self.product_name_input.currentIndex():
            self.product_name_input.setCurrentIndex(matched_index)

    def _on_client_changed(self) -> None:
        self._apply_selected_client()

    def _on_client_text_changed(self, text: str) -> None:
        normalized_text = text.strip().lower()
        if not normalized_text:
            self.company_name_input.clear()
            self.nip_input.clear()
            return

        matched_index = -1
        for index in range(self.client_select.count()):
            label = self.client_select.itemText(index).strip().lower()
            if label == normalized_text:
                matched_index = index
                break

        if matched_index >= 0 and matched_index != self.client_select.currentIndex():
            self.client_select.setCurrentIndex(matched_index)
            return

        current_client_id = self.client_select.currentData()
        current_label = self.client_select.currentText().strip().lower()
        if matched_index < 0 or normalized_text != current_label or current_client_id not in self.clients_cache:
            self.company_name_input.clear()
            self.nip_input.clear()

    def _on_value_changed(self) -> None:
        if not self._building_form:
            self.last_price_driver = "value"
        self._recalculate_item_preview()

    def _recalculate_item_preview(self) -> None:
        if self._building_form:
            return
        try:
            result = self._resolve_item_inputs()
        except ValueError as exc:
            self.item_message.setText(str(exc))
            return

        self.item_message.setText(
            f"Podglad: cena {result.unit_price:.2f}, wartosc {result.value:.2f}"
        )
        self._building_form = True
        try:
            self.unit_price_input.setValue(float(result.unit_price))
            self.value_input.setValue(float(result.value))
        finally:
            self._building_form = False

    def add_item(self) -> None:
        if not self.products_cache:
            self._show_error("Najpierw dodaj towar w zakladce Towary.")
            return

        product_id = self.product_name_input.currentData()
        if product_id not in self.products_cache:
            self._show_error("Wybierz towar z listy, korzystajac z wyszukiwarki pola Nazwa towaru.")
            return

        product_name = self.products_cache[product_id]
        if not product_name:
            self._show_error("Podaj nazwe towaru.")
            return
        try:
            result = self._resolve_item_inputs()
        except ValueError as exc:
            self._show_error(str(exc))
            return

        item_data = {
            "product_name": product_name,
            "quantity": result.quantity,
            "weight": result.weight,
            "unit_price": result.unit_price,
            "value": result.value,
            "price_driver": self.last_price_driver,
        }

        existing_row = self._find_matching_item_row(item_data)
        if existing_row is not None:
            item_data = self._merge_item_data(existing_row, item_data)
            self._set_items_table_row(existing_row, item_data)
        else:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)
            self._set_items_table_row(row, item_data)

        self._sort_items_table()
        self._clear_item_inputs()
        self._update_total()
        self.status_label.clear()

    def remove_selected_item(self) -> None:
        selected_rows = sorted({item.row() for item in self.items_table.selectedItems()}, reverse=True)
        for row in selected_rows:
            self.items_table.removeRow(row)
        self._update_total()

    def edit_item(self, table_item: QTableWidgetItem) -> None:
        if self.current_locked:
            return

        row = table_item.row()
        item_data = self.items_table.item(row, 0).data(Qt.UserRole)
        self._building_form = True
        try:
            self.set_selected_product_name(item_data["product_name"])
            self.quantity_input.setValue(item_data["quantity"] or 0)
            self.weight_input.setValue(float(item_data["weight"] or 0))
            self.unit_price_input.setValue(float(item_data["unit_price"] or 0))
            self.value_input.setValue(float(item_data["value"] or 0))
            self.last_price_driver = str(
                item_data.get(
                    "price_driver",
                    infer_price_driver(
                        item_data["quantity"],
                        item_data["weight"],
                        item_data["unit_price"],
                        item_data["value"],
                    ),
                )
            )
        finally:
            self._building_form = False

        self.items_table.removeRow(row)
        self._recalculate_item_preview()
        self._update_total()
        self.status_label.setStyleSheet("color: #1f4f7a;")
        self.status_label.setText("Pozycja przeniesiona do edycji. Zapisz ja ponownie przyciskiem Dodaj pozycje.")

    def add_attachments(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Wybierz zalaczniki")
        for file_name in files:
            path = Path(file_name)
            if path not in self.attachment_paths:
                self.attachment_paths.append(path)
                self.attachments_list.addItem(str(path))

    def remove_attachment(self) -> None:
        current_row = self.attachments_list.currentRow()
        if current_row < 0:
            return
        self.attachment_paths.pop(current_row)
        self.attachments_list.takeItem(current_row)

    def _toggle_attachments_panel(self, expanded: bool) -> None:
        self.attachments_panel.setVisible(expanded)
        self.attachments_toggle_button.setText("Ukryj zalaczniki" if expanded else "Pokaz zalaczniki")
        self.attachments_toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)

    def refresh_receipts(self) -> None:
        receipts = self.service.list_receipts()
        color_by_nip = self.service.get_client_color_map_by_nip()
        search_text = self.receipts_search_input.text().strip().lower()
        self.receipts_table.setSortingEnabled(False)
        self.receipts_table.setRowCount(0)
        for receipt in receipts:
            if self.hide_locked_receipts and receipt.is_locked:
                continue
            if search_text and search_text not in receipt.company_name.lower() and search_text not in receipt.nip.lower():
                continue
            row = self.receipts_table.rowCount()
            self.receipts_table.insertRow(row)
            values = [
                str(receipt.id),
                receipt.company_name,
                receipt.nip,
                receipt.issue_date.isoformat(),
                decimal_text(receipt.total),
                "Zablokowany" if receipt.is_locked else "Roboczy",
            ]
            is_warning_total = receipt.total > RECEIPT_WARNING_TOTAL
            for column, value in enumerate(values):
                if column == 0:
                    table_item = SortableTableWidgetItem(value, receipt.id)
                elif column == 3:
                    table_item = SortableTableWidgetItem(value, receipt.issue_date.isoformat())
                elif column == 4:
                    table_item = SortableTableWidgetItem(value, float(receipt.total))
                else:
                    table_item = SortableTableWidgetItem(value, value.lower())
                if column == 0:
                    table_item.setData(Qt.UserRole, receipt.id)
                self.receipts_table.setItem(row, column, table_item)

            color_hex = color_by_nip.get(receipt.nip)
            if color_hex:
                apply_background_to_table_row(self.receipts_table, row, color_hex)
            if is_warning_total:
                for column in range(self.receipts_table.columnCount()):
                    table_item = self.receipts_table.item(row, column)
                    if table_item is not None:
                        table_item.setForeground(QColor("#b42318"))

        self.receipts_table.setSortingEnabled(True)
        self.current_receipt_id = None
        self.unlock_receipt_button.setEnabled(False)
        self.delete_receipt_button.setEnabled(False)

    def load_selected_receipt(self) -> None:
        selected_rows = self._selected_receipt_rows()
        if not selected_rows:
            self.current_receipt_id = None
            self.current_locked = False
            self.unlock_receipt_button.setEnabled(False)
            self.delete_receipt_button.setEnabled(False)
            return
        if len(selected_rows) > 1:
            self.current_receipt_id = None
            self.current_locked = False
            self._clear_receipt_editor_contents()
            self.unlock_receipt_button.setEnabled(False)
            self.delete_receipt_button.setEnabled(self._all_selected_receipts_unlocked(selected_rows))
            return

        receipt_id = self.receipts_table.item(selected_rows[0], 0).data(Qt.UserRole)
        receipt = self.service.get_receipt(receipt_id)
        if receipt is None:
            return

        self._clear_receipt_editor_contents()
        self.current_receipt_id = receipt.id
        self.current_locked = receipt.is_locked
        self.set_receipt_client(receipt.company_name, receipt.nip)
        self.issue_date_input.setDate(receipt.issue_date)
        self.unlock_receipt_button.setEnabled(receipt.is_locked)
        self.delete_receipt_button.setEnabled(not receipt.is_locked)

        for receipt_item in receipt.items:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)
            item_data = {
                "product_name": receipt_item.product_name,
                "quantity": receipt_item.quantity,
                "weight": receipt_item.weight,
                "unit_price": receipt_item.unit_price,
                "value": receipt_item.value,
                "price_driver": infer_price_driver(
                    receipt_item.quantity,
                    receipt_item.weight,
                    receipt_item.unit_price,
                    receipt_item.value,
                ),
            }
            for column, key in enumerate(["product_name", "quantity", "weight", "unit_price", "value"]):
                value = item_data[key]
                if key == "weight":
                    text = weight_text(value)
                elif isinstance(value, Decimal):
                    text = decimal_text(value)
                else:
                    text = "" if value is None else str(value)
                table_item = QTableWidgetItem(text)
                table_item.setData(Qt.UserRole, item_data)
                self.items_table.setItem(row, column, table_item)

        self._sort_items_table()

        self.attachment_paths = []
        self.attachments_list.clear()
        for attachment in receipt.attachments:
            path = get_app_paths().attachments_dir / attachment.stored_name
            self.attachment_paths.append(path)
            self.attachments_list.addItem(str(path))

        self._update_total()
        self._set_locked_state(receipt.is_locked)
        if receipt.is_locked:
            self.status_label.setText("Rachunek jest przypisany do faktury koncowej.")

    def reset_form(self, clear_selection: bool = True) -> None:
        self.current_receipt_id = None
        self.current_locked = False
        self.refresh_clients()
        self.refresh_products()
        self._clear_receipt_editor_contents()
        self._set_locked_state(False)
        self.issue_date_input.setDate(date.today())
        self.status_label.clear()
        self.unlock_receipt_button.setEnabled(False)
        self.delete_receipt_button.setEnabled(False)
        if clear_selection:
            self.receipts_table.clearSelection()

    def _clear_item_inputs(self) -> None:
        self.product_name_input.blockSignals(True)
        self.product_name_input.setCurrentIndex(-1)
        self.product_name_input.setEditText("")
        self.product_name_input.blockSignals(False)
        self.quantity_input.setValue(0)
        self.weight_input.setValue(0)
        self.unit_price_input.setValue(0)
        self.value_input.setValue(0)
        self.last_price_driver = "unit_price"
        self.item_message.clear()

    def _resolve_item_inputs(self):
        quantity = self.quantity_input.value() or None
        weight = to_decimal(self.weight_input.value()) if self.weight_input.value() > 0 else None
        unit_price = to_decimal(self.unit_price_input.value()) if self.unit_price_input.value() > 0 else None
        value = to_decimal(self.value_input.value()) if self.value_input.value() > 0 else None

        if unit_price is not None and value is not None:
            if self.last_price_driver == "value":
                unit_price = None
            else:
                value = None

        return calculate_item(quantity=quantity, weight=weight, unit_price=unit_price, value=value)

    def _find_matching_item_row(self, new_item_data: dict) -> int | None:
        new_product_name = new_item_data["product_name"].strip().casefold()
        new_unit_price = new_item_data["unit_price"]
        new_has_quantity = new_item_data["quantity"] is not None

        for row in range(self.items_table.rowCount()):
            existing_data = self.items_table.item(row, 0).data(Qt.UserRole)
            existing_product_name = existing_data["product_name"].strip().casefold()
            existing_has_quantity = existing_data["quantity"] is not None
            if existing_product_name != new_product_name:
                continue
            if existing_data["unit_price"] != new_unit_price:
                continue
            if existing_has_quantity != new_has_quantity:
                continue
            return row

        return None

    def _merge_item_data(self, row: int, new_item_data: dict) -> dict:
        existing_data = self.items_table.item(row, 0).data(Qt.UserRole)
        existing_price_driver = str(
            existing_data.get(
                "price_driver",
                infer_price_driver(
                    existing_data["quantity"],
                    existing_data["weight"],
                    existing_data["unit_price"],
                    existing_data["value"],
                ),
            )
        )
        new_price_driver = str(
            new_item_data.get(
                "price_driver",
                infer_price_driver(
                    new_item_data["quantity"],
                    new_item_data["weight"],
                    new_item_data["unit_price"],
                    new_item_data["value"],
                ),
            )
        )
        merged_price_driver = "value" if "value" in {existing_price_driver, new_price_driver} else "unit_price"
        if existing_data["quantity"] is not None:
            merged_quantity = existing_data["quantity"] + new_item_data["quantity"]
            result = calculate_item(
                quantity=merged_quantity,
                weight=None,
                unit_price=existing_data["unit_price"] if merged_price_driver == "unit_price" else None,
                value=(existing_data["value"] + new_item_data["value"]) if merged_price_driver == "value" else None,
            )
        else:
            merged_weight = existing_data["weight"] + new_item_data["weight"]
            result = calculate_item(
                quantity=None,
                weight=merged_weight,
                unit_price=existing_data["unit_price"] if merged_price_driver == "unit_price" else None,
                value=(existing_data["value"] + new_item_data["value"]) if merged_price_driver == "value" else None,
            )

        return {
            "product_name": existing_data["product_name"],
            "quantity": result.quantity,
            "weight": result.weight,
            "unit_price": result.unit_price,
            "value": result.value,
            "price_driver": merged_price_driver,
        }

    def _set_items_table_row(self, row: int, item_data: dict) -> None:
        for column, key in enumerate(["product_name", "quantity", "weight", "unit_price", "value"]):
            value = item_data[key]
            if key == "weight":
                text = weight_text(value)
            elif isinstance(value, Decimal):
                text = decimal_text(value)
            else:
                text = "" if value is None else str(value)
            table_item = QTableWidgetItem(text)
            table_item.setData(Qt.UserRole, item_data)
            self.items_table.setItem(row, column, table_item)

    def _sort_items_table(self) -> None:
        items_data = []
        for row in range(self.items_table.rowCount()):
            items_data.append(self.items_table.item(row, 0).data(Qt.UserRole))

        items_data.sort(
            key=lambda item: (
                item["product_name"].strip().casefold(),
                item["unit_price"],
                item["quantity"] is None,
                item["quantity"] or 0,
                item["weight"] or Decimal("0"),
            )
        )

        self.items_table.setRowCount(0)
        for item_data in items_data:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)
            self._set_items_table_row(row, item_data)

    def _update_total(self) -> None:
        total = Decimal("0.00")
        for row in range(self.items_table.rowCount()):
            data = self.items_table.item(row, 0).data(Qt.UserRole)
            total += data["value"]
        self.total_label.setText(f"Razem: {decimal_text(total)}")

    def save_receipt(self) -> None:
        try:
            if not self.clients_cache:
                raise ValueError("Najpierw dodaj klienta w zakladce Klienci.")
            selected_client_id = self.client_select.currentData()
            if selected_client_id not in self.clients_cache:
                raise ValueError("Wybierz klienta z listy, korzystajac z wyszukiwarki pola Klient.")
            items = []
            for row in range(self.items_table.rowCount()):
                item_data = self.items_table.item(row, 0).data(Qt.UserRole)
                items.append(build_receipt_item_input(item_data))

            payload = ReceiptInput(
                company_name=self.company_name_input.text(),
                nip=self.nip_input.text(),
                issue_date=self.issue_date_input.date().toPython(),
                items=items,
                attachment_paths=self.attachment_paths,
            )
            self.service.save_receipt(payload, receipt_id=self.current_receipt_id)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self.refresh_receipts()
        self.refresh_callback()
        self.reset_form()
        self.status_label.setStyleSheet("color: #006400;")
        self.status_label.setText("Rachunek zapisany.")

    def set_receipt_client(self, company_name: str, nip: str) -> None:
        stale_index = self.client_select.findData(-1)
        if stale_index >= 0:
            self.client_select.removeItem(stale_index)
        for client_id, values in self.clients_cache.items():
            if values == (company_name, nip):
                index = self.client_select.findData(client_id)
                if index >= 0:
                    self.client_select.setCurrentIndex(index)
                self._apply_selected_client()
                return

        self.client_select.blockSignals(True)
        self.client_select.insertItem(0, f"{company_name} | {nip} | spoza listy", -1)
        self.client_select.setCurrentIndex(0)
        self.client_select.blockSignals(False)
        self.company_name_input.setText(company_name)
        self.nip_input.setText(nip)

    def set_selected_product_name(self, product_name: str) -> None:
        stale_index = self.product_name_input.findData(-1)
        if stale_index >= 0:
            self.product_name_input.removeItem(stale_index)

        normalized_name = product_name.strip().casefold()
        for product_id, name in self.products_cache.items():
            if name.strip().casefold() == normalized_name:
                index = self.product_name_input.findData(product_id)
                if index >= 0:
                    self.product_name_input.setCurrentIndex(index)
                return

        self.product_name_input.blockSignals(True)
        self.product_name_input.insertItem(0, product_name, -1)
        self.product_name_input.setCurrentIndex(0)
        self.product_name_input.blockSignals(False)

    def _set_locked_state(self, locked: bool) -> None:
        editable_widgets = [
            self.client_select,
            self.company_name_input,
            self.nip_input,
            self.issue_date_input,
            self.product_name_input,
            self.quantity_input,
            self.weight_input,
            self.unit_price_input,
            self.value_input,
            self.add_item_button,
            self.remove_item_button,
            self.add_attachment_button,
            self.remove_attachment_button,
            self.save_button,
        ]
        for widget in editable_widgets:
            widget.setEnabled(not locked)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Blad", message)

    def _selected_receipt_rows(self) -> list[int]:
        return sorted({item.row() for item in self.receipts_table.selectedItems()})

    def _all_selected_receipts_unlocked(self, selected_rows: list[int]) -> bool:
        for row in selected_rows:
            status = self.receipts_table.item(row, 5).text()
            if status == "Zablokowany":
                return False
        return True

    def _clear_receipt_editor_contents(self) -> None:
        self.refresh_clients()
        self.refresh_products()
        self.items_table.setRowCount(0)
        self.attachments_list.clear()
        self.attachment_paths = []
        self._clear_item_inputs()
        self._update_total()
        self._set_locked_state(False)

    def _toggle_hide_locked_receipts(self, checked: bool) -> None:
        self.hide_locked_receipts = checked
        self.hide_locked_button.setText("Pokaz zablokowane" if checked else "Ukryj zablokowane")
        self.refresh_receipts()
        self.reset_form()

    def unlock_selected_receipt(self) -> None:
        if self.current_receipt_id is None:
            self._show_error("Wybierz rachunek do odblokowania.")
            return
        confirm = QMessageBox.question(
            self,
            "Odblokuj rachunek",
            "Odblokowanie odepnie rachunek od faktury koncowej. Kontynuowac?",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.service.unlock_receipt(self.current_receipt_id)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self.refresh_receipts()
        self.refresh_callback()
        self.reset_form()
        self.status_label.setStyleSheet("color: #006400;")
        self.status_label.setText("Rachunek odblokowany.")

    def delete_selected_receipt(self) -> None:
        selected_rows = self._selected_receipt_rows()
        if not selected_rows:
            self._show_error("Wybierz rachunek do usuniecia.")
            return
        locked_receipts = []
        receipt_descriptions = []
        receipt_ids = []
        for row in selected_rows:
            receipt_id = self.receipts_table.item(row, 0).data(Qt.UserRole)
            company_name = self.receipts_table.item(row, 1).text()
            issue_date = self.receipts_table.item(row, 3).text()
            status = self.receipts_table.item(row, 5).text()
            if status == "Zablokowany":
                locked_receipts.append(f"#{receipt_id} | {company_name} | {issue_date}")
            receipt_ids.append(receipt_id)
            receipt_descriptions.append(f"#{receipt_id} | {company_name} | {issue_date}")

        if locked_receipts:
            locked_text = "\n".join(locked_receipts)
            self._show_error(f"Nie mozna usunac zablokowanych rachunkow:\n{locked_text}")
            return

        listed_receipts = "\n".join(receipt_descriptions[:8])
        if len(receipt_descriptions) > 8:
            listed_receipts += f"\n... oraz {len(receipt_descriptions) - 8} kolejnych"
        title = "Usun rachunek" if len(receipt_ids) == 1 else "Usun rachunki"
        message = (
            f"Czy na pewno usunac rachunek:\n{listed_receipts}"
            if len(receipt_ids) == 1
            else f"Czy na pewno usunac {len(receipt_ids)} rachunki:\n{listed_receipts}"
        )
        confirm = QMessageBox.question(
            self,
            title,
            message,
        )
        if confirm != QMessageBox.Yes:
            return

        for receipt_id in receipt_ids:
            try:
                self.service.delete_receipt(receipt_id)
            except ValueError as exc:
                self._show_error(str(exc))
                return

        self.refresh_receipts()
        self.refresh_callback()
        self.reset_form()
        self.status_label.setStyleSheet("color: #006400;")
        self.status_label.setText("Rachunek usuniety." if len(receipt_ids) == 1 else "Rachunki usuniete.")

    def _apply_selected_client(self) -> None:
        client_id = self.client_select.currentData()
        if client_id in self.clients_cache:
            company_name, nip = self.clients_cache[client_id]
            self.company_name_input.setText(company_name)
            self.nip_input.setText(nip)
        elif client_id != -1:
            self.company_name_input.clear()
            self.nip_input.clear()


class ClientsEditor(QWidget):
    def __init__(self, service: DocumentService, refresh_callback) -> None:
        super().__init__()
        self.service = service
        self.refresh_callback = refresh_callback
        self.current_client_id: int | None = None
        self.current_settlement_type_name: str | None = None

        layout = QHBoxLayout(self)
        layout.addWidget(self._build_form_panel(), 2)
        layout.addWidget(self._build_list_panel(), 3)
        self.refresh_clients()

    def _build_form_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        actions = QHBoxLayout()
        self.new_button = QPushButton("Nowy klient")
        self.save_button = QPushButton("Zapisz klienta")
        self.delete_button = QPushButton("Usun klienta")
        actions.addWidget(self.new_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.delete_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        group = QGroupBox("Klient")
        form = QFormLayout(group)
        self.client_name_input = QLineEdit()
        self.client_nip_input = QLineEdit()
        self.client_settlement_type_input = QComboBox()
        form.addRow("Nazwa klienta", self.client_name_input)
        form.addRow("NIP", self.client_nip_input)
        form.addRow("Typ rozliczenia", self.client_settlement_type_input)
        layout.addWidget(group)

        settlement_group = QGroupBox("Typy rozliczenia")
        settlement_layout = QVBoxLayout(settlement_group)
        settlement_form = QFormLayout()
        self.settlement_type_name_input = QLineEdit()
        self.settlement_type_color_input = QLineEdit()
        self.settlement_type_color_input.setReadOnly(True)
        self.settlement_type_color_preview = QLabel()
        self.settlement_type_color_preview.setFixedSize(72, 28)
        self.settlement_type_color_preview.setAlignment(Qt.AlignCenter)
        self.choose_settlement_type_color_button = QPushButton("Wybierz kolor")
        color_row = QWidget()
        color_row_layout = QHBoxLayout(color_row)
        color_row_layout.setContentsMargins(0, 0, 0, 0)
        color_row_layout.addWidget(self.settlement_type_color_preview)
        color_row_layout.addWidget(self.settlement_type_color_input)
        color_row_layout.addWidget(self.choose_settlement_type_color_button)
        settlement_form.addRow("Nazwa typu", self.settlement_type_name_input)
        settlement_form.addRow("Kolor", color_row)
        settlement_layout.addLayout(settlement_form)

        settlement_actions = QHBoxLayout()
        self.new_settlement_type_button = QPushButton("Nowy typ")
        self.save_settlement_type_button = QPushButton("Zapisz typ")
        self.delete_settlement_type_button = QPushButton("Usun typ")
        settlement_actions.addWidget(self.new_settlement_type_button)
        settlement_actions.addWidget(self.save_settlement_type_button)
        settlement_actions.addWidget(self.delete_settlement_type_button)
        settlement_layout.addLayout(settlement_actions)

        self.settlement_types_table = QTableWidget(0, 2)
        self.settlement_types_table.setHorizontalHeaderLabels(["Typ", "Kolor"])
        self.settlement_types_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.settlement_types_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.settlement_types_table.horizontalHeader().setStretchLastSection(True)
        self.settlement_types_table.itemSelectionChanged.connect(self.load_selected_settlement_type)
        settlement_layout.addWidget(self.settlement_types_table)
        layout.addWidget(settlement_group)

        self.client_status_label = QLabel()
        self.client_status_label.setStyleSheet("color: #8b0000;")
        layout.addWidget(self.client_status_label)

        self.settlement_types_status_label = QLabel()
        self.settlement_types_status_label.setStyleSheet("color: #8b0000;")
        layout.addWidget(self.settlement_types_status_label)
        layout.addStretch(1)

        self.new_button.clicked.connect(self.reset_form)
        self.save_button.clicked.connect(self.save_client)
        self.delete_button.clicked.connect(self.delete_client)
        self.new_settlement_type_button.clicked.connect(self.reset_settlement_type_form)
        self.save_settlement_type_button.clicked.connect(self.save_settlement_type)
        self.delete_settlement_type_button.clicked.connect(self.delete_settlement_type)
        self.choose_settlement_type_color_button.clicked.connect(self.choose_settlement_type_color)
        self._set_settlement_type_color(self._default_settlement_type_color())
        return container

    def _build_list_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Baza klientow"))
        self.clients_search_input = QLineEdit()
        self.clients_search_input.setPlaceholderText("Szukaj po nazwie klienta lub NIP")
        self.clients_search_input.textChanged.connect(self.refresh_clients)
        layout.addWidget(self.clients_search_input)
        self.clients_table = QTableWidget(0, 4)
        self.clients_table.setHorizontalHeaderLabels(["ID", "Nazwa klienta", "NIP", "Typ rozliczenia"])
        self.clients_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.clients_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.clients_table.horizontalHeader().setStretchLastSection(True)
        self.clients_table.itemSelectionChanged.connect(self.load_selected_client)
        layout.addWidget(self.clients_table)
        return container

    def refresh_clients(self) -> None:
        settlement_type_configs = self.service.list_settlement_type_configs()
        self._refresh_settlement_type_controls(settlement_type_configs)
        clients = self.service.list_clients()
        color_by_type = {
            config.settlement_type: config.color_hex
            for config in settlement_type_configs
        }
        search_text = self.clients_search_input.text().strip().lower()
        self.clients_table.setRowCount(0)
        for client in clients:
            settlement_label = settlement_type_label(client.settlement_type)
            if (
                search_text
                and search_text not in client.company_name.lower()
                and search_text not in client.nip.lower()
                and search_text not in settlement_label.lower()
            ):
                continue
            row = self.clients_table.rowCount()
            self.clients_table.insertRow(row)
            values = [str(client.id), client.company_name, client.nip, settlement_label]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, client.id)
                if column == 3:
                    item.setData(Qt.UserRole, client.settlement_type)
                self.clients_table.setItem(row, column, item)
            color_hex = color_by_type.get(client.settlement_type)
            if color_hex:
                apply_background_to_table_row(self.clients_table, row, color_hex)

    def load_selected_client(self) -> None:
        selected = self.clients_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        self.current_client_id = self.clients_table.item(row, 0).data(Qt.UserRole)
        self.client_name_input.setText(self.clients_table.item(row, 1).text())
        self.client_nip_input.setText(self.clients_table.item(row, 2).text())
        settlement_type = self.clients_table.item(row, 3).data(Qt.UserRole)
        settlement_index = self.client_settlement_type_input.findData(settlement_type)
        self.client_settlement_type_input.setCurrentIndex(settlement_index if settlement_index >= 0 else 0)
        self.client_status_label.clear()

    def save_client(self) -> None:
        try:
            self.service.save_client(
                ClientInput(
                    company_name=self.client_name_input.text(),
                    nip=self.client_nip_input.text(),
                    settlement_type=self.client_settlement_type_input.currentData(),
                ),
                client_id=self.current_client_id,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Blad", str(exc))
            return

        self.refresh_clients()
        self.refresh_callback()
        self.reset_form()
        self.client_status_label.setStyleSheet("color: #006400;")
        self.client_status_label.setText("Klient zapisany.")

    def delete_client(self) -> None:
        if self.current_client_id is None:
            QMessageBox.warning(self, "Blad", "Wybierz klienta do usuniecia.")
            return
        confirm = QMessageBox.question(self, "Usun klienta", "Czy na pewno usunac wybranego klienta?")
        if confirm != QMessageBox.Yes:
            return
        try:
            self.service.delete_client(self.current_client_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Blad", str(exc))
            return

        self.refresh_clients()
        self.refresh_callback()
        self.reset_form()
        self.client_status_label.setStyleSheet("color: #006400;")
        self.client_status_label.setText("Klient usuniety.")

    def reset_form(self) -> None:
        self.current_client_id = None
        self.client_name_input.clear()
        self.client_nip_input.clear()
        if self.client_settlement_type_input.count() > 0:
            self.client_settlement_type_input.setCurrentIndex(0)
        self.clients_table.clearSelection()
        self.client_status_label.clear()

    def _default_settlement_type_color(self) -> str:
        return DEFAULT_SETTLEMENT_TYPE_COLORS.get("inne", next(iter(DEFAULT_SETTLEMENT_TYPE_COLORS.values()), "#ECECEC"))

    def _set_settlement_type_color(self, color_hex: str) -> None:
        self.settlement_type_color_input.setText(color_hex)
        self.settlement_type_color_preview.setStyleSheet(
            f"background-color: {color_hex}; border: 1px solid #9ca3af; border-radius: 4px;"
        )

    def _refresh_settlement_type_controls(self, configs) -> None:
        current_client_type = self.client_settlement_type_input.currentData()
        current_type_name = self.current_settlement_type_name
        type_names = [config.settlement_type for config in configs]

        self.client_settlement_type_input.blockSignals(True)
        self.client_settlement_type_input.clear()
        for config in configs:
            self.client_settlement_type_input.addItem(
                settlement_type_label(config.settlement_type),
                config.settlement_type,
            )
        self.client_settlement_type_input.setEnabled(bool(configs))
        if configs:
            if current_client_type in type_names:
                self.client_settlement_type_input.setCurrentIndex(
                    self.client_settlement_type_input.findData(current_client_type)
                )
            else:
                self.client_settlement_type_input.setCurrentIndex(0)
        self.client_settlement_type_input.blockSignals(False)

        self.settlement_types_table.blockSignals(True)
        self.settlement_types_table.setRowCount(0)
        for config in configs:
            row = self.settlement_types_table.rowCount()
            self.settlement_types_table.insertRow(row)
            type_item = QTableWidgetItem(settlement_type_label(config.settlement_type))
            type_item.setData(Qt.UserRole, config.settlement_type)
            color_item = QTableWidgetItem(config.color_hex)
            self.settlement_types_table.setItem(row, 0, type_item)
            self.settlement_types_table.setItem(row, 1, color_item)
            apply_background_to_table_row(self.settlement_types_table, row, config.color_hex)
        self.settlement_types_table.blockSignals(False)

        if current_type_name in type_names:
            for row in range(self.settlement_types_table.rowCount()):
                item = self.settlement_types_table.item(row, 0)
                if item is not None and item.data(Qt.UserRole) == current_type_name:
                    self.settlement_types_table.selectRow(row)
                    self.load_selected_settlement_type()
                    break
        elif self.current_settlement_type_name is not None:
            self.reset_settlement_type_form(clear_selection=True)

    def load_selected_settlement_type(self) -> None:
        selected = self.settlement_types_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        type_item = self.settlement_types_table.item(row, 0)
        color_item = self.settlement_types_table.item(row, 1)
        if type_item is None or color_item is None:
            return
        self.current_settlement_type_name = type_item.data(Qt.UserRole)
        self.settlement_type_name_input.setText(self.current_settlement_type_name)
        self._set_settlement_type_color(color_item.text())
        self.settlement_types_status_label.clear()

    def reset_settlement_type_form(self, clear_selection: bool = True) -> None:
        self.current_settlement_type_name = None
        self.settlement_type_name_input.clear()
        self._set_settlement_type_color(self._default_settlement_type_color())
        if clear_selection:
            self.settlement_types_table.clearSelection()
        self.settlement_types_status_label.clear()

    def choose_settlement_type_color(self) -> None:
        current_color = QColor(self.settlement_type_color_input.text())
        if not current_color.isValid():
            current_color = QColor(self._default_settlement_type_color())
        selected_color = QColorDialog.getColor(current_color, self, "Wybierz kolor typu rozliczenia")
        if not selected_color.isValid():
            return
        self._set_settlement_type_color(selected_color.name().upper())

    def save_settlement_type(self) -> None:
        try:
            saved_config = self.service.save_settlement_type_config(
                SettlementTypeConfigInput(
                    settlement_type=self.settlement_type_name_input.text(),
                    color_hex=self.settlement_type_color_input.text(),
                    original_settlement_type=self.current_settlement_type_name,
                )
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Blad", str(exc))
            return

        self.current_settlement_type_name = saved_config.settlement_type
        self.refresh_callback()
        self.settlement_types_status_label.setStyleSheet("color: #006400;")
        self.settlement_types_status_label.setText("Typ rozliczenia zapisany.")

    def delete_settlement_type(self) -> None:
        if self.current_settlement_type_name is None:
            QMessageBox.warning(self, "Blad", "Wybierz typ rozliczenia do usuniecia.")
            return
        confirm = QMessageBox.question(
            self,
            "Usun typ rozliczenia",
            "Czy na pewno usunac wybrany typ rozliczenia? Klienci zostana przypisani do innego typu.",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            replacement = self.service.delete_settlement_type_config(self.current_settlement_type_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Blad", str(exc))
            return

        self.reset_settlement_type_form()
        self.refresh_callback()
        self.settlement_types_status_label.setStyleSheet("color: #006400;")
        self.settlement_types_status_label.setText(
            f"Typ rozliczenia usuniety. Klienci przypisani do: {settlement_type_label(replacement)}."
        )


class ProductsEditor(QWidget):
    def __init__(self, service: DocumentService, refresh_callback) -> None:
        super().__init__()
        self.service = service
        self.refresh_callback = refresh_callback
        self.current_product_id: int | None = None

        layout = QHBoxLayout(self)
        layout.addWidget(self._build_form_panel(), 2)
        layout.addWidget(self._build_list_panel(), 3)
        self.refresh_products()

    def _build_form_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        group = QGroupBox("Towar")
        form = QFormLayout(group)
        self.product_name_input = QLineEdit()
        form.addRow("Nazwa towaru", self.product_name_input)
        layout.addWidget(group)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #8b0000;")
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.new_button = QPushButton("Nowy towar")
        self.save_button = QPushButton("Zapisz towar")
        self.delete_button = QPushButton("Usun towar")
        actions.addWidget(self.new_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        self.new_button.clicked.connect(self.reset_form)
        self.save_button.clicked.connect(self.save_product)
        self.delete_button.clicked.connect(self.delete_product)
        return container

    def _build_list_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Baza towarow"))
        self.products_table = QTableWidget(0, 2)
        self.products_table.setHorizontalHeaderLabels(["ID", "Nazwa towaru"])
        self.products_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.products_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.products_table.horizontalHeader().setStretchLastSection(True)
        self.products_table.itemSelectionChanged.connect(self.load_selected_product)
        layout.addWidget(self.products_table)
        return container

    def refresh_products(self) -> None:
        products = self.service.list_products()
        self.products_table.setRowCount(0)
        for product in products:
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            values = [str(product.id), product.name]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, product.id)
                self.products_table.setItem(row, column, item)

    def load_selected_product(self) -> None:
        selected = self.products_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        self.current_product_id = self.products_table.item(row, 0).data(Qt.UserRole)
        self.product_name_input.setText(self.products_table.item(row, 1).text())
        self.status_label.clear()

    def save_product(self) -> None:
        try:
            self.service.save_product(ProductInput(name=self.product_name_input.text()), product_id=self.current_product_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Blad", str(exc))
            return

        self.refresh_products()
        self.refresh_callback()
        self.reset_form()
        self.status_label.setStyleSheet("color: #006400;")
        self.status_label.setText("Towar zapisany.")

    def delete_product(self) -> None:
        if self.current_product_id is None:
            QMessageBox.warning(self, "Blad", "Wybierz towar do usuniecia.")
            return
        confirm = QMessageBox.question(self, "Usun towar", "Czy na pewno usunac wybrany towar?")
        if confirm != QMessageBox.Yes:
            return
        try:
            self.service.delete_product(self.current_product_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Blad", str(exc))
            return

        self.refresh_products()
        self.refresh_callback()
        self.reset_form()
        self.status_label.setStyleSheet("color: #006400;")
        self.status_label.setText("Towar usuniety.")

    def reset_form(self) -> None:
        self.current_product_id = None
        self.product_name_input.clear()
        self.products_table.clearSelection()
        self.status_label.clear()


class FinalInvoiceEditor(QWidget):
    def __init__(self, service: DocumentService) -> None:
        super().__init__()
        self.service = service
        self.clients_cache: dict[int, tuple[str, str]] = {}
        self.client_color_map_by_nip: dict[str, str] = {}
        self.current_final_invoice_id: int | None = None
        self.final_invoices_cache: list[FinalInvoice] = []
        layout = QHBoxLayout(self)
        layout.addWidget(self._build_create_panel(), 3)
        layout.addWidget(self._build_list_panel(), 2)
        self.refresh()

    def _build_create_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        header_group = QGroupBox("Nowa faktura koncowa")
        form = QFormLayout(header_group)
        self.client_select = QComboBox()
        self.client_select.setEditable(True)
        self.client_select.setInsertPolicy(QComboBox.NoInsert)
        self.client_select.setPlaceholderText("Szukaj po nazwie klienta lub NIP")
        client_completer = self.client_select.completer()
        if client_completer is not None:
            client_completer.setCaseSensitivity(Qt.CaseInsensitive)
            client_completer.setFilterMode(Qt.MatchContains)
            client_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.client_select.currentIndexChanged.connect(self._on_client_changed)
        self.client_select.editTextChanged.connect(self._on_client_text_changed)
        self.company_name_input = QLineEdit()
        self.company_name_input.setReadOnly(True)
        self.nip_input = QLineEdit()
        self.nip_input.setReadOnly(True)
        self.issue_date_input = QDateEdit()
        self.issue_date_input.setCalendarPopup(True)
        self.issue_date_input.setDate(date.today())
        form.addRow("Klient", self.client_select)
        form.addRow("Nazwa firmy", self.company_name_input)
        form.addRow("NIP", self.nip_input)
        form.addRow("Data wystawienia", self.issue_date_input)
        layout.addWidget(header_group)

        layout.addWidget(QLabel("Dostepne rachunki"))
        self.available_receipts_list = QListWidget()
        layout.addWidget(self.available_receipts_list)

        self.total_label = QLabel(f"Razem: {decimal_text(Decimal('0.00'))}")
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #8b0000;")
        self.create_button = QPushButton("Utworz fakture koncowa")
        layout.addWidget(self.total_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.create_button)

        self.available_receipts_list.itemChanged.connect(self._update_total)
        self.create_button.clicked.connect(self.create_final_invoice)
        return container

    def _build_list_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(QLabel("Istniejace faktury koncowe"))
        self.final_invoices_search_input = QLineEdit()
        self.final_invoices_search_input.setPlaceholderText("Szukaj po nazwie klienta lub NIP")
        self.final_invoices_search_input.textChanged.connect(self._apply_final_invoice_filter)
        layout.addWidget(self.final_invoices_search_input)
        self.final_invoices_table = QTableWidget(0, 5)
        self.final_invoices_table.setHorizontalHeaderLabels(["ID", "Firma", "NIP", "Data", "Razem"])
        self.final_invoices_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.final_invoices_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.final_invoices_table.horizontalHeader().setStretchLastSection(True)
        self.final_invoices_table.setSortingEnabled(True)
        self.final_invoices_table.itemSelectionChanged.connect(self._on_final_invoice_selection_changed)
        self.final_invoices_table.itemDoubleClicked.connect(self.preview_selected_final_invoice)
        layout.addWidget(self.final_invoices_table)
        self.preview_button = QPushButton("Podglad PDF / Drukuj")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self.preview_selected_final_invoice)
        layout.addWidget(self.preview_button)
        return container

    def refresh(self) -> None:
        self.client_color_map_by_nip = self.service.get_client_color_map_by_nip()
        self._refresh_clients()
        self._refresh_available_receipts()
        self._refresh_final_invoices()
        self._update_total()

    def _refresh_clients(self) -> None:
        clients = self.service.list_clients()
        current_client_id = self.client_select.currentData()
        self.client_select.blockSignals(True)
        self.client_select.clear()
        self.clients_cache = {}

        if not clients:
            self.client_select.addItem("Brak klientow - dodaj klienta w osobnej zakladce", None)
            self.client_select.setEnabled(False)
            self.company_name_input.clear()
            self.nip_input.clear()
        else:
            self.client_select.setEnabled(True)
            for client in clients:
                label = f"{client.company_name} | {client.nip}"
                self.client_select.addItem(label, client.id)
                self.clients_cache[client.id] = (client.company_name, client.nip)

            if current_client_id in self.clients_cache:
                self.client_select.setCurrentIndex(self.client_select.findData(current_client_id))
            else:
                self.client_select.setCurrentIndex(0)
            self._apply_selected_client()

        self.client_select.blockSignals(False)

    def _refresh_available_receipts(self) -> None:
        self.available_receipts_list.blockSignals(True)
        self.available_receipts_list.clear()
        selected_company = self.company_name_input.text().strip()
        selected_nip = self.nip_input.text().strip()
        for receipt in self.service.list_available_receipts():
            if selected_company and receipt.company_name != selected_company:
                continue
            if selected_nip and receipt.nip != selected_nip:
                continue
            item = QListWidgetItem(
                f"{receipt.company_name} | {receipt.nip} | {receipt.issue_date.isoformat()} | {decimal_text(receipt.total)}"
            )
            item.setData(Qt.UserRole, {"id": receipt.id, "total": receipt.total})
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            color_hex = self.client_color_map_by_nip.get(receipt.nip)
            if color_hex:
                apply_background_to_list_item(item, color_hex)
            self.available_receipts_list.addItem(item)
        self.available_receipts_list.blockSignals(False)

    def _refresh_final_invoices(self) -> None:
        self.final_invoices_cache = self.service.list_final_invoices()
        self._apply_final_invoice_filter()

    def _apply_final_invoice_filter(self) -> None:
        search_text = self.final_invoices_search_input.text().strip().lower()
        self.final_invoices_table.setSortingEnabled(False)
        self.final_invoices_table.setRowCount(0)

        for final_invoice in self.final_invoices_cache:
            if search_text and search_text not in final_invoice.company_name.lower() and search_text not in final_invoice.nip.lower():
                continue
            row = self.final_invoices_table.rowCount()
            self.final_invoices_table.insertRow(row)
            values = [
                str(final_invoice.id),
                final_invoice.company_name,
                final_invoice.nip,
                final_invoice.issue_date.isoformat(),
                decimal_text(final_invoice.total),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, final_invoice.id)
                self.final_invoices_table.setItem(row, column, item)

            color_hex = self.client_color_map_by_nip.get(final_invoice.nip)
            if color_hex:
                apply_background_to_table_row(self.final_invoices_table, row, color_hex)

            self.final_invoices_table.setSortingEnabled(True)
        self.current_final_invoice_id = None
        self.preview_button.setEnabled(False)

    def _update_total(self) -> None:
        total = Decimal("0.00")
        for index in range(self.available_receipts_list.count()):
            item = self.available_receipts_list.item(index)
            if item.checkState() == Qt.Checked:
                total += item.data(Qt.UserRole)["total"]
        self.total_label.setText(f"Razem: {decimal_text(total)}")

    def _on_client_changed(self) -> None:
        self._apply_selected_client()
        self._refresh_available_receipts()
        self._update_total()

    def _on_client_text_changed(self, text: str) -> None:
        normalized_text = text.strip().lower()
        if not normalized_text:
            self.company_name_input.clear()
            self.nip_input.clear()
            self._refresh_available_receipts()
            self._update_total()
            return

        matched_index = -1
        for index in range(self.client_select.count()):
            label = self.client_select.itemText(index).strip().lower()
            if label == normalized_text:
                matched_index = index
                break

        if matched_index >= 0 and matched_index != self.client_select.currentIndex():
            self.client_select.setCurrentIndex(matched_index)
            return

        current_client_id = self.client_select.currentData()
        current_label = self.client_select.currentText().strip().lower()
        if matched_index < 0 or normalized_text != current_label or current_client_id not in self.clients_cache:
            self.company_name_input.clear()
            self.nip_input.clear()
            self._refresh_available_receipts()
            self._update_total()

    def create_final_invoice(self) -> None:
        receipt_ids: list[int] = []
        for index in range(self.available_receipts_list.count()):
            item = self.available_receipts_list.item(index)
            if item.checkState() == Qt.Checked:
                receipt_ids.append(item.data(Qt.UserRole)["id"])

        try:
            selected_client_id = self.client_select.currentData()
            if selected_client_id not in self.clients_cache:
                raise ValueError("Wybierz klienta z listy, korzystajac z wyszukiwarki pola Klient.")
            payload = FinalInvoiceInput(
                company_name=self.company_name_input.text(),
                nip=self.nip_input.text(),
                issue_date=self.issue_date_input.date().toPython(),
                receipt_ids=receipt_ids,
            )
            self.service.create_final_invoice(payload)
        except ValueError as exc:
            QMessageBox.warning(self, "Blad", str(exc))
            return

        self.company_name_input.clear()
        self.nip_input.clear()
        self.issue_date_input.setDate(date.today())
        self.refresh()
        self.status_label.setStyleSheet("color: #006400;")
        self.status_label.setText("Faktura koncowa utworzona.")

    def preview_selected_final_invoice(self, *_args) -> None:
        if self.current_final_invoice_id is None:
            QMessageBox.warning(self, "Blad", "Wybierz fakture koncowa do podgladu.")
            return

        final_invoice = self.service.get_final_invoice(self.current_final_invoice_id)
        if final_invoice is None:
            QMessageBox.warning(self, "Blad", "Nie znaleziono wybranej faktury koncowej.")
            return

        dialog = FinalInvoicePreviewDialog(final_invoice, self)
        dialog.exec()

    def _on_final_invoice_selection_changed(self) -> None:
        selected = self.final_invoices_table.selectedItems()
        if not selected:
            self.current_final_invoice_id = None
            self.preview_button.setEnabled(False)
            return
        row = selected[0].row()
        self.current_final_invoice_id = self.final_invoices_table.item(row, 0).data(Qt.UserRole)
        self.preview_button.setEnabled(self.current_final_invoice_id is not None)

    def _apply_selected_client(self) -> None:
        client_id = self.client_select.currentData()
        if client_id in self.clients_cache:
            company_name, nip = self.clients_cache[client_id]
            self.company_name_input.setText(company_name)
            self.nip_input.setText(nip)
        else:
            self.company_name_input.clear()
            self.nip_input.clear()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths = get_app_paths()
        self.service = DocumentService(self.paths)
        self.setWindowTitle("Fakturownik")
        self.setWindowIcon(load_brand_icon())
        self.resize(1400, 900)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.admin_button = QToolButton()
        self.admin_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.admin_button.setToolTip("Administracja")
        self.admin_button.setCheckable(True)
        self.admin_button.setAutoRaise(True)

        self.tabs = QTabWidget()
        self.receipt_editor = ReceiptEditor(self.service, refresh_callback=self.refresh_related_views)
        self.final_invoice_editor = FinalInvoiceEditor(self.service)
        self.clients_editor = ClientsEditor(self.service, refresh_callback=self.refresh_related_views)
        self.products_editor = ProductsEditor(self.service, refresh_callback=self.refresh_related_views)
        self.tabs.addTab(self.clients_editor, "Klienci")
        self.tabs.addTab(self.products_editor, "Towary")
        self.tabs.addTab(self.receipt_editor, "Rachunki")
        self.tabs.addTab(self.final_invoice_editor, "Faktury koncowe")
        self.tabs.setCornerWidget(self.admin_button, Qt.TopRightCorner)
        layout.addWidget(self.tabs)

        self.receipt_editor.refresh_clients()
        self.receipt_editor.refresh_products()

        self.setCentralWidget(central)
        self.admin_dock = self._build_admin_dock()
        self.addDockWidget(Qt.RightDockWidgetArea, self.admin_dock)
        self.admin_dock.hide()

        self.admin_button.toggled.connect(self._toggle_admin_panel)
        self.admin_dock.visibilityChanged.connect(self._sync_admin_button_state)

    def _build_admin_dock(self) -> QDockWidget:
        dock = QDockWidget("Administracja", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetClosable)

        content = QWidget()
        layout = QVBoxLayout(content)
        info_label = QLabel("Narzędzia administracyjne")
        backup_button = QPushButton("Export backup")
        restore_button = QPushButton("Import backup")
        data_path_label = QLabel(f"Katalog danych:\n{self.paths.base_dir}")
        data_path_label.setWordWrap(True)

        layout.addWidget(info_label)
        layout.addWidget(backup_button)
        layout.addWidget(restore_button)
        layout.addWidget(data_path_label)
        layout.addStretch(1)

        dock.setWidget(content)

        backup_button.clicked.connect(self.export_backup)
        restore_button.clicked.connect(self.import_backup)
        return dock

    def _toggle_admin_panel(self, visible: bool) -> None:
        self.admin_dock.setVisible(visible)

    def _sync_admin_button_state(self, visible: bool) -> None:
        self.admin_button.blockSignals(True)
        self.admin_button.setChecked(visible)
        self.admin_button.blockSignals(False)

    def refresh_related_views(self) -> None:
        self.clients_editor.refresh_clients()
        self.products_editor.refresh_products()
        self.receipt_editor.refresh_clients()
        self.receipt_editor.refresh_products()
        self.receipt_editor.refresh_receipts()
        self.final_invoice_editor.refresh()

    def export_backup(self) -> None:
        default_path = self.paths.backup_dir / f"backup_{date.today().isoformat()}.zip"
        file_name, _ = QFileDialog.getSaveFileName(self, "Zapisz backup", str(default_path), "ZIP (*.zip)")
        if not file_name:
            return
        export_backup(Path(file_name), self.paths)
        QMessageBox.information(self, "Backup", f"Backup zapisany do:\n{file_name}")

    def import_backup(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Wczytaj backup", str(self.paths.backup_dir), "ZIP (*.zip)")
        if not file_name:
            return
        confirm = QMessageBox.question(
            self,
            "Import backupu",
            "Import nadpisze aktualna baze i zalaczniki. Kontynuowac?",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            import_backup(Path(file_name), self.paths)
            init_database()
        except ValueError as exc:
            QMessageBox.warning(self, "Blad importu", str(exc))
            return
        self.refresh_related_views()
        self.products_editor.reset_form()
        self.receipt_editor.reset_form()
        QMessageBox.information(self, "Import", "Backup zostal odtworzony.")


def run() -> int:
    init_database()
    app = QApplication(sys.argv)
    app.setWindowIcon(load_brand_icon())
    apply_dark_theme(app)
    window = MainWindow()
    window.showMaximized()
    return app.exec()