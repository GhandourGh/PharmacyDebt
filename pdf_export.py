from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, LongTable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime
from xml.sax.saxutils import escape

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


def generate_customer_statement_pdf(customer, statement, mode='unpaid'):
    """Generate a directly downloadable A5 customer statement PDF."""
    if mode not in {'unpaid', 'full'}:
        raise ValueError('Statement mode must be unpaid or full.')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A5,
        leftMargin=0.8 * cm,
        rightMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
        title=f"{customer.get('name', 'Customer')} - Pharmacy Thabet",
        author='Pharmacy Thabet',
    )

    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle(
        'StatementBrand', parent=styles['Heading1'], fontName='Helvetica-Bold',
        fontSize=12, leading=14, alignment=TA_CENTER, spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        'StatementSubtitle', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=9, leading=11, alignment=TA_CENTER, spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        'StatementMeta', parent=styles['Normal'], fontSize=7, leading=9,
        textColor=colors.Color(0.33, 0.33, 0.33), alignment=TA_CENTER,
    )
    customer_style = ParagraphStyle(
        'StatementCustomer', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=10.5, leading=13, spaceAfter=2,
    )
    customer_meta_style = ParagraphStyle(
        'StatementCustomerMeta', parent=styles['Normal'], fontSize=7.5, leading=9,
        textColor=colors.Color(0.25, 0.25, 0.25),
    )
    section_style = ParagraphStyle(
        'StatementSection', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=9, leading=11, spaceBefore=5, spaceAfter=3,
    )
    cell_style = ParagraphStyle(
        'StatementCell', parent=styles['Normal'], fontSize=7.25, leading=9,
        splitLongWords=True,
    )
    amount_style = ParagraphStyle(
        'StatementAmount', parent=cell_style, alignment=TA_RIGHT,
        wordWrap='LTR',
    )
    total_due = statement['total_due'] if mode == 'unpaid' else statement['balance_due']
    balance_label = 'CURRENT CREDIT BALANCE' if total_due < 0 else ('TOTAL DUE' if mode == 'unpaid' else 'CURRENT BALANCE DUE')
    subtitle = 'Outstanding Statement' if mode == 'unpaid' else 'Account Statement'

    elements = [
        Paragraph('Pharmacy Thabet', brand_style),
        Paragraph(subtitle, subtitle_style),
        Paragraph(f"Generated on {datetime.now().strftime('%m/%d/%Y, %I:%M:%S %p')}", meta_style),
        Spacer(1, 0.22 * cm),
        Table([['']], colWidths=[doc.width], rowHeights=[0.04 * cm], style=TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.black),
            ('LINEBELOW', (0, 0), (-1, -1), 0, colors.black),
        ])),
        Spacer(1, 0.28 * cm),
        Paragraph(escape(str(customer.get('name') or 'Customer')), customer_style),
    ]
    if customer.get('phone'):
        elements.append(Paragraph(f"Phone: {escape(str(customer['phone']))}", customer_meta_style))
    elements.append(Spacer(1, 0.2 * cm))

    balance_table = Table(
        [[Paragraph(balance_label, subtitle_style)],
         [Paragraph(f"${abs(float(total_due)):.2f}", ParagraphStyle(
             'StatementBalance', parent=styles['Normal'], fontName='Helvetica-Bold',
             fontSize=16, leading=18, alignment=TA_CENTER,
         ))]],
        colWidths=[doc.width],
    )
    balance_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
        ('TOPPADDING', (0, 1), (-1, 1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 7),
    ]))
    elements.append(balance_table)

    if mode == 'full':
        summary = Table([
            ['Total Charges', f"${statement['total_charges']:.2f}"],
            ['Payments Received', f"${statement['total_payments']:.2f}"],
            ['Credit Balance' if total_due < 0 else 'Balance Due', f"${abs(total_due):.2f}"],
        ], colWidths=[5.8 * cm, 3.2 * cm], hAlign='CENTER')
        summary.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, -1), (-1, -1), 0.6, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.extend([Spacer(1, 0.25 * cm), summary])

    elements.append(Paragraph('Outstanding Debts' if mode == 'unpaid' else 'Account Activity', section_style))
    if mode == 'unpaid':
        data = [['DATE', 'ITEMS', 'ORIGINAL', 'PAID', 'REMAINING']]
        for row in statement['rows']:
            data.append([
                row['date'], Paragraph(escape(str(row['details'])), cell_style),
                f"${row['original']:.2f}", f"${row['paid']:.2f}" if row['paid'] is not None else '-',
                f"${row['remaining']:.2f}",
            ])
        if not statement['rows']:
            data.append(['', Paragraph('No outstanding debts.', cell_style), '', '', ''])
        if statement.get('has_adjustment'):
            data.append(['', '', '', 'Outstanding debts', f"${statement['outstanding_total']:.2f}"])
            sign = '-' if statement['adjustment'] < 0 else '+'
            data.append(['', '', '', 'Adjustments', f"{sign}${abs(statement['adjustment']):.2f}"])
        data.append(['TOTAL DUE' if total_due >= 0 else 'CURRENT CREDIT BALANCE', '', '', '', f"${abs(total_due):.2f}"])
        col_widths = [2.1 * cm, 5.55 * cm, 1.85 * cm, 1.85 * cm, 1.85 * cm]
    else:
        data = [['DATE', 'ACTIVITY', 'DETAILS', 'CHARGE', 'PAYMENT', 'BALANCE']]
        for row in statement['activity']:
            data.append([
                row['date'], Paragraph(escape(str(row['activity'])), cell_style),
                Paragraph(escape(str(row['details'])), cell_style),
                f"${row['charge']:.2f}" if row['charge'] is not None else '-',
                f"${row['payment']:.2f}" if row['payment'] is not None else '-',
                f"${row['balance']:.2f}",
            ])
        if not statement['activity']:
            data.append(['', '', Paragraph('No account activity.', cell_style), '', '', ''])
        data.append([balance_label, '', '', '', '', f"${abs(total_due):.2f}"])
        col_widths = [1.95 * cm, 1.7 * cm, 3.95 * cm, 1.85 * cm, 1.85 * cm, 1.9 * cm]

    table = LongTable(
        data,
        colWidths=col_widths,
        repeatRows=1,
        hAlign='LEFT',
        splitByRow=True,
    )
    last_row = len(data) - 1
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.92, 0.92, 0.92)),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 6.5),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7.25),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.black),
        ('LINEBELOW', (0, 1), (-1, -2), 0.3, colors.Color(0.75, 0.75, 0.75)),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('LINEABOVE', (0, last_row), (-1, last_row), 1, colors.black),
        ('FONTNAME', (0, last_row), (-1, last_row), 'Helvetica-Bold'),
        ('SPAN', (0, last_row), (-2, last_row)),
        ('ALIGN', (0, last_row), (0, last_row), 'LEFT'),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer


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
