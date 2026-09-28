from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime

# Explicit on all sides: SimpleDocTemplate leaves unstated margins at ~1in by default.
_PDF_PAGE_MARGINS = dict(
    leftMargin=1.2 * cm,
    rightMargin=1.2 * cm,
    topMargin=0.45 * cm,
    bottomMargin=0.8 * cm,
)


def format_datetime_12h(dt=None):
    """Format datetime in 12-hour format (e.g., '2026-01-28 12:52 PM')"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime('%Y-%m-%d %I:%M %p')


def generate_debt_report(transactions, total_debt, start_date, end_date, customer_name=None):
    """Generate a PDF report of debt transactions"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, **_PDF_PAGE_MARGINS)

    styles = getSampleStyleSheet()
    # Match styling with the customer / all-customers PDFs
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=6,
        spaceBefore=0,
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=4,
        spaceBefore=0,
        textColor=colors.grey
    )
    total_style = ParagraphStyle(
        'Total',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_RIGHT,
        spaceBefore=12,
        spaceAfter=12,
        textColor=colors.Color(0.8, 0.1, 0.1)
    )

    elements = []

    # Title
    elements.append(Paragraph("Pharmacy Thabet", title_style))
    elements.append(Paragraph("Debt Report", subtitle_style))

    # Date range / customer line – styled like the other PDFs
    range_line = f"{start_date} to {end_date}"
    if customer_name:
        range_line = f"Customer: <b>{customer_name}</b><br/>{range_line}"
    elements.append(Paragraph(range_line, subtitle_style))
    elements.append(Spacer(1, 10))

    # Transactions table
    if transactions:
        data = [['Date', 'Customer', 'Type', 'Amount', 'Notes']]
        for trans in transactions:
            # Get date from created_at or date field
            date_val = trans.get('created_at') or trans.get('date') or '-'
            if date_val and date_val != '-':
                date_val = date_val[:10]

            # Get amount from amount or total field
            amount = trans.get('amount') or trans.get('total') or 0

            # Format amount based on type
            entry_type = trans.get('entry_type', 'DEBT')
            if entry_type == 'NEW_DEBT':
                amount_str = f"+${amount:.2f}"
                type_str = "Debt"
            elif entry_type == 'PAYMENT':
                amount_str = f"-${abs(amount):.2f}"
                type_str = "Payment"
            else:
                amount_str = f"${amount:.2f}"
                type_str = entry_type

            data.append([
                date_val,
                trans.get('customer_name', '-'),
                type_str,
                amount_str,
                trans.get('notes') or trans.get('description') or '-'
            ])

        table = Table(data, colWidths=[2.5*cm, 4*cm, 2.5*cm, 3*cm, 5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.17, 0.32, 0.51)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.Color(0.9, 0.9, 0.9)),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No transactions found for the selected period.", styles['Normal']))

    # Total (match GRAND TOTAL style from all-customers PDF)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"<b>GRAND TOTAL: ${total_debt:.2f}</b>", total_style))

    # Footer with generation date
    elements.append(Spacer(1, 40))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(f"Generated on {format_datetime_12h()}", footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_debt_report_by_date_range(customers_data, total_debt, start_date, end_date):
    """Generate a PDF report of customers with debts for a date range, formatted like All Customers Debt Report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, **_PDF_PAGE_MARGINS)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=6,
        spaceBefore=0,
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=0,
        textColor=colors.grey
    )
    customer_name_style = ParagraphStyle(
        'CustomerName',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.Color(0.17, 0.32, 0.51)
    )
    grand_total_style = ParagraphStyle(
        'GrandTotal',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_RIGHT,
        spaceBefore=30,
        spaceAfter=20,
        textColor=colors.Color(0.8, 0.1, 0.1)
    )

    elements = []

    # Title
    elements.append(Paragraph("Pharmacy Thabet", title_style))
    elements.append(Paragraph("Debt Report", subtitle_style))
    elements.append(Paragraph(f"{start_date} to {end_date}", subtitle_style))
    elements.append(Paragraph(f"Generated on {format_datetime_12h()}", subtitle_style))
    elements.append(Spacer(1, 10))

    # Process each customer (only customers with debt > 0 are included)
    if customers_data:
        for customer in customers_data:
            # Customer name and debt
            elements.append(Paragraph(f"<b>{customer['name']}</b>", customer_name_style))
            elements.append(Paragraph(f"Amount Owed: <b>${customer['debt']:.2f}</b>", styles['Normal']))
            elements.append(Spacer(1, 8))
            
            # Compact items list for this customer
            if customer.get('items') and len(customer['items']) > 0:
                # Group items by product name and sum quantities
                from collections import defaultdict
                product_totals = defaultdict(lambda: {'quantity': 0, 'total': 0})
                
                for item in customer['items']:
                    product_name = item.get('product_name', 'Unknown')
                    quantity = item.get('quantity', 1)
                    price = item.get('price', 0)
                    item_total = price * quantity
                    
                    product_totals[product_name]['quantity'] += quantity
                    product_totals[product_name]['total'] += item_total
                
                # Build compact product list
                product_list = []
                for product_name, data in sorted(product_totals.items()):
                    qty = data['quantity']
                    
                    if qty > 1:
                        product_list.append(f"{product_name} (x{qty})")
                    else:
                        product_list.append(product_name)
                
                # Display products as comma-separated list
                products_text = ", ".join(product_list)
                elements.append(Paragraph(f"<b>Products:</b> {products_text}", styles['Normal']))
            else:
                elements.append(Paragraph("No items recorded.", styles['Normal']))
            
            elements.append(Spacer(1, 12))
    else:
        elements.append(Paragraph("No customers with debt in this date range.", styles['Normal']))

    # Summary before Grand Total
    elements.append(Spacer(1, 20))
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_RIGHT,
        spaceAfter=10,
        textColor=colors.Color(0.17, 0.32, 0.51)
    )
    total_customers = len(customers_data) if customers_data else 0
    elements.append(Paragraph(f"Total Customers with Debts: <b>{total_customers}</b>", summary_style))
    
    # Grand Total
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>GRAND TOTAL: ${total_debt:.2f}</b>", grand_total_style))

    # Footer
    elements.append(Spacer(1, 40))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(f"Report generated on {format_datetime_12h()}", footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_all_customers_debt_report(customers_data, total_debt):
    """PDF: all customers who owe money — summary table only (name, phone, amount)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, **_PDF_PAGE_MARGINS)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=6,
        spaceBefore=0,
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=0,
        textColor=colors.grey
    )
    grand_total_style = ParagraphStyle(
        'GrandTotal',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_RIGHT,
        spaceBefore=16,
        spaceAfter=12,
        textColor=colors.Color(0.8, 0.1, 0.1)
    )

    elements = []
    elements.append(Paragraph("Pharmacy Thabet", title_style))
    elements.append(Paragraph("All Customers — Amounts Owed", subtitle_style))
    elements.append(Paragraph(f"Generated on {format_datetime_12h()}", subtitle_style))
    elements.append(Spacer(1, 12))

    # Deduplicate by customer id (keep first / highest debt order from caller)
    seen_ids = set()
    unique_customers = []
    for customer in customers_data or []:
        cid = customer.get('id')
        if cid is None or cid in seen_ids:
            continue
        seen_ids.add(cid)
        unique_customers.append(customer)

    if unique_customers:
        summary_data = [['#', 'Customer', 'Phone', 'Amount Owed']]
        row_total = 0.0
        for idx, customer in enumerate(unique_customers, start=1):
            debt = float(customer.get('debt') or 0)
            row_total += debt
            name = customer.get('name') or 'Unknown'
            phone = customer.get('phone') or '—'
            summary_data.append([
                str(idx),
                Paragraph(name, styles['Normal']),
                phone,
                f"${debt:.2f}",
            ])

        summary_table = Table(summary_data, colWidths=[1.0 * cm, 7.5 * cm, 3.5 * cm, 3.5 * cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.17, 0.32, 0.51)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.9, 0.9, 0.9)),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.98, 0.98, 0.98)]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(
            f"<b>Customers owing: {len(unique_customers)}</b> &nbsp;|&nbsp; "
            f"<b>Total from list: ${row_total:.2f}</b>",
            ParagraphStyle('Meta', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)
        ))
    else:
        elements.append(Paragraph("No customers with outstanding balances.", styles['Normal']))

    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>GRAND TOTAL OWED: ${total_debt:.2f}</b>", grand_total_style))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Report generated on {format_datetime_12h()}", footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer
