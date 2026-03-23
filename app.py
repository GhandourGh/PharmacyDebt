from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import database as db
from pdf_export import generate_debt_report, generate_customer_report, generate_all_customers_debt_report, generate_debt_report_by_date_range
from validators import (
    ValidationError, validate_amount, validate_quantity,
    validate_payment_amount, validate_date_range, validate_customer_active,
    validate_string, validate_debt_items, validate_donation_usage,
    validate_file_type
)
import os
import io
from chatbot import process_message

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'pharmacy-thabet-secret-key')

# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database on startup
db.init_db()

# ============== DASHBOARD ==============

@app.route('/')
def dashboard():
    total_debt = db.get_total_debt_all()
    recent_activity = db.get_recent_activity(10)
    # Get all customers for search functionality, but we'll show only recent ones initially
    all_customers = db.get_customers_with_debt()
    recent_customers = db.get_recent_active_customers(4)  # Get 4 most recent customers with activity
    daily_stats = db.get_daily_reconciliation()
    products = db.get_all_products()
    
    # Fix negative zero display issue and detect credit customers
    for customer in all_customers:
        debt = customer.get('debt', 0)
        if debt < 0:
            customer['has_credit'] = True
            customer['display_debt'] = abs(debt)
        else:
            customer['has_credit'] = False
            customer['display_debt'] = debt

    for customer in recent_customers:
        debt = customer.get('debt', 0)
        if debt < 0:
            customer['has_credit'] = True
            customer['display_debt'] = abs(debt)
        else:
            customer['has_credit'] = False
            customer['display_debt'] = debt

    # Count customers with debts (debt > 0)
    customers_with_debt_count = len([c for c in all_customers if c.get('debt', 0) > 0])

    return render_template('dashboard.html',
                         total_debt=total_debt,
                         recent_activity=recent_activity,
                         all_customers=all_customers,  # Pass all customers for search
                         recent_customers=recent_customers,  # Pass recent customers for initial display
                         daily_stats=daily_stats,
                         products=products,
                         customers_with_debt_count=customers_with_debt_count)

# ============== SEARCH API ==============

@app.route('/api/search')
def search():
    query = request.args.get('q', '')
    customers = db.search_customers(query)
    for customer in customers:
        customer['debt'] = db.get_customer_total_debt(customer['id'])
    return jsonify(customers)

# ============== ANALYTICS ==============

@app.route('/analytics')
def analytics():
    """Analytics page with charts and statistics"""
    total_debt = db.get_total_debt_all()
    customers = db.get_customers_with_debt()
    customers_with_debt = len([c for c in customers if c['debt'] > 0])

    # Calculate weekly totals
    weekly_debt = 0
    weekly_payments = 0
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        stats = db.get_daily_reconciliation(date)
        weekly_debt += float(stats['total_debt'] or 0)
        weekly_payments += float(stats['total_payments'] or 0)

    return render_template('analytics.html',
                         total_debt=total_debt,
                         customers_with_debt=customers_with_debt,
                         weekly_debt=weekly_debt,
                         weekly_payments=weekly_payments)

# ============== DASHBOARD STATS API ==============

@app.route('/api/dashboard-stats')
def dashboard_stats():
    """Get statistics for dashboard charts"""
    # Weekly summary (last 7 days)
    weekly_data = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        stats = db.get_daily_reconciliation(date)
        weekly_data.append({
            'date': date,
            'day': (datetime.now() - timedelta(days=i)).strftime('%a'),
            'debt': float(stats['total_debt']),
            'payments': float(stats['total_payments'])
        })

    # Top debtors (customers with highest debt)
    customers = db.get_customers_with_debt()
    top_debtors = sorted([c for c in customers if c['debt'] > 0], key=lambda x: x['debt'], reverse=True)[:10]
    top_debtors_data = [{
        'name': c['name'][:15] + '...' if len(c['name']) > 15 else c['name'],
        'debt': float(c['debt'])
    } for c in top_debtors]

    # Monthly trend (last 6 months)
    monthly_data = []
    for i in range(5, -1, -1):
        # Get first and last day of each month
        first_day = (datetime.now().replace(day=1) - timedelta(days=i*30)).replace(day=1)
        if first_day.month == 12:
            last_day = first_day.replace(year=first_day.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = first_day.replace(month=first_day.month + 1, day=1) - timedelta(days=1)

        # Get transactions for the month
        transactions = db.get_transactions_by_date(
            first_day.strftime('%Y-%m-%d'),
            last_day.strftime('%Y-%m-%d')
        )

        total_debt = sum(t['amount'] for t in transactions if t['entry_type'] == 'NEW_DEBT')
        total_payments = sum(t['amount'] for t in transactions if t['entry_type'] == 'PAYMENT')

        monthly_data.append({
            'month': first_day.strftime('%b'),
            'debt': float(total_debt),
            'payments': float(total_payments)
        })

    return jsonify({
        'weekly': weekly_data,
        'top_debtors': top_debtors_data,
        'monthly': monthly_data
    })

# ============== CUSTOMERS ==============

@app.route('/customers')
def customers():
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    per_page = min(per_page, 50)  # Max 50 per page

    customers_list = db.get_customers_with_debt()
    products = db.get_all_products()
    
    # Fix negative zero display issue - ensure zero balances show as positive
    for customer in customers_list:
        if customer.get('debt', 0) <= 0:
            customer['display_debt'] = abs(customer.get('debt', 0))
        else:
            customer['display_debt'] = customer.get('debt', 0)

    # Calculate pagination
    total = len(customers_list)
    total_pages = (total + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_customers = customers_list[start_idx:end_idx]

    return render_template('customers.html',
                         customers=paginated_customers,
                         products=products,
                         page=page,
                         per_page=per_page,
                         total=total,
                         total_pages=total_pages)

@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    if request.method == 'POST':
        try:
            name = validate_string(request.form.get('name'), 'Customer name', max_length=200)
            phone = validate_string(request.form.get('phone', ''), 'Phone', required=False, max_length=50)
            notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=1000)

            # Handle profile image upload
            profile_image = None
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    try:
                        # Validate file size
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)
                        if file_size > MAX_FILE_SIZE:
                            raise ValidationError(f'File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024}MB)')
                        
                        # Validate file type including MIME check
                        validate_file_type(
                            file,
                            ALLOWED_EXTENSIONS,
                            allowed_mimetypes=['image/png', 'image/jpeg', 'image/gif', 'image/webp']
                        )

                        filename = secure_filename(file.filename)
                        # Handle empty filename after secure_filename (special chars only)
                        if not filename or filename == '':
                            filename = 'uploaded_image.jpg'

                        # Add timestamp to make filename unique
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        filename = f"{timestamp}_{filename}"
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        file.save(filepath)
                        profile_image = filename

                    except ValidationError as e:
                        flash(f'Image upload warning: {e.message}', 'warning')
                        # Continue without profile image

            customer_id = db.add_customer(name, phone, notes=notes, profile_image=profile_image)
            flash(f'Customer "{name}" added successfully.', 'success')
            return redirect(url_for('customer_detail', customer_id=customer_id))

        except ValidationError as e:
            flash(e.message, 'error')
            existing_customers = db.get_all_customers()
            customer_names = [c['name'] for c in existing_customers if c.get('name')]
            return render_template('add_customer.html', customer_names=customer_names)
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'error')
            existing_customers = db.get_all_customers()
            customer_names = [c['name'] for c in existing_customers if c.get('name')]
            return render_template('add_customer.html', customer_names=customer_names)

    # Get existing customer names for autocomplete
    existing_customers = db.get_all_customers()
    customer_names = [c['name'] for c in existing_customers if c.get('name')]
    
    return render_template('add_customer.html', customer_names=customer_names)

@app.route('/customers/<int:customer_id>')
def customer_detail(customer_id):
    customer = db.get_customer(customer_id)
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))

    ledger = db.get_customer_ledger(customer_id, include_voided=True)
    total_debt = db.get_customer_balance(customer_id)
    products = db.get_all_products()

    # Calculate total paid and original total from ledger (voided entries still count)
    total_paid = 0
    total_original = 0
    for entry in ledger:
        if entry.get('entry_type') == 'NEW_DEBT':
            total_original += entry.get('amount', 0)
        elif entry.get('entry_type') == 'PAYMENT':
            total_paid += abs(entry.get('amount', 0))

    # Ensure zero balance is displayed as positive (fixes -0.00 issue)
    display_debt = abs(total_debt) if total_debt <= 0 else total_debt

    # Get unpaid debts for FIFO display
    unpaid_debts = db.get_unpaid_debts(customer_id)

    # Receipt/print: only OPEN/PARTIAL purchases that still have a balance due (exclude $0 / credit-covered)
    receipt_ledger = []
    for e in ledger:
        if e.get('is_voided') or e.get('entry_type') != 'NEW_DEBT' or e.get('payment_status') not in ('OPEN', 'PARTIAL'):
            continue
        remaining = e.get('remaining_amount') if e.get('remaining_amount') is not None else e.get('amount', 0)
        if (remaining or 0) <= 0:
            continue
        receipt_ledger.append(e)

    return render_template('customer_detail.html',
                         customer=customer,
                         ledger=ledger,
                         receipt_ledger=receipt_ledger,
                         total_debt=total_debt,
                         display_debt=display_debt,
                         total_paid=total_paid,
                         total_original=total_original,
                         products=products,
                         unpaid_debts=unpaid_debts)

@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = db.get_customer(customer_id)
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))

    if request.method == 'POST':
        try:
            name = validate_string(request.form.get('name'), 'Customer name', max_length=200)
            phone = validate_string(request.form.get('phone', ''), 'Phone', required=False, max_length=50)
            notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=1000)

            # Handle profile image upload
            profile_image = customer.get('profile_image')  # Keep existing image by default

            # Check if user wants to remove the image
            if request.form.get('remove_image'):
                if profile_image:
                    # Delete old image file
                    old_filepath = os.path.join(UPLOAD_FOLDER, profile_image)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                profile_image = None
            elif 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    try:
                        # Validate file size
                        file.seek(0, os.SEEK_END)
                        file_size = file.tell()
                        file.seek(0)
                        if file_size > MAX_FILE_SIZE:
                            raise ValidationError(f'File size ({file_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size ({MAX_FILE_SIZE / 1024 / 1024}MB)')
                        
                        # Validate file type including MIME check
                        validate_file_type(
                            file,
                            ALLOWED_EXTENSIONS,
                            allowed_mimetypes=['image/png', 'image/jpeg', 'image/gif', 'image/webp']
                        )

                        # Delete old image if exists
                        if profile_image:
                            old_filepath = os.path.join(UPLOAD_FOLDER, profile_image)
                            if os.path.exists(old_filepath):
                                os.remove(old_filepath)

                        # Save new image
                        filename = secure_filename(file.filename)
                        # Handle empty filename after secure_filename
                        if not filename or filename == '':
                            filename = 'uploaded_image.jpg'

                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        filename = f"{timestamp}_{filename}"
                        filepath = os.path.join(UPLOAD_FOLDER, filename)
                        file.save(filepath)
                        profile_image = filename

                    except ValidationError as e:
                        flash(f'Image upload warning: {e.message}', 'warning')
                        # Continue with old profile image

            db.update_customer(customer_id, name, phone, notes=notes, profile_image=profile_image)
            flash('Customer updated successfully.', 'success')
            return redirect(url_for('customer_detail', customer_id=customer_id))

        except ValidationError as e:
            flash(e.message, 'error')
            return render_template('edit_customer.html', customer=customer)
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'error')
            return render_template('edit_customer.html', customer=customer)

    return render_template('edit_customer.html', customer=customer)

@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
def delete_customer(customer_id):
    db.deactivate_customer(customer_id)
    flash('Customer deleted successfully.', 'success')
    return redirect(url_for('customers'))

# ============== DEBT & PAYMENT ==============

@app.route('/customers/<int:customer_id>/add-debt', methods=['POST'])
def add_debt(customer_id):
    try:
        # Validate customer exists and is active
        customer = db.get_customer(customer_id)
        validate_customer_active(customer)

        # Parse items from form
        items = []
        i = 0
        while f'product_name_{i}' in request.form:
            product_name = request.form.get(f'product_name_{i}')
            price = request.form.get(f'price_{i}')
            quantity = request.form.get(f'quantity_{i}', 1)

            if product_name and price:
                items.append({
                    'product_name': product_name,
                    'price': price,
                    'quantity': quantity
                })
            i += 1

        # Validate all items (validates amounts, quantities, and ensures at least one item)
        validated_items, total = validate_debt_items(items)

        # Validate notes
        notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=500)

        # Optional debt date
        debt_date = request.form.get('debt_date', '').strip() or None
        if debt_date:
            try:
                datetime.strptime(debt_date, '%Y-%m-%d')
            except ValueError:
                raise ValidationError('Invalid date format')

        # Check if customer has credit before adding debt (for flash message)
        current_balance = db.get_customer_balance(customer_id)
        db.add_debt(customer_id, validated_items, notes=notes, user_id=None, debt_date=debt_date)

        if current_balance < 0:
            credit_available = abs(current_balance)
            credit_used = min(credit_available, total)
            remaining_credit = round(credit_available - credit_used, 2)
            actual_debt = round(total - credit_used, 2)
            if actual_debt <= 0:
                flash(f'${total:.2f} purchase covered by credit. Remaining credit: ${remaining_credit:.2f}', 'success')
            else:
                flash(f'${credit_used:.2f} covered by credit. Remaining debt: ${actual_debt:.2f}', 'success')
        else:
            flash(f'Debt of ${total:.2f} added.', 'success')
        return redirect(url_for('customer_detail', customer_id=customer_id))

    except ValidationError as e:
        flash(e.message, 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))
    except Exception as e:
        flash(f'An unexpected error occurred: {str(e)}', 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))


@app.route('/customers/<int:customer_id>/mark-paid', methods=['POST'])
def mark_paid(customer_id):
    """Mark a customer as fully paid by recording a payment equal to their current balance."""
    try:
        # Validate customer exists and is active
        customer = db.get_customer(customer_id)
        validate_customer_active(customer)

        # Get current balance
        current_balance = db.get_customer_balance(customer_id)

        if current_balance <= 0:
            flash('Customer has no outstanding balance to mark as paid.', 'info')
            return redirect(url_for('customer_detail', customer_id=customer_id))

        # Record a payment for the full remaining balance
        db.add_payment(
            customer_id,
            current_balance,
            payment_method='CASH',
            notes='Marked as paid (auto full payment)',
            user_id=None
        )

        flash(f'Customer marked as paid with a payment of ${current_balance:.2f}.', 'success')
        return redirect(url_for('customer_detail', customer_id=customer_id))

    except ValidationError as e:
        flash(e.message, 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))
    except Exception as e:
        flash(f'An unexpected error occurred: {str(e)}', 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))

@app.route('/customers/<int:customer_id>/add-payment', methods=['POST'])
def add_payment(customer_id):
    try:
        # Validate customer exists and is active
        customer = db.get_customer(customer_id)
        validate_customer_active(customer)

        # Get current balance to check for overpayment
        current_balance = db.get_customer_balance(customer_id)

        # Validate payment amount (blocks overpayments)
        amount_input = request.form.get('amount')
        amount, _ = validate_payment_amount(amount_input, current_balance, allow_overpayment=False)

        # Validate payment method
        payment_method = request.form.get('payment_method', 'CASH')
        if payment_method not in ['CASH', 'CARD', 'CHECK', 'CREDIT', 'SPLIT']:
            payment_method = 'CASH'

        # Validate notes
        notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=500)

        db.add_payment(customer_id, amount, payment_method=payment_method, notes=notes, user_id=None)

        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': True, 'message': f'Payment of ${amount:.2f} recorded.'})

        flash(f'Payment of ${amount:.2f} recorded.', 'success')
        return redirect(url_for('customer_detail', customer_id=customer_id))

    except ValidationError as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': False, 'error': e.message}), 400
        flash(e.message, 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'An unexpected error occurred: {str(e)}', 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))


@app.route('/customers/<int:customer_id>/add-credit', methods=['POST'])
def add_credit(customer_id):
    """
    Add third‑party credit to a customer's account.

    This credit will:
    - Reduce any existing debt immediately
    - Become a positive credit (negative balance) if there is no debt,
      and will be automatically consumed by future debts.
    """
    try:
        # Validate customer exists and is active
        customer = db.get_customer(customer_id)
        validate_customer_active(customer)

        # Validate credit amount (no balance check – credit is always allowed)
        amount = validate_amount(request.form.get('amount'), 'Amount')

        # Validate payer name (Person Y) and notes
        payer_name = validate_string(
            request.form.get('payer_name', ''),
            'Payer name',
            required=False,
            max_length=200,
        )
        notes = validate_string(
            request.form.get('notes', ''),
            'Notes',
            required=False,
            max_length=500,
        )

        db.add_credit(
            customer_id,
            amount,
            payer_name=payer_name,
            notes=notes,
            user_id=None,
        )

        flash(f'Credit of ${amount:.2f} added.', 'success')
        return redirect(url_for('customer_detail', customer_id=customer_id))

    except ValidationError as e:
        flash(e.message, 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))
    except Exception as e:
        flash(f'Error adding credit: {str(e)}', 'error')
        return redirect(url_for('customer_detail', customer_id=customer_id))

@app.route('/ledger/<int:ledger_id>/edit', methods=['POST'])
def edit_entry(ledger_id):
    customer_id = request.form.get('customer_id')

    try:
        entry_type = request.form.get('entry_type')

        if entry_type == 'NEW_DEBT':
            # Parse items from form
            items = []
            item_keys = [k for k in request.form.keys() if k.startswith('items[')]

            if not item_keys:
                raise ValidationError("At least one item is required")

            item_indices = sorted(set([int(k.split('[')[1].split(']')[0]) for k in item_keys]))

            for idx in item_indices:
                product_name = request.form.get(f'items[{idx}][product_name]')
                price = request.form.get(f'items[{idx}][price]', 0)
                quantity = request.form.get(f'items[{idx}][quantity]', 1)
                if product_name:
                    items.append({
                        'product_name': product_name,
                        'price': price,
                        'quantity': quantity
                    })

            # Validate all items
            validated_items, total = validate_debt_items(items)
            notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=500)

            db.update_debt_entry(ledger_id, validated_items, notes=notes)
            flash('Debt entry updated.', 'success')
        else:
            # Payment entry - validate amount
            amount = validate_amount(request.form.get('amount', 0), 'Amount')
            notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=500)

            db.update_payment_entry(ledger_id, amount, notes=notes)
            flash('Payment entry updated.', 'success')

        if customer_id:
            return redirect(url_for('customer_detail', customer_id=customer_id))
        return redirect(url_for('dashboard'))

    except ValidationError as e:
        flash(e.message, 'error')
        if customer_id:
            return redirect(url_for('customer_detail', customer_id=customer_id))
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f'An unexpected error occurred: {str(e)}', 'error')
        if customer_id:
            return redirect(url_for('customer_detail', customer_id=customer_id))
        return redirect(url_for('dashboard'))

@app.route('/ledger/<int:ledger_id>/void', methods=['POST'])
def void_entry(ledger_id):
    customer_id = request.form.get('customer_id')
    reason = request.form.get('reason', 'Hidden by user')
    try:
        db.void_entry(ledger_id, reason, user_id=None)
        flash('Entry hidden successfully.', 'success')
    except Exception as e:
        flash(f'Error hiding entry: {str(e)}', 'error')
    if customer_id:
        return redirect(url_for('customer_detail', customer_id=customer_id))
    return redirect(url_for('dashboard'))

@app.route('/ledger/<int:ledger_id>/unvoid', methods=['POST'])
def unvoid_entry(ledger_id):
    customer_id = request.form.get('customer_id')
    try:
        db.unvoid_entry(ledger_id, user_id=None)
        flash('Entry restored successfully.', 'success')
    except Exception as e:
        flash(f'Error restoring entry: {str(e)}', 'error')
    if customer_id:
        return redirect(url_for('customer_detail', customer_id=customer_id))
    return redirect(url_for('dashboard'))

@app.route('/ledger/<int:ledger_id>/delete', methods=['POST'])
def delete_entry(ledger_id):
    customer_id = request.form.get('customer_id')
    try:
        db.delete_ledger_entry(ledger_id)
        flash('Entry permanently deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting entry: {str(e)}', 'error')
    if customer_id:
        return redirect(url_for('customer_detail', customer_id=customer_id))
    return redirect(url_for('dashboard'))

# ============== PRODUCTS ==============

@app.route('/products')
def products():
    products_list = db.get_all_products()
    return render_template('products.html', products=products_list)

@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        try:
            name = validate_string(request.form.get('name'), 'Product name', max_length=200)
            price = validate_amount(request.form.get('price'), 'Price')

            db.add_product(name, price)
            flash(f'Product "{name}" added.', 'success')
            return redirect(url_for('products'))

        except ValidationError as e:
            flash(e.message, 'error')
            return render_template('add_product.html')
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'error')
            return render_template('add_product.html')

    return render_template('add_product.html')

@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    product = db.get_product(product_id)
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))

    if request.method == 'POST':
        try:
            name = validate_string(request.form.get('name'), 'Product name', max_length=200)
            price = validate_amount(request.form.get('price'), 'Price')

            db.update_product(product_id, name, price)
            flash('Product updated.', 'success')
            return redirect(url_for('products'))

        except ValidationError as e:
            flash(e.message, 'error')
            return render_template('edit_product.html', product=product)
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'error')
            return render_template('edit_product.html', product=product)

    return render_template('edit_product.html', product=product)

@app.route('/products/<int:product_id>/delete', methods=['POST'])
def delete_product(product_id):
    db.delete_product(product_id)
    flash('Product deleted.', 'success')
    return redirect(url_for('products'))

@app.route('/api/products/<int:product_id>')
def get_product_api(product_id):
    product = db.get_product(product_id)
    return jsonify(product) if product else (jsonify({'error': 'Not found'}), 404)

# ============== REPORTS ==============

@app.route('/reports')
def reports():
    try:
        report_type = request.args.get('type', 'transactions')
        
        # Handle different report types
        if report_type == 'aging':
            aging_data = db.get_aging_report()
            return render_template('reports_aging.html', aging_data=aging_data)
        
        elif report_type == 'overdue':
            days = request.args.get('days', 30, type=int)
            overdue_customers = db.get_overdue_customers(days)
            return render_template('reports_overdue.html', 
                                 overdue_customers=overdue_customers, 
                                 days=days)
        
        elif report_type == 'daily':
            selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
            daily_stats = db.get_daily_reconciliation(selected_date)
            return render_template('reports_daily.html', 
                                 daily_stats=daily_stats,
                                 selected_date=selected_date)
        
        else:  # Default: transactions report
            # Date range with defaults
            default_end = datetime.now()
            default_start = default_end - timedelta(days=30)
            start_str = request.args.get('start_date', default_start.strftime('%Y-%m-%d'))
            end_str = request.args.get('end_date', default_end.strftime('%Y-%m-%d'))

            # Validate date range
            try:
                validate_date_range(start_str, end_str)
            except ValidationError as e:
                flash(e.message, 'error')
                # Reset to defaults if invalid
                start_str = default_start.strftime('%Y-%m-%d')
                end_str = default_end.strftime('%Y-%m-%d')

            # Validate customer_id if provided
            customer_id = request.args.get('customer_id', '')
            customer_id_int = None

            if customer_id:
                try:
                    customer_id_int = int(customer_id)
                except (ValueError, TypeError):
                    flash('Invalid customer ID', 'error')
                    customer_id = ''

            customers = db.get_all_customers()
            selected_customer = db.get_customer(customer_id_int) if customer_id_int else None

            transactions = db.get_transactions_by_date(start_str, end_str, customer_id_int)
            total_debt = db.get_debt_by_date(start_str, end_str, customer_id_int)

            return render_template('reports.html',
                                 transactions=transactions,
                                 total_debt=total_debt,
                                 customers=customers,
                                 start_date=start_str,
                                 end_date=end_str,
                                 selected_customer_id=customer_id,
                                 selected_customer=selected_customer)

    except Exception as e:
        flash(f'Error loading reports: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

# ============== PDF EXPORTS ==============

@app.route('/reports/export-pdf')
def export_pdf():
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    customer_id = request.args.get('customer_id', '')
    customer_id_int = int(customer_id) if customer_id else None

    # Get customers with their debt totals for the date range (format like all customers report)
    customers_data = db.get_customers_with_debt_by_date_range(start_str, end_str, customer_id_int)
    
    # Calculate total debt from the customers
    total_debt = sum(c['debt'] for c in customers_data)

    pdf_buffer = generate_debt_report_by_date_range(customers_data, total_debt, start_str, end_str)

    filename = f"debt_report_{start_str}_to_{end_str}.pdf"
    if customer_id_int:
        customer = db.get_customer(customer_id_int)
        if customer:
            filename = f"debt_report_{customer['name']}_{start_str}_to_{end_str}.pdf"

    return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/reports/export-aging-pdf')
def export_aging_pdf():
    """Export aging report as PDF"""
    try:
        aging_data = db.get_aging_report()
        
        # Calculate totals
        total_0_30 = sum(c.get('days_0_30', 0) for c in aging_data)
        total_31_60 = sum(c.get('days_31_60', 0) for c in aging_data)
        total_61_90 = sum(c.get('days_61_90', 0) for c in aging_data)
        total_90_plus = sum(c.get('days_90_plus', 0) for c in aging_data)
        grand_total = sum(c.get('total_debt', 0) for c in aging_data)
        
        # Convert to format expected by PDF generator (similar to debt report)
        customers_data = []
        for customer in aging_data:
            customers_data.append({
                'name': customer.get('name', ''),
                'phone': customer.get('phone', ''),
                'debt': customer.get('total_debt', 0),
                'items': []  # Aging report doesn't have items
            })
        
        # Use existing PDF generator with custom title
        pdf_buffer = generate_debt_report_by_date_range(
            customers_data, 
            grand_total, 
            datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d')
        )
        
        filename = f"aging_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e:
        flash(f'Error generating aging report: {str(e)}', 'error')
        return redirect(url_for('reports', type='aging'))

@app.route('/reports/export-overdue-pdf')
def export_overdue_pdf():
    """Export overdue report as PDF"""
    try:
        days = request.args.get('days', 30, type=int)
        overdue_customers = db.get_overdue_customers(days)
        
        # Calculate total
        total_debt = sum(c.get('debt', 0) for c in overdue_customers)
        
        # Convert to format expected by PDF generator
        customers_data = []
        for customer in overdue_customers:
            customers_data.append({
                'name': customer.get('name', ''),
                'phone': customer.get('phone', ''),
                'debt': customer.get('debt', 0),
                'items': []  # Overdue report doesn't have items
            })
        
        # Use existing PDF generator
        pdf_buffer = generate_debt_report_by_date_range(
            customers_data,
            total_debt,
            datetime.now().strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d')
        )
        
        filename = f"overdue_report_{days}days_{datetime.now().strftime('%Y%m%d')}.pdf"
        return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e:
        flash(f'Error generating overdue report: {str(e)}', 'error')
        return redirect(url_for('reports', type='overdue'))

@app.route('/customers/<int:customer_id>/export-pdf')
def export_customer_pdf(customer_id):
    customer = db.get_customer(customer_id)
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))

    ledger = db.get_customer_ledger(customer_id, include_voided=False)
    total_debt = db.get_customer_balance(customer_id)

    # Printed statement: only OPEN/PARTIAL purchases that still have a balance due (exclude $0 / credit-covered)
    pdf_ledger = []
    for entry in ledger:
        if entry.get('entry_type') != 'NEW_DEBT' or entry.get('payment_status') not in ('OPEN', 'PARTIAL'):
            continue
        remaining = entry.get('remaining_amount') if entry.get('remaining_amount') is not None else entry.get('amount', 0)
        if (remaining or 0) <= 0:
            continue
        pdf_ledger.append(entry)

    total_remaining = sum(
        entry.get('remaining_amount', entry.get('amount', 0)) or entry.get('amount', 0)
        for entry in pdf_ledger
    )

    pdf_buffer = generate_customer_report(
        customer, pdf_ledger, [], total_debt,
        total_debts=total_remaining, total_payments=0,
        statements_only=True
    )

    filename = f"report_{customer['name']}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

@app.route('/reports/download-all-debts')
def download_all_debts_pdf():
    """Download PDF report of all customers with debts"""
    try:
        customers = db.get_customers_with_debt_and_items()
        total_debt = db.get_total_debt_all()
        
        if not customers:
            flash('No customers with debts found.', 'info')
            return redirect(url_for('dashboard'))
        
        pdf_buffer = generate_all_customers_debt_report(customers, total_debt)
        filename = f"daily_report_{datetime.now().strftime('%m/%d/%Y')}.pdf"
        return send_file(pdf_buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')
    except Exception as e:
        import traceback
        print(f"Error generating PDF report: {e}")
        print(traceback.format_exc())
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

# ============== DATA MANAGEMENT ==============

@app.route('/admin/delete-all-customers', methods=['POST'])
def delete_all_customers():
    """
    Delete all customer data - use with caution!
    
    WARNING: This route is unprotected and should be secured in production.
    Consider adding authentication/authorization checks before allowing access.
    """
    # Basic protection: require confirmation parameter
    confirm = request.form.get('confirm', '').lower()
    if confirm != 'delete all':
        flash('Deletion requires confirmation. Please type "delete all" to confirm.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        db.delete_all_customer_data()
        flash('All customer data has been deleted successfully.', 'success')
    except Exception as e:
        import traceback
        print(f"Error deleting customer data: {e}")
        print(traceback.format_exc())
        flash(f'Error deleting customer data: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

# ============== DONATIONS ==============

@app.route('/donations')
def donations():
    donations_list = db.get_all_donations()
    total_donations = db.get_total_donations()
    total_used = db.get_total_donations_used()
    total_available = db.get_total_donations_available()
    usage_history = db.get_donation_usage_history()
    
    anonymous_available = db.get_anonymous_donations_available()
    return render_template('donations.html',
                         donations=donations_list,
                         total_donations=total_donations,
                         total_used=total_used,
                         total_available=total_available,
                         anonymous_available=anonymous_available,
                         usage_history=usage_history)

@app.route('/donations/add', methods=['GET', 'POST'])
def add_donation():
    if request.method == 'POST':
        try:
            amount = validate_amount(request.form.get('amount'), 'Donation amount')
            donor_name = validate_string(request.form.get('donor_name', ''), 'Donor name', required=False, max_length=200)
            notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=500)

            db.add_donation(amount, donor_name=donor_name, notes=notes)
            flash(f'Donation of ${amount:.2f} added successfully.', 'success')
            return redirect(url_for('donations'))

        except ValidationError as e:
            flash(e.message, 'error')
            donor_names = db.get_unique_donor_names()
            return render_template('add_donation.html', donor_names=donor_names)
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'error')
            donor_names = db.get_unique_donor_names()
            return render_template('add_donation.html', donor_names=donor_names)

    donor_names = db.get_unique_donor_names()
    return render_template('add_donation.html', donor_names=donor_names)

@app.route('/donations/adjust', methods=['POST'])
def adjust_donations():
    try:
        amount = validate_amount(request.form.get('amount'), 'Adjustment amount')
        notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=500)
        result = db.adjust_donations_anonymous(amount, notes=notes)
        if result['success']:
            flash(f'${amount:.2f} deducted from anonymous donations successfully.', 'success')
        else:
            flash(result['message'], 'error')
    except ValidationError as e:
        flash(e.message, 'error')
    except Exception as e:
        flash(f'An unexpected error occurred: {str(e)}', 'error')
    return redirect(url_for('donations'))


@app.route('/donations/<int:donation_id>/use', methods=['GET', 'POST'])
def use_donation(donation_id):
    donation = db.get_donation(donation_id)
    if not donation:
        flash('Donation not found.', 'error')
        return redirect(url_for('donations'))

    if donation['amount_remaining'] <= 0:
        flash('This donation has no remaining funds.', 'error')
        return redirect(url_for('donations'))

    if request.method == 'POST':
        try:
            # Validate customer_id
            customer_id_str = request.form.get('customer_id')
            if not customer_id_str:
                raise ValidationError("Customer is required", "customer_id")

            try:
                customer_id = int(customer_id_str)
            except (ValueError, TypeError):
                raise ValidationError("Invalid customer ID", "customer_id")

            # Validate customer exists and is active
            customer = db.get_customer(customer_id)
            validate_customer_active(customer)

            # Validate donation usage amount
            amount = validate_donation_usage(donation, request.form.get('amount'))
            notes = validate_string(request.form.get('notes', ''), 'Notes', required=False, max_length=500)

            result = db.use_donation(donation_id, customer_id, amount, notes=notes)
            if result['success']:
                flash(f'Donation of ${amount:.2f} applied to customer successfully.', 'success')
                return redirect(url_for('customer_detail', customer_id=customer_id))
            else:
                flash(result['message'], 'error')
                return redirect(url_for('use_donation', donation_id=donation_id))

        except ValidationError as e:
            flash(e.message, 'error')
            return redirect(url_for('use_donation', donation_id=donation_id))
        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'error')
            return redirect(url_for('use_donation', donation_id=donation_id))

    customers = db.get_customers_with_debt()
    return render_template('use_donation.html', donation=donation, customers=customers)

# ============== SETTINGS ==============

@app.route('/settings', methods=['GET'])
def settings():
    # Get system statistics
    import os
    from datetime import datetime
    
    customers = db.get_all_customers()
    total_debt = db.get_total_debt_all()
    total_donations = db.get_total_donations()
    total_donations_available = db.get_total_donations_available()
    total_payments = db.get_total_payments_all()

    system_info = {
        'total_customers': len(customers),
        'total_debt': total_debt,
        'total_payments': total_payments,
        'total_donations': total_donations,
        'total_donations_available': total_donations_available,
        'customers_with_debt': len([c for c in customers if db.get_customer_balance(c['id']) > 0])
    }
    
    return render_template('settings.html', system_info=system_info)

@app.route('/settings/export-backup')
def export_backup():
    """Export all data as CSV backup"""
    try:
        csv_data = db.export_all_data_to_csv()
        filename = f'pharmacy_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        response = send_file(
            io.BytesIO(csv_data.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        return response
    except Exception as e:
        flash(f'Error exporting backup: {str(e)}', 'error')
        return redirect(url_for('settings'))

@app.route('/settings/import-backup', methods=['POST'])
def import_backup():
    """Import data from CSV backup file"""
    try:
        if 'backup_file' not in request.files:
            flash('No file selected.', 'error')
            return redirect(url_for('settings'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('settings'))
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file.', 'error')
            return redirect(url_for('settings'))
        
        # Read file content
        csv_content = file.read().decode('utf-8')
        
        # Import data
        result = db.import_data_from_csv(csv_content)
        
        if result['success']:
            imported = result['imported']
            summary = f"Imported: {imported['customers']} customers, {imported['products']} products, {imported['donations']} donations"
            flash(f'Backup restored successfully! {summary}', 'success')
        else:
            errors = result.get('errors', [])
            flash(f'Import completed with errors: {"; ".join(errors)}', 'error')
        
        return redirect(url_for('settings'))
    except Exception as e:
        flash(f'Error importing backup: {str(e)}', 'error')
        return redirect(url_for('settings'))
    
@app.route('/admin/create-demo-data', methods=['POST'])
def create_demo_data():
    """Create demo data for testing"""
    try:
        db.create_demo_data()
        flash('Demo data created successfully!', 'success')
    except Exception as e:
        flash(f'Error creating demo data: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

# ============== AI CHATBOT ==============

def _fuzzy_find_customer(name):
    """Find a customer by name with fuzzy matching. Returns list of matches (best first)."""
    from difflib import SequenceMatcher
    # Try exact substring match first
    results = db.search_customers(name)
    if results:
        return results
    # Fuzzy match against all active customers
    all_customers = db.get_all_customers()
    name_lower = name.lower().strip()
    scored = []
    for c in all_customers:
        ratio = SequenceMatcher(None, name_lower, c['name'].lower()).ratio()
        # Also check if all words from input appear as prefixes in customer name
        input_words = name_lower.split()
        customer_words = c['name'].lower().split()
        prefix_match = all(
            any(cw.startswith(iw) or iw.startswith(cw) for cw in customer_words)
            for iw in input_words
        )
        if prefix_match:
            ratio = max(ratio, 0.75)
        if ratio >= 0.6:
            scored.append((ratio, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a natural language message via the AI chatbot and execute the action."""
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({"reply": "Please enter a message."}), 400

    user_message = data['message'].strip()
    result = process_message(user_message)

    # Handle errors from the AI layer
    if result.get("action") == "error":
        return jsonify({"reply": result["error"]})

    if result.get("action") == "unknown":
        return jsonify({"reply": result.get("error", "I didn't understand that. Type 'help' to see what I can do.")})

    action = result["action"]
    name = result.get("name", "")
    amount = result.get("amount", 0)

    try:
        return jsonify({"reply": _handle_chat_action(action, name, amount, result), "action": action})
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})


def _handle_chat_action(action, name, amount, result):
    """Execute a chatbot action and return a reply string."""

    # ---- HELP ----
    if action == "help":
        return (
            "Here's what I can do:\n"
            "- \"[name] owes [amount]\" — add debt\n"
            "- \"[name] paid [amount]\" — record payment\n"
            "- \"How much does [name] owe?\" — check balance\n"
            "- \"Show details for [name]\" — customer info\n"
            "- \"Show [name]'s history\" — transaction history\n"
            "- \"List all customers\" — all customers\n"
            "- \"Who owes the most?\" — top debtors\n"
            "- \"List all products\" — product catalog\n"
            "- \"Add product [name] at [price]\" — new product\n"
            "- \"What's the total debt?\" — system total\n"
            "- \"Show today's summary\" — daily report\n"
            "- \"Who is overdue?\" — overdue customers\n"
            "- \"Show recent activity\" — latest transactions\n"
            "- \"Aging report\" — debt aging breakdown\n"
            "- \"Weekly stats\" — week summary\n"
            "- \"Donation balance\" — available donations\n"
            "- \"Add donation [amount] from [name]\" — record donation\n"
            "- \"[name]'s uncle paid [amount] for him\" — third-party credit\n"
            "- \"Use donation for [name] [amount]\" — apply donation to debt\n"
            "- \"What happened on March 15?\" — date lookup\n"
            "Works in English and Arabic!"
        )

    # ---- GET DEBT ----
    if action == "get_debt":
        customers = _fuzzy_find_customer(name)
        if not customers:
            return f"No customer found matching '{name}'."
        customer = customers[0]
        balance = db.get_customer_balance(customer['id'])
        if balance > 0:
            return f"{customer['name']} owes ${balance:.2f}."
        elif balance < 0:
            return f"{customer['name']} has a credit of ${abs(balance):.2f}."
        return f"{customer['name']} has no outstanding debt."

    # ---- ADD DEBT ----
    if action == "add_debt":
        customers = _fuzzy_find_customer(name)
        if not customers:
            customer_id = db.add_customer(name)
            customer_name = name
        else:
            customer_id = customers[0]['id']
            customer_name = customers[0]['name']
        product = result.get("product", "") or "Chatbot Entry"
        items = [{"product_name": product, "price": amount, "quantity": 1}]
        db.add_debt(customer_id, items, description="Added via AI chatbot")
        new_balance = db.get_customer_balance(customer_id)
        return f"Added ${amount:.2f} debt for {customer_name}. Total balance: ${new_balance:.2f}."

    # ---- PAY DEBT ----
    if action == "pay_debt":
        customers = _fuzzy_find_customer(name)
        if not customers:
            return f"No customer found matching '{name}'."
        customer = customers[0]
        db.add_payment(customer['id'], amount, notes="Paid via AI chatbot")
        new_balance = db.get_customer_balance(customer['id'])
        return f"Recorded ${amount:.2f} payment from {customer['name']}. Remaining balance: ${new_balance:.2f}."

    # ---- LIST CUSTOMERS ----
    if action == "list_customers":
        customers = db.get_customers_with_debt()
        if not customers:
            return "No customers found."
        lines = []
        for c in customers[:15]:
            debt = c.get('debt', 0)
            status = f"${debt:.2f}" if debt > 0 else "No debt"
            lines.append(f"- {c['name']}: {status}")
        total = len(customers)
        reply = "\n".join(lines)
        if total > 15:
            reply += f"\n...and {total - 15} more."
        return reply

    # ---- CUSTOMER DETAIL ----
    if action == "customer_detail":
        customers = _fuzzy_find_customer(name)
        if not customers:
            return f"No customer found matching '{name}'."
        c = customers[0]
        balance = db.get_customer_balance(c['id'])
        lines = [
            f"Name: {c['name']}",
            f"Phone: {c.get('phone') or 'N/A'}",
            f"Email: {c.get('email') or 'N/A'}",
            f"Address: {c.get('address') or 'N/A'}",
            f"Credit Limit: ${c.get('credit_limit', 500):.2f}",
            f"Balance: ${balance:.2f}" if balance >= 0 else f"Credit: ${abs(balance):.2f}",
            f"Status: {'Active' if c.get('is_active', 1) else 'Inactive'}",
        ]
        return "\n".join(lines)

    # ---- ADD CUSTOMER ----
    if action == "add_customer":
        existing = _fuzzy_find_customer(name)
        if existing:
            return f"Customer '{existing[0]['name']}' already exists with balance ${db.get_customer_balance(existing[0]['id']):.2f}."
        phone = result.get("phone", "")
        customer_id = db.add_customer(name, phone=phone if phone else None)
        return f"Customer '{name}' created successfully (ID: {customer_id})."

    # ---- REMOVE CUSTOMER ----
    if action == "remove_customer":
        customers = _fuzzy_find_customer(name)
        if not customers:
            return f"No customer found matching '{name}'."
        customer = customers[0]
        balance = db.get_customer_balance(customer['id'])
        if balance > 0:
            return f"Cannot remove {customer['name']} — they still owe ${balance:.2f}. Clear their debt first."
        db.deactivate_customer(customer['id'])
        return f"Customer '{customer['name']}' has been removed."

    # ---- TOP DEBTORS ----
    if action == "top_debtors":
        customers = db.get_customers_with_debt()
        debtors = [c for c in customers if c.get('debt', 0) > 0]
        if not debtors:
            return "No customers with outstanding debt."
        debtors.sort(key=lambda c: c['debt'], reverse=True)
        lines = []
        for i, c in enumerate(debtors[:10], 1):
            lines.append(f"{i}. {c['name']}: ${c['debt']:.2f}")
        return "Top debtors:\n" + "\n".join(lines)

    # ---- CUSTOMER HISTORY ----
    if action == "customer_history":
        customers = _fuzzy_find_customer(name)
        if not customers:
            return f"No customer found matching '{name}'."
        customer = customers[0]
        ledger = db.get_customer_ledger(customer['id'])
        if not ledger:
            return f"No transaction history for {customer['name']}."
        lines = [f"History for {customer['name']}:"]
        for entry in ledger[:10]:
            etype = entry['entry_type']
            amt = entry['amount']
            date = entry.get('created_at', '')[:10]
            if etype == 'NEW_DEBT':
                lines.append(f"- {date}: Debt +${amt:.2f}")
            elif etype == 'PAYMENT':
                lines.append(f"- {date}: Payment -${amt:.2f}")
            else:
                lines.append(f"- {date}: {etype} ${amt:.2f}")
        if len(ledger) > 10:
            lines.append(f"...and {len(ledger) - 10} more entries.")
        balance = db.get_customer_balance(customer['id'])
        lines.append(f"Current balance: ${balance:.2f}")
        return "\n".join(lines)

    # ---- LIST PRODUCTS ----
    if action == "list_products":
        products = db.get_all_products()
        if not products:
            return "No products found."
        lines = []
        for p in products[:20]:
            cat = f" ({p['category']})" if p.get('category') else ""
            lines.append(f"- {p['name']}: ${p['price']:.2f}{cat}")
        if len(products) > 20:
            lines.append(f"...and {len(products) - 20} more.")
        return "\n".join(lines)

    # ---- PRODUCT DETAIL ----
    if action == "product_detail":
        products = db.get_all_products()
        name_lower = name.lower()
        match = None
        for p in products:
            if name_lower in p['name'].lower():
                match = p
                break
        if not match:
            return f"No product found matching '{name}'."
        cat = f"Category: {match['category']}" if match.get('category') else "No category"
        rx = "Yes" if match.get('is_prescription') else "No"
        return f"{match['name']}\nPrice: ${match['price']:.2f}\n{cat}\nPrescription: {rx}"

    # ---- ADD PRODUCT ----
    if action == "add_product":
        product_id = db.add_product(name, amount)
        return f"Product '{name}' added at ${amount:.2f} (ID: {product_id})."

    # ---- TOTAL DEBT ----
    if action == "total_debt":
        total = db.get_total_debt_all()
        customers = db.get_customers_with_debt()
        count = len([c for c in customers if c.get('debt', 0) > 0])
        return f"Total debt across all customers: ${total:.2f}\nCustomers with debt: {count}"

    # ---- DAILY SUMMARY ----
    if action == "daily_summary":
        stats = db.get_daily_reconciliation()
        debt = float(stats.get('total_debt') or 0)
        payments = float(stats.get('total_payments') or 0)
        count_debts = stats.get('debt_count', 0)
        count_payments = stats.get('payment_count', 0)
        return (
            f"Today's Summary:\n"
            f"Debts added: {count_debts} (${debt:.2f})\n"
            f"Payments received: {count_payments} (${payments:.2f})\n"
            f"Net: ${debt - payments:.2f}"
        )

    # ---- TODAY'S DEBTS ----
    if action == "today_debts":
        today = datetime.now().strftime('%Y-%m-%d')
        transactions = db.get_transactions_by_date(today, today)
        debts = [t for t in transactions if t.get('entry_type') == 'NEW_DEBT']
        if not debts:
            return "No debts were added today."
        lines = [f"Debts added today ({len(debts)}):"]
        for t in debts:
            product = t.get('product_name') or t.get('description') or ''
            product_str = f" ({product})" if product else ""
            lines.append(f"- {t['customer_name']}: ${float(t.get('amount', 0)):.2f}{product_str}")
        return "\n".join(lines)

    # ---- TODAY'S PAYMENTS ----
    if action == "today_payments":
        today = datetime.now().strftime('%Y-%m-%d')
        transactions = db.get_transactions_by_date(today, today)
        payments = [t for t in transactions if t.get('entry_type') == 'PAYMENT']
        if not payments:
            return "No payments were received today."
        lines = [f"Payments received today ({len(payments)}):"]
        for t in payments:
            lines.append(f"- {t['customer_name']}: ${float(t.get('amount', 0)):.2f}")
        return "\n".join(lines)

    # ---- TODAY'S NEW CUSTOMERS ----
    if action == "today_customers":
        today = datetime.now().strftime('%Y-%m-%d')
        all_customers = db.get_all_customers()
        added_today = [c for c in all_customers if str(c.get('created_at', ''))[:10] == today]
        if not added_today:
            return "No new customers were added today."
        lines = [f"Customers added today ({len(added_today)}):"]
        for c in added_today:
            lines.append(f"- {c['name']}")
        return "\n".join(lines)

    # ---- OVERDUE CUSTOMERS ----
    if action == "overdue_customers":
        overdue = db.get_overdue_customers()
        if not overdue:
            return "No overdue customers. Everyone is on time!"
        lines = ["Overdue customers (30+ days):"]
        for c in overdue[:10]:
            lines.append(f"- {c['name']}: ${c.get('total_debt', c.get('debt', 0)):.2f} (oldest: {c.get('oldest_date', 'N/A')[:10]})")
        if len(overdue) > 10:
            lines.append(f"...and {len(overdue) - 10} more.")
        return "\n".join(lines)

    # ---- OVER LIMIT CUSTOMERS ----
    if action == "over_limit_customers":
        over = db.get_over_limit_customers()
        if not over:
            return "No customers over their credit limit."
        lines = ["Customers over credit limit:"]
        for c in over[:10]:
            lines.append(f"- {c['name']}: ${c.get('debt', 0):.2f} / limit ${c.get('credit_limit', 500):.2f}")
        return "\n".join(lines)

    # ---- RECENT ACTIVITY ----
    if action == "recent_activity":
        activity = db.get_recent_activity(10)
        if not activity:
            return "No recent activity."
        lines = ["Recent activity:"]
        for a in activity:
            date = a.get('created_at', '')[:10]
            etype = a.get('entry_type', '')
            amt = a.get('amount', 0)
            cname = a.get('customer_name', 'Unknown')
            if etype == 'NEW_DEBT':
                lines.append(f"- {date}: {cname} +${amt:.2f} (debt)")
            elif etype == 'PAYMENT':
                lines.append(f"- {date}: {cname} -${amt:.2f} (payment)")
            else:
                lines.append(f"- {date}: {cname} ${amt:.2f} ({etype})")
        return "\n".join(lines)

    # ---- AGING REPORT ----
    if action == "aging_report":
        aging = db.get_aging_report()
        if not aging:
            return "No aging data available."
        lines = ["Debt Aging Report:"]
        for entry in aging[:10]:
            cname = entry.get('customer_name', entry.get('name', 'Unknown'))
            current = float(entry.get('current', 0))
            days_30 = float(entry.get('days_30', 0))
            days_60 = float(entry.get('days_60', 0))
            days_90 = float(entry.get('days_90', 0))
            total = current + days_30 + days_60 + days_90
            if total > 0:
                lines.append(f"- {cname}: ${total:.2f} (Current: ${current:.2f}, 30d: ${days_30:.2f}, 60d: ${days_60:.2f}, 90d+: ${days_90:.2f})")
        if len(lines) == 1:
            return "No outstanding aging debt."
        return "\n".join(lines)

    # ---- WEEKLY STATS ----
    if action == "weekly_stats":
        weekly_debt = 0
        weekly_payments = 0
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            stats = db.get_daily_reconciliation(date)
            weekly_debt += float(stats.get('total_debt') or 0)
            weekly_payments += float(stats.get('total_payments') or 0)
        return (
            f"This Week's Stats (last 7 days):\n"
            f"Total debts added: ${weekly_debt:.2f}\n"
            f"Total payments received: ${weekly_payments:.2f}\n"
            f"Net: ${weekly_debt - weekly_payments:.2f}"
        )

    # ---- DONATION BALANCE ----
    if action == "donation_balance":
        available = db.get_total_donations_available()
        total = db.get_total_donations()
        used = db.get_total_donations_used()
        return (
            f"Donations:\n"
            f"Total received: ${total:.2f}\n"
            f"Used: ${used:.2f}\n"
            f"Available: ${available:.2f}"
        )

    # ---- ADD DONATION ----
    if action == "add_donation":
        donor = result.get("donor", "")
        db.add_donation(amount, donor_name=donor if donor else None)
        available = db.get_total_donations_available()
        donor_text = f" from {donor}" if donor else ""
        return f"Donation of ${amount:.2f}{donor_text} recorded. Total available: ${available:.2f}."

    # ---- ADD CREDIT (third-party payment) ----
    if action == "add_credit":
        customers = _fuzzy_find_customer(name)
        if not customers:
            return f"No customer found matching '{name}'."
        customer = customers[0]
        payer = result.get("payer", "")
        db.add_credit(customer['id'], amount, payer_name=payer if payer else None, notes="Added via AI chatbot")
        new_balance = db.get_customer_balance(customer['id'])
        payer_text = f" from {payer}" if payer else ""
        if new_balance > 0:
            return f"Credit of ${amount:.2f}{payer_text} applied to {customer['name']}. Remaining balance: ${new_balance:.2f}."
        elif new_balance < 0:
            return f"Credit of ${amount:.2f}{payer_text} applied to {customer['name']}. Customer now has ${abs(new_balance):.2f} in credit."
        return f"Credit of ${amount:.2f}{payer_text} applied to {customer['name']}. Balance is now $0.00."

    # ---- USE DONATION ----
    if action == "use_donation":
        customers = _fuzzy_find_customer(name)
        if not customers:
            return f"No customer found matching '{name}'."
        customer = customers[0]
        balance = db.get_customer_balance(customer['id'])
        if balance <= 0:
            return f"{customer['name']} has no outstanding debt to apply donations to."
        if amount > balance:
            return f"Amount ${amount:.2f} exceeds {customer['name']}'s debt of ${balance:.2f}."
        # Find an available donation to use
        available = db.get_available_donations()
        if not available:
            return "No donations available to use."
        # Find a donation with enough remaining funds
        donation = None
        for d in available:
            if d['amount_remaining'] >= amount:
                donation = d
                break
        if not donation:
            # Try to use the largest available
            available.sort(key=lambda d: d['amount_remaining'], reverse=True)
            total_avail = sum(d['amount_remaining'] for d in available)
            if total_avail < amount:
                return f"Not enough donation funds. Total available: ${total_avail:.2f}, requested: ${amount:.2f}."
            donation = available[0]
            if donation['amount_remaining'] < amount:
                return f"Largest single donation has ${donation['amount_remaining']:.2f}. Try a smaller amount or split manually."
        result_data = db.use_donation(donation['id'], customer['id'], amount, notes="Applied via AI chatbot")
        if result_data.get('success'):
            new_balance = db.get_customer_balance(customer['id'])
            donor_name = donation.get('donor_name') or 'Anonymous'
            return f"Applied ${amount:.2f} from donation (by {donor_name}) to {customer['name']}. Remaining balance: ${new_balance:.2f}."
        return f"Could not apply donation: {result_data.get('message', 'Unknown error')}"

    # ---- DATE LOOKUP ----
    if action == "date_lookup":
        date = result.get("date", "")
        transactions = db.get_transactions_by_date(date, date)
        if not transactions:
            return f"No transactions found on {date}."
        lines = [f"Transactions on {date}:"]
        total_debt = 0
        total_payments = 0
        for t in transactions[:15]:
            etype = t['entry_type']
            amt = t['amount']
            cname = t.get('customer_name', 'Unknown')
            if etype == 'NEW_DEBT':
                lines.append(f"- {cname}: +${amt:.2f} (debt)")
                total_debt += amt
            elif etype == 'PAYMENT':
                lines.append(f"- {cname}: -${amt:.2f} (payment)")
                total_payments += amt
            else:
                lines.append(f"- {cname}: ${amt:.2f} ({etype})")
        if len(transactions) > 15:
            lines.append(f"...and {len(transactions) - 15} more.")
        lines.append(f"\nTotal: ${total_debt:.2f} in debts, ${total_payments:.2f} in payments")
        return "\n".join(lines)

    return "I didn't understand that. Type 'help' to see what I can do."


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    app.run(debug=True, port=port)
