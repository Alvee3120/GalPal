"""
Invoices: one normalized invoice built from an order's own stored snapshot (never today's prices, zones or coupons),
used by every surface — the storefront/customer view, the staff view, print and the PDF.

    build_invoice(order, request=None) -> dict   the invoice data (JSON-ready; QR + barcode included as SVG)
    render_invoice_pdf(invoice) -> bytes          the same invoice as a real A4 PDF (text is text; codes are vectors)

* Invoice number: derived from the order number (GP-260923-SKJ3 -> INV-260923-SKJ3). The order number is unique and
  never changes, so the invoice number is stable across reprints, refreshes and PDFs without storing anything new.
* Parcel ID: the order's saved `consignment_id`, entered by Admin/CCE (services.set_parcel_id). It is the ONLY source:
  the QR code and barcode are drawn from it on every render and never stored. Until one is saved the invoice says so;
  nothing is made up, and no QR/barcode is drawn.
* Paid / due: from the payment record (amount received minus refunds); an order without one has paid nothing.
* The PDF shows money as "BDT 1,870" — the standard PDF fonts have no Taka sign (৳); the HTML view uses ৳.
"""
import logging
import re
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.core.files.storage import default_storage
from django.utils import timezone

from apps.site_settings.models import INVOICE_LAYOUT
from apps.site_settings.services import get_site_settings

logger = logging.getLogger(__name__)
ZERO = Decimal("0.00")

MM = 72 / 25.4  # points per millimetre


class Layout:
    """
    The invoice print layout: the admin's saved Site Settings (INVOICE_LAYOUT — content width %, page padding mm,
    text size pt, section spacing mm, logo / QR / barcode mm), or the standard design's defaults. Every other size is
    derived in the standard design's proportions: type and cell padding from the 9pt text size, gaps between sections
    from the 4mm section spacing. The web/print CSS derives the SAME sizes from the same values (frontend globals.css,
    "Invoice" section), so preview, print, PDF and reprint match. Nothing is ever scaled to fit the content.
    """

    STANDARD_TEXT_PT, STANDARD_SPACING_MM = 9, 4
    STANDARD_BAR_WIDTH_MM, STANDARD_BAR_HEIGHT_MM = 0.33, 16

    def __init__(self, values=None):
        values = values or {}
        for field, (default, low, high, _unit) in INVOICE_LAYOUT.items():
            name = field.removeprefix("invoice_")
            try:
                value = float(values.get(name, default))
            except (TypeError, ValueError):
                value = float(default)
            setattr(self, name, min(max(value, low), high))

    def as_dict(self):
        return {field.removeprefix("invoice_"): getattr(self, field.removeprefix("invoice_")) for field in INVOICE_LAYOUT}

    def pt(self, standard_pt):
        """A type size / cell padding, in points, from its size in the standard 9pt design."""
        return self.text_size * standard_pt / self.STANDARD_TEXT_PT

    def gap(self, standard_mm):
        """A gap between sections, in points, from its size in the standard 4mm-spacing design."""
        return self.section_spacing * standard_mm / self.STANDARD_SPACING_MM * MM

    @property
    def bar_width_mm(self):
        """Code 128 module width: scales with the barcode height, so the barcode keeps its proportions."""
        return self.STANDARD_BAR_WIDTH_MM * self.barcode_height / self.STANDARD_BAR_HEIGHT_MM


def invoice_layout(site):
    """The saved print layout from Site Settings (a cached row without the fields falls back to the defaults)."""
    return Layout({f.removeprefix("invoice_"): getattr(site, f, None) for f in INVOICE_LAYOUT if getattr(site, f, None) is not None})


LAYOUT_KEYS = tuple(field.removeprefix("invoice_") for field in INVOICE_LAYOUT)


def clean_layout_overrides(overrides, global_layout):
    """
    A per-invoice override set as it's stored: known keys only, in range (else a field error), and without values
    equal to the global layout — only what really differs is kept, so every other value keeps following the global
    Invoice Settings (and so does a value set back to the global one).
    """
    from rest_framework.exceptions import ValidationError

    cleaned, errors = {}, {}
    base = global_layout.as_dict()
    for key, value in (overrides or {}).items():
        if key not in LAYOUT_KEYS:
            errors[key] = ["Unknown layout setting."]
            continue
        _default, low, high, unit = INVOICE_LAYOUT[f"invoice_{key}"]
        try:
            number = round(float(value), 1)
        except (TypeError, ValueError):
            errors[key] = ["Enter a number."]
            continue
        if not low <= number <= high:
            errors[key] = [f"Must be between {low} and {high} {unit}."]
        elif number != base[key]:
            cleaned[key] = number
    if errors:
        raise ValidationError(errors)
    return cleaned


def resolve_layout(order, site=None):
    """
    The layout this order's invoice is printed with: the global Invoice Settings, with this invoice's own overrides
    (Order.invoice_layout) on top — {**global, **overrides}. The single resolver behind the invoice data (preview,
    print, reprint) and the PDF. Returns (resolved, global, overrides).
    """
    base = invoice_layout(site or get_site_settings())
    overrides = {k: v for k, v in (order.invoice_layout or {}).items() if k in LAYOUT_KEYS}
    return Layout({**base.as_dict(), **overrides}), base, overrides


# --- data --------------------------------------------------------------------------------------------------------------


def invoice_number(order):
    number = order.number or ""
    return f"INV-{number[3:]}" if number.startswith("GP-") else f"INV-{number}"


def parcel_id(order):
    return (order.consignment_id or "").strip()


def _url(field_or_path, request):
    name = getattr(field_or_path, "name", field_or_path)
    if not name:
        return None
    try:
        url = default_storage.url(name)
    except Exception:  # noqa: BLE001 - a missing file must not break the invoice
        return None
    return request.build_absolute_uri(url) if request is not None and url.startswith("/") else url


def _paid(order):
    payment = getattr(order, "payment", None)
    if payment is None:
        return ZERO
    from apps.payments.services import net_received  # lazy: payments imports orders

    return max(net_received(payment), ZERO)


def parcel_codes(order):
    """{"qr_svg", "barcode_svg"} for the order's saved Parcel ID, or None when it has none (order details, invoice)."""
    qr_svg, barcode_svg = _codes_svg(parcel_id(order))
    return {"qr_svg": qr_svg, "barcode_svg": barcode_svg} if qr_svg else None


def _codes_svg(value):
    """(qr_svg, barcode_svg) for `value` — real, vector QR (error level M) and Code 128 (full ASCII) codes."""
    if not value:
        return None, None
    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode import createBarcodeDrawing

    std = Layout()  # drawn at the standard size; the invoice CSS resizes them to the saved layout, keeping proportions
    qr = createBarcodeDrawing("QR", value=value, barLevel="M", width=std.qr_size * MM, height=std.qr_size * MM)
    barcode = createBarcodeDrawing(
        "Code128", value=value, barHeight=std.barcode_height * MM, barWidth=std.bar_width_mm * MM, humanReadable=False, quiet=True,
    )
    return _inline_svg(renderSVG.drawToString(qr), "qr"), _inline_svg(renderSVG.drawToString(barcode), "barcode")


def _inline_svg(svg, prefix):
    """ReportLab's standalone SVG, made safe to drop into a page: no XML prolog/DOCTYPE, no placeholder
    <title>/<desc>, a clip-path id that can't collide with the other code's on the same page, and its size in points
    (ReportLab writes unitless numbers, which a browser would read as px) so it prints at the same size as the PDF."""
    svg = svg[svg.index("<svg"):]
    svg = re.sub(r'^<svg width="([\d.]+)" height="([\d.]+)"', r'<svg width="\1pt" height="\2pt"', svg)
    svg = re.sub(r"\s*<title>.*?</title>|\s*<desc>.*?</desc>", "", svg, flags=re.S)
    return svg.replace('id="clip"', f'id="{prefix}-clip"').replace("url(#clip)", f"url(#{prefix}-clip)")


def _plain(value):
    """Decimals as exact strings ("1067.50"), like every other money field in the API; recurses into lists/dicts."""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def invoice_data(order, request=None):
    """build_invoice, JSON-ready."""
    return _plain(build_invoice(order, request))


def pdf_response(order, request=None):
    """The order's invoice as an A4 PDF download (Content-Disposition: attachment; <invoice number>.pdf)."""
    from django.http import HttpResponse

    invoice = build_invoice(order, request)
    pdf = render_invoice_pdf(invoice)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{invoice["invoice_number"]}.pdf"'
    response["Cache-Control"] = "no-store"
    return response


def build_invoice(order, request=None):
    site = get_site_settings()
    created = timezone.localtime(order.created_at)
    items = []
    product_discount = ZERO
    for item in order.items.all():
        regular = item.regular_price or item.unit_price
        discount = max((regular - item.unit_price) * item.quantity, ZERO)
        product_discount += discount
        items.append({
            "name": item.product_name,
            "variant": item.variant_label,
            "sku": item.sku,
            "image": _url(item.image, request),
            "quantity": item.quantity,
            "unit_price": regular,  # the price before any sale, per unit
            "sale_price": item.unit_price,  # what was actually charged, per unit
            "discount": discount,  # sale savings on this line
            "total": item.line_total,
        })
    paid = _paid(order)
    resolved, base_layout, overrides = resolve_layout(order, site)
    parcel = parcel_id(order)
    qr_svg, barcode_svg = _codes_svg(parcel)
    return {
        "store": {
            "name": site.site_name,
            "address": site.address,
            "phone": site.phone,
            "email": site.email,
            "currency_symbol": site.currency_symbol or "৳",
            "currency_code": site.currency_code or "BDT",
        },
        "invoice_number": invoice_number(order),
        "order_number": order.number,
        "order_id": order.id,
        "issued_at": created.isoformat(),
        "date": created.strftime("%d %b %Y"),
        "time": created.strftime("%I:%M %p"),
        "customer": {
            "name": order.customer_name,
            "phone": order.phone,
            "email": order.email,
            "address": order.address_line,
            "area": order.area,
            "city": order.district,
            "division": order.division,
            "postal_code": order.postal_code,
        },
        "items": items,
        "subtotal": order.subtotal,  # sum of line totals, at the prices charged
        "product_discount": product_discount,  # already inside the line totals (shown for information)
        "coupon_code": order.coupon_code,
        "coupon_discount": order.discount_amount,
        "delivery_charge": order.shipping_charge,
        "delivery_free_reason": order.shipping_free_reason,
        "delivery_zone": order.shipping_zone_name,
        "tax_percent": order.tax_percent,
        "tax_amount": order.tax_amount,
        "total": order.grand_total,
        "paid": paid,
        "due": max(order.grand_total - paid, ZERO),
        "payment_method": order.get_payment_method_display(),
        "payment_status": order.get_payment_status_display(),
        "parcel_id": parcel,
        "courier": order.courier_name,
        "parcel_qr_svg": qr_svg,
        "parcel_barcode_svg": barcode_svg,
        "note": order.note,
        # The print layout: global Invoice Settings + this invoice's own overrides (resolve_layout). The PDF reads
        # "layout" too, so preview, print, reprint and PDF always agree.
        "layout": resolved.as_dict(),
        "layout_global": base_layout.as_dict(),
        "layout_overrides": overrides,
    }


# --- PDF -------------------------------------------------------------------------------------------------------------------


# The backend can't read the frontend's files at runtime, so the invoice's assets are copies kept here:
# * galpal-logo.svg = an exact copy of frontend/public/assets/galpal/galpal-logo.svg (keep them identical). Its
#   "GAL PAL" wordmark is live <text> naming "SORA-Regular, SORA", which browsers don't have, so the site shows it in
#   the browser's default serif (Times New Roman). The PDF maps that font name to the PDF standard Times-Roman, so the
#   logo looks the same as on the site.
# * The website's fonts, embedded in every PDF: Montserrat 400/600/700 (the site's body font, loaded from Google Fonts
#   on the web — SIL OFL, see Montserrat-OFL.txt) and Honacu (frontend/public/font/honacu.ttf, the site's heading font).
ASSETS = Path(__file__).resolve().parent / "assets"
LOGO_SVG = ASSETS / "galpal-logo.svg"
FONTS = {
    "Montserrat": "Montserrat-Regular.ttf",
    "Montserrat-SemiBold": "Montserrat-SemiBold.ttf",
    "Montserrat-Bold": "Montserrat-Bold.ttf",
    "Honacu": "Honacu-Regular.ttf",
}


def _register_fonts():
    """Register (once) the site's fonts with ReportLab; TTFs are embedded (subset) into each PDF."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, filename in FONTS.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, str(ASSETS / filename)))
    # <b> inside a Montserrat paragraph -> SemiBold (the web invoice's bold weight, 600).
    pdfmetrics.registerFontFamily("Montserrat", normal="Montserrat", bold="Montserrat-SemiBold",
                                  italic="Montserrat", boldItalic="Montserrat-SemiBold")


def _logo_flowable(max_w):
    """The GalPal logo as a vector drawing, `max_w` wide, aspect ratio kept (svglib: SVG -> ReportLab graphics)."""
    try:
        from reportlab.graphics.shapes import Drawing
        from svglib.fonts import register_font
        from svglib.svglib import svg2rlg

        for family in ("SORA-Regular", "SORA"):  # the wordmark's font -> Times, as browsers render the site's logo
            register_font(family, rlgFontName="Times-Roman")
        logo = svg2rlg(str(LOGO_SVG))
        scale = max_w / logo.width
        drawing = Drawing(logo.width * scale, logo.height * scale)
        logo.scale(scale, scale)
        drawing.add(logo)
        drawing.hAlign = "LEFT"
        return drawing
    except Exception:  # noqa: BLE001 - still issue the invoice, but say loudly why the logo is missing
        logger.exception("Invoice PDF: couldn't load the logo from %s", LOGO_SVG)
        return None


def render_invoice_pdf(invoice):
    """
    The invoice as a real PDF (platypus flowables: text is text, codes are vectors) at its saved print layout (Layout):
    A4 width, the saved padding and content width, fixed type sizes. One page exactly as tall as the invoice when it
    fits on one A4 page (no blank space below); otherwise normal A4 pages, flowing on at the same size — never scaled.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import SimpleDocTemplate

    _register_fonts()
    layout = Layout(invoice.get("layout"))
    top, right, bottom, left = (getattr(layout, f"padding_{side}") * MM for side in ("top", "right", "bottom", "left"))
    inner = A4[0] - left - right
    width = inner * layout.content_width / 100  # centred in the padded area
    side = (inner - width) / 2
    scratch = Canvas(BytesIO())  # measuring only
    height = sum(f.wrapOn(scratch, width, A4[1])[1] for f in _invoice_story(invoice, width, layout, keep_together=False))
    fits = height <= A4[1] - top - bottom - MM  # 1mm slack for rounding
    pagesize = (A4[0], height + top + bottom + MM) if fits else A4

    buffer = BytesIO()
    # SimpleDocTemplate's frame adds 6pt padding of its own, so the margins are the padding minus that.
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize, leftMargin=left + side - 6, rightMargin=right + side - 6, topMargin=top - 6, bottomMargin=bottom - 6,
        title=f"Invoice {invoice['invoice_number']}", author=invoice["store"]["name"],
    )
    doc.build(_invoice_story(invoice, width, layout))  # fresh flowables: the measuring pass has already wrapped the first set
    return buffer.getvalue()


def _invoice_story(invoice, width, layout, keep_together=True):
    """
    The invoice's flowables at content `width`. The totals and the parcel box are kept whole across a page break;
    measuring passes keep_together=False, since KeepTogether reports an unbounded height until it's laid out.
    """
    from reportlab.graphics.barcode import createBarcodeDrawing
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

    code = invoice["store"]["currency_code"]

    def money(value):
        return f"{code} {Decimal(value):,.2f}".replace(".00", "")

    ink = colors.HexColor("#171717")
    muted = colors.HexColor("#6b6b6b")
    line = colors.HexColor("#d9d9d9")
    brand = colors.HexColor("#6b0127")
    L = layout
    base = ParagraphStyle("base", fontName="Montserrat", fontSize=L.pt(9), leading=L.pt(12), textColor=ink)
    small = ParagraphStyle("small", parent=base, fontSize=L.pt(7.5), leading=L.pt(10), textColor=muted)  # store lines, labels
    detail = ParagraphStyle("detail", parent=small, fontSize=L.pt(6.5), leading=L.pt(8.5))  # variant / SKU line
    bold = ParagraphStyle("bold", parent=base, fontName="Montserrat-SemiBold")
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    right_small = ParagraphStyle("rsmall", parent=small, alignment=TA_RIGHT)
    # Headings in the site's heading font, like the website's h1s (.custom-font).
    title = ParagraphStyle("title", parent=base, fontName="Honacu", fontSize=L.pt(20), leading=L.pt(23), textColor=brand, alignment=TA_RIGHT)
    store_style = ParagraphStyle("store", parent=bold, fontSize=L.pt(14), leading=L.pt(17))
    esc = lambda s: (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    story = []

    # Header: store (logo — its wordmark is the store name — then phone, email, address) | INVOICE + number, order, date, time
    store = invoice["store"]
    logo = _logo_flowable(L.logo_width * mm)
    left = [logo, Spacer(1, L.gap(2))] if logo else [Paragraph(esc(store["name"]), store_style)]
    for text in (store["phone"] and f"Phone: {store['phone']}", store["email"] and f"Email: {store['email']}", store["address"]):
        if text:
            left.append(Paragraph(esc(text).replace("\n", "<br/>"), small))
    meta = [
        Paragraph("INVOICE", title),
        Paragraph(f"<b>Invoice #:</b> {esc(invoice['invoice_number'])}", right),
        Paragraph(f"<b>Order #:</b> {esc(invoice['order_number'])}", right),
        Paragraph(f"<b>Date:</b> {esc(invoice['date'])}", right),
        Paragraph(f"<b>Time:</b> {esc(invoice['time'])}", right),
    ]
    header = Table([[left, meta]], colWidths=[width * 0.58, width * 0.42])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("LINEBELOW", (0, 0), (-1, 0), 1, brand), ("BOTTOMPADDING", (0, 0), (-1, 0), L.pt(6))]))
    story += [header, Spacer(1, L.gap(4))]

    # Bill to | Payment
    c = invoice["customer"]
    place = ", ".join(p for p in (c["area"], c["city"], c["division"]) if p) + (f" {c['postal_code']}" if c["postal_code"] else "")
    bill = [Paragraph("BILL TO", small), Paragraph(esc(c["name"]), bold)]
    zone = f"Delivery zone: {invoice['delivery_zone']}" if invoice["delivery_zone"] else ""
    for text in (c["phone"], c["email"], c["address"], place, zone):
        if text:
            bill.append(Paragraph(esc(text), base))
    pay = [Paragraph("PAYMENT", right_small),
           Paragraph(esc(invoice["payment_method"]), ParagraphStyle("pm", parent=bold, alignment=TA_RIGHT)),
           Paragraph(f"Status: {esc(invoice['payment_status'])}", right)]
    parties = Table([[bill, pay]], colWidths=[width * 0.6, width * 0.4])
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [parties, Spacer(1, L.gap(4))]

    # Items
    rows = [[Paragraph("<b>Product</b>", base), Paragraph("<b>Qty</b>", right), Paragraph("<b>Price</b>", right),
             Paragraph("<b>Discount</b>", right), Paragraph("<b>Total</b>", right)]]
    for item in invoice["items"]:
        name = esc(item["name"])
        details = " · ".join(esc(x) for x in (item["variant"], item["sku"] and f"SKU {item['sku']}") if x)
        rows.append([
            [Paragraph(name, base)] + ([Paragraph(details, detail)] if details else []),
            Paragraph(str(item["quantity"]), right),
            Paragraph(money(item["unit_price"]), right),
            Paragraph(money(item["discount"]) if item["discount"] else "—", right),
            Paragraph(money(item["total"]), right),
        ])
    items = Table(rows, colWidths=[width * 0.46, width * 0.08, width * 0.15, width * 0.15, width * 0.16], repeatRows=1)
    items.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ink), ("LINEBELOW", (0, 1), (-1, -1), 0.4, line),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), L.pt(3.5)), ("BOTTOMPADDING", (0, 0), (-1, -1), L.pt(3.5)),
        ("LEFTPADDING", (0, 0), (0, -1), 0), ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
    ]))
    story += [items, Spacer(1, L.gap(3))]

    # Totals
    totals = [["Subtotal", money(invoice["subtotal"])]]
    if Decimal(invoice["product_discount"]) > 0:
        totals.append(["Product discount (in prices)", f"- {money(invoice['product_discount'])}"])
    if Decimal(invoice["coupon_discount"]) > 0:
        label = f"Coupon discount ({invoice['coupon_code']})" if invoice["coupon_code"] else "Coupon discount"
        totals.append([label, f"- {money(invoice['coupon_discount'])}"])
    delivery = invoice["delivery_charge"]
    totals.append(["Delivery charge", "Free" if Decimal(delivery) == 0 else money(delivery)])
    if Decimal(invoice["tax_amount"]) > 0:
        totals.append([f"Tax ({Decimal(invoice['tax_percent']).normalize()}%)", money(invoice["tax_amount"])])
    totals.append(["TOTAL", money(invoice["total"])])
    totals.append(["Paid", money(invoice["paid"])])
    totals.append(["Due", money(invoice["due"])])
    total_row = len(totals) - 3
    summary_rows = [
        [Paragraph(f"<font name=\"Montserrat-Bold\">{esc(a)}</font>" if i == total_row else esc(a), base),
         Paragraph(f"<font name=\"Montserrat-Bold\">{esc(b)}</font>" if i == total_row else esc(b), right)]
        for i, (a, b) in enumerate(totals)
    ]
    summary = Table(summary_rows, colWidths=[width * 0.32, width * 0.18], hAlign="RIGHT")
    summary.setStyle(TableStyle([
        ("LINEABOVE", (0, total_row), (-1, total_row), 0.8, ink),
        ("TOPPADDING", (0, 0), (-1, -1), L.pt(1.5)), ("BOTTOMPADDING", (0, 0), (-1, -1), L.pt(1.5)), ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
    ]))
    story += [KeepTogether(summary) if keep_together else summary, Spacer(1, L.gap(5))]

    # Parcel: id + QR + Code 128
    parcel = invoice["parcel_id"]
    if parcel:
        qr = createBarcodeDrawing("QR", value=parcel, barLevel="M", width=L.qr_size * mm, height=L.qr_size * mm)
        barcode = createBarcodeDrawing(
            "Code128", value=parcel, barHeight=L.barcode_height * mm, barWidth=L.bar_width_mm * mm, humanReadable=True, quiet=True,
        )
        label = [Paragraph("PARCEL ID", small),
                 Paragraph(f"<b>{esc(parcel)}</b>", ParagraphStyle("pid", parent=bold, fontSize=L.pt(10.5), leading=L.pt(13)))]
        if invoice.get("courier"):
            label.append(Paragraph(esc(invoice["courier"]), small))
        col_widths = [width * 0.3, (L.qr_size + 4) * mm, None]
        barcode_room = width - col_widths[0] - col_widths[1] - L.pt(6) - 6  # the last column minus its cell padding
        if barcode.width <= barcode_room:
            rows, spans = [[label, qr, barcode]], []
        else:  # a long Parcel ID / big barcode: its own full-width row below (as the web layout wraps it)
            rows, spans = [[label, qr, ""], [barcode, "", ""]], [("SPAN", (0, 1), (-1, 1))]
        parcel_table = Table(rows, colWidths=col_widths)
        parcel_table.setStyle(TableStyle([*spans, ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, line),
                                          ("LEFTPADDING", (0, 0), (-1, -1), L.pt(6)), ("TOPPADDING", (0, 0), (-1, -1), L.pt(4)),
                                          ("BOTTOMPADDING", (0, 0), (-1, -1), L.pt(4))]))
        story.append(KeepTogether(parcel_table) if keep_together else parcel_table)
    else:
        story.append(Paragraph("PARCEL ID: not assigned yet (it is added when the order is handed to the courier).", small))
    story += [Spacer(1, L.gap(6)),
              Paragraph("Thank you for your purchase.", ParagraphStyle("thanks", parent=base, fontName="Honacu", fontSize=L.pt(11), leading=L.pt(14), textColor=brand))]
    return story
