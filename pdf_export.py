from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime


def format_datetime_12h(dt=None):
    """Format datetime in 12-hour format (e.g., '2026-01-28 12:52 PM')"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime('%Y-%m-%d %I:%M %p')


def generate_debt_report(transactions, total_debt, start_date, end_date, customer_name=None):
    """Generate a PDF report of debt transactions"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    # Match styling with the customer / all-customers PDFs
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=5,
        textColor=colors.grey
    )
    total_style = ParagraphStyle(
        'Total',
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

    # Date range / customer line – styled like the other PDFs
    range_line = f"{start_date} to {end_date}"
    if customer_name:
        range_line = f"Customer: <b>{customer_name}</b><br/>{range_line}"
    elements.append(Paragraph(range_line, subtitle_style))
    elements.append(Spacer(1, 20))

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
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=20,
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
    elements.append(Spacer(1, 20))

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


def generate_customer_report(customer, ledger, payments, total_debt, total_debts=0, total_payments=0):
    """Generate a PDF report for a specific customer"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=5,
        textColor=colors.Color(0.17, 0.32, 0.51)
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=15,
        textColor=colors.grey
    )
    customer_name_style = ParagraphStyle(
        'CustomerName',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=10,
        spaceAfter=5,
        textColor=colors.Color(0.17, 0.32, 0.51)
    )
    info_style = ParagraphStyle(
        'Info',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=3
    )
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=12,
        textColor=colors.Color(0.17, 0.32, 0.51)
    )
    summary_label_style = ParagraphStyle(
        'SummaryLabel',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.grey
    )
    summary_value_style = ParagraphStyle(
        'SummaryValue',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.Color(0.17, 0.32, 0.51)
    )
    balance_style = ParagraphStyle(
        'Balance',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=TA_CENTER,
        spaceBefore=15,
        spaceAfter=20,
        textColor=colors.Color(0.8, 0.1, 0.1) if total_debt > 0 else colors.Color(0.1, 0.6, 0.3)
    )

    elements = []

    # Title
    elements.append(Paragraph("Pharmacy Thabet", title_style))
    elements.append(Paragraph("Customer Report", subtitle_style))
    elements.append(Spacer(1, 15))

    # Customer Info Box
    customer_info = []
    customer_info.append(Paragraph(f"<b>{customer['name']}</b>", customer_name_style))
    if customer.get('phone'):
        customer_info.append(Paragraph(f"<b>Phone:</b> {customer['phone']}", info_style))
    if customer.get('email'):
        customer_info.append(Paragraph(f"<b>Email:</b> {customer.get('email')}", info_style))
    if customer.get('address'):
        customer_info.append(Paragraph(f"<b>Address:</b> {customer.get('address')}", info_style))
    
    for item in customer_info:
        elements.append(item)
    
    elements.append(Spacer(1, 15))

    # Summary Section
    summary_data = [
        ['Total Debts', Paragraph(f"${total_debts:.2f}", styles['Normal'])],
        ['Total Payments', Paragraph(f"<font color='green'>${total_payments:.2f}</font>", styles['Normal'])],
        ['Debt Left', Paragraph(f"<font color='red'>${total_debt:.2f}</font>", styles['Normal'])]
    ]
    
    summary_table = Table(summary_data, colWidths=[6*cm, 6*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.Color(0.95, 0.95, 0.95)),
        ('BACKGROUND', (1, 0), (1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.Color(0.3, 0.3, 0.3)),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.Color(0.17, 0.32, 0.51)),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.Color(0.9, 0.9, 0.9)),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(summary_table)
    
    elements.append(Spacer(1, 20))

    # Debt Left (highlighted)
    balance_color = "red" if total_debt > 0 else "green"
    balance_text = "Debt Left" if total_debt > 0 else "Credit Balance"
    elements.append(Paragraph(f"<b>{balance_text}: <font color='{balance_color}'>${abs(total_debt):.2f}</font></b>", balance_style))

    elements.append(Spacer(1, 20))

    # Transaction History
    elements.append(Paragraph("Transaction History", section_style))
    if ledger:
        data = [['Date', 'Type', 'Items', 'Debt Added', 'Payment', 'Notes']]
        for entry in ledger:
            date_val = entry.get('created_at', '-')
            if date_val and date_val != '-':
                date_val = date_val[:10]

            entry_type = entry.get('entry_type', '')
            amount = entry.get('amount', 0) or 0

            debt_col = ""
            payment_col = ""
            items_col = ""

            if entry_type == 'NEW_DEBT':
                debt_col = f"+${amount:.2f}"
                type_str = "Debt"
                # Get items for this debt entry
                items = entry.get('items', [])
                if items and len(items) > 0:
                    # Format items: "Product1 (x2), Product2, Product3 (x3)"
                    item_list = []
                    for item in items:
                        product_name = item.get('product_name', 'Unknown')
                        quantity = item.get('quantity', 1)
                        if quantity > 1:
                            item_list.append(f"{product_name} (x{quantity})")
                        else:
                            item_list.append(product_name)
                    # Join items and wrap in Paragraph for proper text wrapping
                    items_text = ", ".join(item_list)
                    items_col = Paragraph(items_text, styles['Normal'])
                else:
                    items_col = "-"
            elif entry_type == 'PAYMENT':
                # Format payment in green color
                payment_col = Paragraph(f"<font color='green'>-${abs(amount):.2f}</font>", styles['Normal'])
                type_str = "Payment"
                items_col = "-"
            else:
                type_str = entry_type
                debt_col = f"${amount:.2f}"
                items_col = "-"

            # Wrap notes in Paragraph for proper text wrapping
            notes_text = entry.get('notes') or entry.get('description') or '-'
            notes_col = Paragraph(notes_text, styles['Normal']) if notes_text != '-' else '-'

            data.append([
                date_val,
                type_str,
                items_col,
                debt_col,
                payment_col,
                notes_col
            ])

        # Increased Items column width and adjusted others for better layout
        table = Table(data, colWidths=[2.5*cm, 2*cm, 7*cm, 2.5*cm, 2.5*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.17, 0.32, 0.51)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (4, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.Color(0.9, 0.9, 0.9)),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 1), (-1, -1), 6),
            ('RIGHTPADDING', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.98, 0.98, 0.98)]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('WORDWRAP', (2, 1), (2, -1), True),  # Enable word wrap for Items column
            ('WORDWRAP', (5, 1), (5, -1), True),  # Enable word wrap for Notes column
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No transaction history.", styles['Normal']))

    # Footer
    elements.append(Spacer(1, 30))
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


def generate_all_customers_debt_report(customers_data, total_debt):
    """Generate a PDF report of all customers with debts, their items, and totals"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=20,
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
    elements.append(Paragraph("All Customers Debt Report", subtitle_style))
    elements.append(Paragraph(f"Generated on {format_datetime_12h()}", subtitle_style))
    elements.append(Spacer(1, 20))

    # Process each customer (only customers with debt > 0 are included)
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
            customer_total = 0
            for product_name, data in sorted(product_totals.items()):
                qty = data['quantity']
                total = data['total']
                customer_total += total
                
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
