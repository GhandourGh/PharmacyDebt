import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
import hashlib
import os
import csv
import io

DATABASE = 'pharmacy.db'

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

def hash_password(password):
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        # Users table (for role-based access)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('clerk', 'manager', 'admin')),
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Customers table (enhanced with credit limit)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                address TEXT,
                credit_limit REAL DEFAULT 500.00,
                grace_period_days INTEGER DEFAULT 7,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                profile_image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add profile_image column if it doesn't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE customers ADD COLUMN profile_image TEXT')
            conn.commit()
        except:
            pass  # Column already exists

        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT,
                is_prescription INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Ledger entries (unified transaction system)
        # Types: NEW_DEBT, PAYMENT, ADJUSTMENT, REFUND, WRITE_OFF, VOID
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                entry_type TEXT NOT NULL CHECK(entry_type IN ('NEW_DEBT', 'PAYMENT', 'ADJUSTMENT', 'REFUND', 'WRITE_OFF', 'VOID')),
                amount REAL NOT NULL,
                balance_after REAL,
                rx_number TEXT,
                description TEXT,
                notes TEXT,
                payment_method TEXT CHECK(payment_method IN ('CASH', 'CARD', 'CHECK', 'CREDIT', 'SPLIT', NULL)),
                reference_id INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_voided INTEGER DEFAULT 0,
                voided_by INTEGER,
                voided_at TIMESTAMP,
                void_reason TEXT,
                is_deleted INTEGER DEFAULT 0,
                deleted_at TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers (id),
                FOREIGN KEY (created_by) REFERENCES users (id),
                FOREIGN KEY (voided_by) REFERENCES users (id),
                FOREIGN KEY (reference_id) REFERENCES ledger (id)
            )
        ''')
        
        # Add is_deleted column if it doesn't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE ledger ADD COLUMN is_deleted INTEGER DEFAULT 0')
            conn.commit()
        except:
            pass  # Column already exists
        
        # Add deleted_at column if it doesn't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE ledger ADD COLUMN deleted_at TIMESTAMP')
            conn.commit()
        except:
            pass  # Column already exists

        # Ledger items (line items for each debt entry)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ledger_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ledger_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                rx_number TEXT,
                FOREIGN KEY (ledger_id) REFERENCES ledger (id)
            )
        ''')

        # Audit log (non-editable record of all changes)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id INTEGER,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Donations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                donor_name TEXT,
                notes TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Donation usage table (tracks when donations are used for customers)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS donation_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                donation_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                amount_used REAL NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (donation_id) REFERENCES donations (id),
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')

        # Create default admin user if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
            ''', ('admin', hash_password('admin123'), 'Administrator', 'admin'))

        # Create default settings
        default_settings = [
            ('default_credit_limit', '500.00'),
            ('default_grace_period', '7'),
            ('overdue_threshold_days', '30'),
            ('auto_archive_days', '90'),
            ('low_balance_alert', '50.00'),
        ]
        for key, value in default_settings:
            cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, value))

        conn.commit()

# ============== USER OPERATIONS ==============

def authenticate_user(username, password):
    """Authenticate user and return user dict if valid"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, full_name, role, is_active
            FROM users WHERE username = ? AND password_hash = ? AND is_active = 1
        ''', (username, hash_password(password)))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, full_name, role, is_active FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_users():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY full_name')
        return [dict(row) for row in cursor.fetchall()]

def add_user(username, password, full_name, role):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        ''', (username, hash_password(password), full_name, role))
        conn.commit()
        return cursor.lastrowid

def update_user(user_id, full_name, role, is_active):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET full_name = ?, role = ?, is_active = ? WHERE id = ?
        ''', (full_name, role, is_active, user_id))
        conn.commit()

def change_password(user_id, new_password):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (hash_password(new_password), user_id))
        conn.commit()

# ============== CUSTOMER OPERATIONS ==============

def add_customer(name, phone=None, email=None, address=None, credit_limit=500.00, notes=None, profile_image=None):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO customers (name, phone, email, address, credit_limit, notes, profile_image)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, phone, email, address, credit_limit, notes, profile_image))
        conn.commit()
        return cursor.lastrowid

def get_all_customers():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM customers WHERE is_active = 1 ORDER BY name')
        return [dict(row) for row in cursor.fetchall()]

def get_customer(customer_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_customer(customer_id, name, phone=None, email=None, address=None, credit_limit=500.00, notes=None, profile_image=None):
    with get_db() as conn:
        cursor = conn.cursor()
        if profile_image is not None:
            cursor.execute('''
                UPDATE customers SET name = ?, phone = ?, email = ?, address = ?, credit_limit = ?, notes = ?, profile_image = ?
                WHERE id = ?
            ''', (name, phone, email, address, credit_limit, notes, profile_image, customer_id))
        else:
            cursor.execute('''
                UPDATE customers SET name = ?, phone = ?, email = ?, address = ?, credit_limit = ?, notes = ?
                WHERE id = ?
            ''', (name, phone, email, address, credit_limit, notes, customer_id))
        conn.commit()

def deactivate_customer(customer_id):
    """Soft delete - deactivate instead of hard delete"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE customers SET is_active = 0 WHERE id = ?', (customer_id,))
        conn.commit()

def search_customers(query):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM customers
            WHERE is_active = 1 AND (name LIKE ? OR phone LIKE ?)
            ORDER BY name
        ''', (f'%{query}%', f'%{query}%'))
        return [dict(row) for row in cursor.fetchall()]

# ============== PRODUCT OPERATIONS ==============

def add_product(name, price, category=None, is_prescription=0):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (name, price, category, is_prescription)
            VALUES (?, ?, ?, ?)
        ''', (name, price, category, is_prescription))
        conn.commit()
        return cursor.lastrowid

def get_all_products():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM products ORDER BY name')
        return [dict(row) for row in cursor.fetchall()]

def get_product(product_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_product(product_id, name, price, category=None, is_prescription=0):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products SET name = ?, price = ?, category = ?, is_prescription = ?
            WHERE id = ?
        ''', (name, price, category, is_prescription, product_id))
        conn.commit()

def delete_product(product_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()

# ============== LEDGER OPERATIONS ==============

def get_customer_balance(customer_id):
    """Calculate current balance for a customer (voided and deleted entries still count)"""
    with get_db() as conn:
        cursor = conn.cursor()
        # Include voided and deleted entries in balance calculation (they're just visual/hidden)
        cursor.execute('''
            SELECT COALESCE(SUM(
                CASE
                    WHEN entry_type IN ('NEW_DEBT', 'ADJUSTMENT') THEN amount
                    WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') THEN -amount
                    ELSE 0
                END
            ), 0) as balance
            FROM ledger WHERE customer_id = ?
        ''', (customer_id,))
        return cursor.fetchone()['balance']

def add_debt(customer_id, items, rx_number=None, description=None, notes=None, user_id=None, debt_date=None):
    """Add a new debt entry with validation. debt_date is optional YYYY-MM-DD string."""
    # Secondary validation layer - ensure data integrity at database level
    customer = get_customer(customer_id)
    if not customer:
        raise ValueError("Customer not found")
    if not customer.get('is_active', True):
        raise ValueError("Cannot add debt to deactivated customer")
    if not items or len(items) == 0:
        raise ValueError("At least one item is required")

    with get_db() as conn:
        cursor = conn.cursor()

        # Calculate total with validation
        total = 0
        for item in items:
            price = float(item.get('price', 0))
            quantity = int(item.get('quantity', 1))
            if price <= 0:
                raise ValueError(f"Invalid price for item: {item.get('product_name')}")
            if quantity <= 0:
                raise ValueError(f"Invalid quantity for item: {item.get('product_name')}")
            total += price * quantity

        # Get current balance and add new debt
        current_balance = get_customer_balance(customer_id)
        new_balance = current_balance + total

        # Use provided date or current timestamp
        if debt_date:
            timestamp = debt_date + ' ' + datetime.now().strftime('%H:%M:%S')
        else:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert ledger entry with explicit local timestamp
        cursor.execute('''
            INSERT INTO ledger (customer_id, entry_type, amount, balance_after, rx_number, description, notes, created_by, created_at)
            VALUES (?, 'NEW_DEBT', ?, ?, ?, ?, ?, ?, ?)
        ''', (customer_id, total, new_balance, rx_number, description, notes, user_id, timestamp))
        ledger_id = cursor.lastrowid

        # Insert line items
        for item in items:
            cursor.execute('''
                INSERT INTO ledger_items (ledger_id, product_name, price, quantity, rx_number)
                VALUES (?, ?, ?, ?, ?)
            ''', (ledger_id, item['product_name'], item['price'], item.get('quantity', 1), item.get('rx_number')))

        # Log audit
        log_audit(user_id, 'ADD_DEBT', 'ledger', ledger_id, None, f'Amount: {total}', conn=conn)

        conn.commit()
        return ledger_id

def add_payment(customer_id, amount, payment_method='CASH', notes=None, user_id=None):
    """Record a payment with validation"""
    # Secondary validation layer - ensure data integrity at database level
    customer = get_customer(customer_id)
    if not customer:
        raise ValueError("Customer not found")
    if not customer.get('is_active', True):
        raise ValueError("Cannot add payment to deactivated customer")
    if amount is None or amount <= 0:
        raise ValueError("Payment amount must be positive")

    with get_db() as conn:
        cursor = conn.cursor()

        current_balance = get_customer_balance(customer_id)

        # Prevent overpayment and payments on zero/negative balance
        if current_balance <= 0:
            if current_balance < 0:
                raise ValueError(f"Customer has a credit balance of ${abs(current_balance):.2f}. Cannot accept additional payments.")
            else:
                raise ValueError("Customer has no outstanding balance to pay")
        
        if amount > current_balance:
            raise ValueError(f"Payment amount (${amount:.2f}) exceeds current balance (${current_balance:.2f}). Maximum payment allowed: ${current_balance:.2f}")

        new_balance = current_balance - amount

        cursor.execute('''
            INSERT INTO ledger (customer_id, entry_type, amount, balance_after, payment_method, notes, created_by, created_at)
            VALUES (?, 'PAYMENT', ?, ?, ?, ?, ?, ?)
        ''', (customer_id, amount, new_balance, payment_method, notes, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ledger_id = cursor.lastrowid

        log_audit(user_id, 'ADD_PAYMENT', 'ledger', ledger_id, None, f'Amount: {amount}', conn=conn)

        conn.commit()
        return ledger_id

def add_adjustment(customer_id, amount, reason, reference_id=None, user_id=None):
    """Add an adjustment entry (can be positive or negative)"""
    with get_db() as conn:
        cursor = conn.cursor()

        current_balance = get_customer_balance(customer_id)
        new_balance = current_balance + amount

        cursor.execute('''
            INSERT INTO ledger (customer_id, entry_type, amount, balance_after, notes, reference_id, created_by, created_at)
            VALUES (?, 'ADJUSTMENT', ?, ?, ?, ?, ?, ?)
        ''', (customer_id, amount, new_balance, reason, reference_id, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ledger_id = cursor.lastrowid

        log_audit(user_id, 'ADD_ADJUSTMENT', 'ledger', ledger_id, None, f'Amount: {amount}, Reason: {reason}', conn=conn)

        conn.commit()
        return ledger_id

def add_refund(customer_id, amount, reason, reference_id=None, user_id=None):
    """Process a refund"""
    with get_db() as conn:
        cursor = conn.cursor()

        current_balance = get_customer_balance(customer_id)
        new_balance = current_balance - amount

        cursor.execute('''
            INSERT INTO ledger (customer_id, entry_type, amount, balance_after, notes, reference_id, created_by, created_at)
            VALUES (?, 'REFUND', ?, ?, ?, ?, ?, ?)
        ''', (customer_id, amount, new_balance, reason, reference_id, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ledger_id = cursor.lastrowid

        log_audit(user_id, 'ADD_REFUND', 'ledger', ledger_id, None, f'Amount: {amount}', conn=conn)

        conn.commit()
        return ledger_id

def write_off_debt(customer_id, amount, reason, user_id=None):
    """Write off uncollectible debt (Manager only)"""
    with get_db() as conn:
        cursor = conn.cursor()

        current_balance = get_customer_balance(customer_id)
        new_balance = current_balance - amount

        cursor.execute('''
            INSERT INTO ledger (customer_id, entry_type, amount, balance_after, notes, created_by, created_at)
            VALUES (?, 'WRITE_OFF', ?, ?, ?, ?, ?)
        ''', (customer_id, amount, new_balance, reason, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ledger_id = cursor.lastrowid

        log_audit(user_id, 'WRITE_OFF', 'ledger', ledger_id, None, f'Amount: {amount}, Reason: {reason}', conn=conn)

        conn.commit()
        return ledger_id

def void_entry(ledger_id, reason, user_id=None):
    """Void a ledger entry (hide it visually, but keep it in calculations)"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get original entry
        cursor.execute('SELECT * FROM ledger WHERE id = ?', (ledger_id,))
        entry = cursor.fetchone()
        if not entry:
            return False
        
        # Check if already voided
        if entry['is_voided']:
            return False

        # Mark as voided (but don't recalculate - voided entries still count in balance)
        cursor.execute('''
            UPDATE ledger SET is_voided = 1, voided_by = ?, voided_at = ?, void_reason = ?
            WHERE id = ?
        ''', (user_id, datetime.now(), reason, ledger_id))

        if user_id:
            log_audit(user_id, 'VOID_ENTRY', 'ledger', ledger_id, str(dict(entry)), f'Reason: {reason}', conn=conn)

        conn.commit()
        return True

def unvoid_entry(ledger_id, user_id=None):
    """Unvoid a ledger entry (show it again)"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get original entry
        cursor.execute('SELECT * FROM ledger WHERE id = ?', (ledger_id,))
        entry = cursor.fetchone()
        if not entry:
            return False
        
        # Check if already not voided
        if not entry['is_voided']:
            return False

        # Mark as not voided (but don't recalculate - voided entries still count in balance)
        cursor.execute('''
            UPDATE ledger SET is_voided = 0, voided_by = NULL, voided_at = NULL, void_reason = NULL
            WHERE id = ?
        ''', (ledger_id,))

        if user_id:
            log_audit(user_id, 'UNVOID_ENTRY', 'ledger', ledger_id, str(dict(entry)), 'Entry restored', conn=conn)

        conn.commit()
        return True

def get_customer_ledger(customer_id, include_voided=False):
    """Get all ledger entries for a customer with their items"""
    with get_db() as conn:
        cursor = conn.cursor()
        voided_clause = "" if include_voided else "AND l.is_voided = 0"
        # Always exclude deleted entries from display (they're permanently hidden)
        cursor.execute(f'''
            SELECT l.*, u.full_name as created_by_name
            FROM ledger l
            LEFT JOIN users u ON l.created_by = u.id
            WHERE l.customer_id = ? AND l.is_deleted = 0 {voided_clause}
            ORDER BY l.created_at DESC
        ''', (customer_id,))
        rows = cursor.fetchall()
        entries = []
        for row in rows:
            entry = dict(row)
            # Get items for debt entries
            if entry.get('entry_type') == 'NEW_DEBT':
                try:
                    items = get_ledger_items(entry['id'])
                    entry['items'] = items
                except Exception as e:
                    print(f"Error getting items for ledger {entry['id']}: {e}")
                    entry['items'] = []
            else:
                entry['items'] = []
            entries.append(entry)
        
        return entries

def get_ledger_items(ledger_id):
    """Get line items for a ledger entry"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ledger_items WHERE ledger_id = ?', (ledger_id,))
        rows = cursor.fetchall()
        items = []
        for row in rows:
            item = dict(row)
            # Ensure all values are JSON serializable
            item['quantity'] = int(item.get('quantity', 1))
            item['price'] = float(item.get('price', 0))
            item['product_name'] = str(item.get('product_name', ''))
            items.append(item)
        return items

# ============== REPORTING ==============

def get_total_debt_all():
    """Get total outstanding debt across all active customers (excludes voided and deleted entries)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COALESCE(SUM(
                CASE
                    WHEN l.entry_type IN ('NEW_DEBT', 'ADJUSTMENT') THEN l.amount
                    WHEN l.entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') THEN -l.amount
                    ELSE 0
                END
            ), 0) as total
            FROM ledger l
            JOIN customers c ON l.customer_id = c.id
            WHERE c.is_active = 1
            AND l.is_voided = 0
            AND l.is_deleted = 0
        ''')
        return cursor.fetchone()['total']

def get_customers_with_debt():
    """Get all customers with their current balance, total debt, and total paid"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*,
                COALESCE((
                    SELECT SUM(
                        CASE
                            WHEN entry_type IN ('NEW_DEBT', 'ADJUSTMENT') THEN amount
                            WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') THEN -amount
                            ELSE 0
                        END
                    ) FROM ledger WHERE customer_id = c.id
                ), 0) as debt,
                COALESCE((
                    SELECT SUM(amount) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'NEW_DEBT'
                ), 0) as total_debt_added,
                COALESCE((
                    SELECT SUM(amount) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'PAYMENT'
                ), 0) as total_paid,
                (SELECT MIN(created_at) FROM ledger WHERE customer_id = c.id AND entry_type = 'NEW_DEBT'
                    AND id NOT IN (SELECT reference_id FROM ledger WHERE reference_id IS NOT NULL)) as oldest_debt_date
            FROM customers c
            WHERE c.is_active = 1
            ORDER BY c.name
        ''')
        return [dict(row) for row in cursor.fetchall()]

def get_customers_with_debt_and_items():
    """Get all customers with outstanding debts (debt > 0), including their items from debt entries"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get only customers with outstanding debt (debt > 0)
        cursor.execute('''
            SELECT * FROM (
                SELECT c.*,
                    COALESCE((
                        SELECT SUM(
                            CASE
                                WHEN entry_type IN ('NEW_DEBT') AND is_voided = 0 THEN amount
                                WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') AND is_voided = 0 THEN -amount
                                WHEN entry_type = 'ADJUSTMENT' AND is_voided = 0 THEN amount
                                ELSE 0
                            END
                        ) FROM ledger WHERE customer_id = c.id
                    ), 0) as debt,
                    COALESCE((
                        SELECT SUM(amount) FROM ledger 
                        WHERE customer_id = c.id AND entry_type = 'PAYMENT' AND is_voided = 0
                    ), 0) as total_paid,
                    COALESCE((
                        SELECT SUM(amount) FROM ledger 
                        WHERE customer_id = c.id AND entry_type = 'NEW_DEBT' AND is_voided = 0
                    ), 0) as total_debt_added
                FROM customers c
                WHERE c.is_active = 1
                AND EXISTS (
                    SELECT 1 FROM ledger l
                    WHERE l.customer_id = c.id
                    AND l.is_voided = 0
                )
            ) WHERE debt > 0
            ORDER BY name
        ''')
        customers = [dict(row) for row in cursor.fetchall()]
        
        # Get items for each customer from their debt entries
        for customer in customers:
            cursor.execute('''
                SELECT li.product_name, li.quantity, li.price
                FROM ledger l
                JOIN ledger_items li ON l.id = li.ledger_id
                WHERE l.customer_id = ? 
                AND l.entry_type = 'NEW_DEBT'
                AND l.is_voided = 0
                ORDER BY l.created_at DESC
            ''', (customer['id'],))
            
            items = []
            for row in cursor.fetchall():
                items.append({
                    'product_name': row['product_name'],
                    'quantity': row['quantity'],
                    'price': row['price']
                })
            
            customer['items'] = items
        
        return customers

def get_recent_active_customers(limit=4):
    """Get the most recent customers with activity, always return exactly limit customers"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # First, get customers with recent activity
        cursor.execute('''
            SELECT DISTINCT c.*,
                COALESCE((
                    SELECT SUM(
                        CASE
                            WHEN entry_type IN ('NEW_DEBT') AND is_voided = 0 THEN amount
                            WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') AND is_voided = 0 THEN -amount
                            WHEN entry_type = 'ADJUSTMENT' AND is_voided = 0 THEN amount
                            ELSE 0
                        END
                    ) FROM ledger WHERE customer_id = c.id
                ), 0) as debt,
                COALESCE((
                    SELECT SUM(amount) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'NEW_DEBT' AND is_voided = 0
                ), 0) as total_debt_added,
                COALESCE((
                    SELECT SUM(amount) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'PAYMENT' AND is_voided = 0
                ), 0) as total_paid,
                (SELECT MAX(created_at) FROM ledger 
                 WHERE customer_id = c.id AND is_voided = 0) as last_activity_date
            FROM customers c
            WHERE c.is_active = 1
            AND EXISTS (
                SELECT 1 FROM ledger l
                WHERE l.customer_id = c.id
                AND l.is_voided = 0
            )
            ORDER BY last_activity_date DESC
            LIMIT ?
        ''', (limit,))
        active_customers = [dict(row) for row in cursor.fetchall()]
        
        # If we have fewer than limit, fill with other customers
        if len(active_customers) < limit:
            needed = limit - len(active_customers)
            active_customer_ids = [c['id'] for c in active_customers]
            
            # Get additional customers (those not already in the list)
            if active_customer_ids:
                placeholders = ','.join(['?'] * len(active_customer_ids))
                cursor.execute(f'''
                    SELECT c.*,
                        COALESCE((
                            SELECT SUM(
                                CASE
                                    WHEN entry_type IN ('NEW_DEBT') AND is_voided = 0 THEN amount
                                    WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') AND is_voided = 0 THEN -amount
                                    WHEN entry_type = 'ADJUSTMENT' AND is_voided = 0 THEN amount
                                    ELSE 0
                                END
                            ) FROM ledger WHERE customer_id = c.id
                        ), 0) as debt,
                        COALESCE((
                            SELECT SUM(amount) FROM ledger 
                            WHERE customer_id = c.id AND entry_type = 'NEW_DEBT' AND is_voided = 0
                        ), 0) as total_debt_added,
                        COALESCE((
                            SELECT SUM(amount) FROM ledger 
                            WHERE customer_id = c.id AND entry_type = 'PAYMENT' AND is_voided = 0
                        ), 0) as total_paid,
                        COALESCE((SELECT MAX(created_at) FROM ledger 
                         WHERE customer_id = c.id AND is_voided = 0), c.created_at) as last_activity_date
                    FROM customers c
                    WHERE c.is_active = 1
                    AND c.id NOT IN ({placeholders})
                    ORDER BY c.created_at DESC
                    LIMIT ?
                ''', active_customer_ids + [needed])
            else:
                # No active customers, get any customers
                cursor.execute('''
                    SELECT c.*,
                        COALESCE((
                            SELECT SUM(
                                CASE
                                    WHEN entry_type IN ('NEW_DEBT') AND is_voided = 0 THEN amount
                                    WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') AND is_voided = 0 THEN -amount
                                    WHEN entry_type = 'ADJUSTMENT' AND is_voided = 0 THEN amount
                                    ELSE 0
                                END
                            ) FROM ledger WHERE customer_id = c.id
                        ), 0) as debt,
                        COALESCE((
                            SELECT SUM(amount) FROM ledger 
                            WHERE customer_id = c.id AND entry_type = 'NEW_DEBT' AND is_voided = 0
                        ), 0) as total_debt_added,
                        COALESCE((
                            SELECT SUM(amount) FROM ledger 
                            WHERE customer_id = c.id AND entry_type = 'PAYMENT' AND is_voided = 0
                        ), 0) as total_paid,
                        COALESCE((SELECT MAX(created_at) FROM ledger 
                         WHERE customer_id = c.id AND is_voided = 0), c.created_at) as last_activity_date
                    FROM customers c
                    WHERE c.is_active = 1
                    ORDER BY c.created_at DESC
                    LIMIT ?
                ''', (needed,))
            
            additional_customers = [dict(row) for row in cursor.fetchall()]
            active_customers.extend(additional_customers)
        
        return active_customers[:limit]  # Ensure we never return more than limit

def get_aging_report():
    """Get debt aging report (0-30, 31-60, 61-90, 90+ days)"""
    today = datetime.now()

    customers = get_customers_with_debt()
    aging_data = []

    for customer in customers:
        if customer['debt'] <= 0:
            continue

        # Calculate aging buckets
        current = 0  # 0-30 days
        days_31_60 = 0
        days_61_90 = 0
        days_90_plus = 0

        # Assign debt to aging bucket based on oldest unpaid debt
        if customer['oldest_debt_date']:
            oldest_date = datetime.strptime(customer['oldest_debt_date'][:10], '%Y-%m-%d')
            days_old = (today - oldest_date).days

            if days_old <= 30:
                current = customer['debt']
            elif days_old <= 60:
                days_31_60 = customer['debt']
            elif days_old <= 90:
                days_61_90 = customer['debt']
            else:
                days_90_plus = customer['debt']

        aging_data.append({
            'id': customer['id'],
            'name': customer['name'],
            'phone': customer['phone'],
            'total_debt': customer['debt'],
            'days_0_30': current,
            'days_31_60': days_31_60,
            'days_61_90': days_61_90,
            'days_90_plus': days_90_plus
        })

    return aging_data

def get_daily_reconciliation(date=None):
    """Get daily summary of debt added vs collected"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    with get_db() as conn:
        cursor = conn.cursor()

        # Debt added today (exclude voided and deleted entries)
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM ledger
            WHERE entry_type = 'NEW_DEBT'
            AND is_voided = 0
            AND is_deleted = 0
            AND DATE(created_at) = ?
        ''', (date,))
        debt_added = cursor.fetchone()['total']

        # Payments collected today (exclude voided and deleted entries)
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM ledger
            WHERE entry_type = 'PAYMENT'
            AND is_voided = 0
            AND is_deleted = 0
            AND DATE(created_at) = ?
        ''', (date,))
        payments_collected = cursor.fetchone()['total']

        # Write-offs today (exclude voided and deleted entries)
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM ledger
            WHERE entry_type = 'WRITE_OFF'
            AND is_voided = 0
            AND is_deleted = 0
            AND DATE(created_at) = ?
        ''', (date,))
        write_offs = cursor.fetchone()['total']

        # Adjustments today (exclude voided and deleted entries)
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as total
            FROM ledger
            WHERE entry_type = 'ADJUSTMENT'
            AND is_voided = 0
            AND is_deleted = 0
            AND DATE(created_at) = ?
        ''', (date,))
        adjustments = cursor.fetchone()['total']

        # Number of transactions (exclude voided and deleted entries)
        cursor.execute('''
            SELECT COUNT(*) as count FROM ledger
            WHERE is_voided = 0
            AND is_deleted = 0
            AND DATE(created_at) = ?
        ''', (date,))
        transaction_count = cursor.fetchone()['count']

        # Count entries by type (exclude voided and deleted entries)
        cursor.execute('''
            SELECT COUNT(*) as count FROM ledger
            WHERE entry_type = 'NEW_DEBT'
            AND is_voided = 0
            AND is_deleted = 0
            AND DATE(created_at) = ?
        ''', (date,))
        debt_count = cursor.fetchone()['count']

        cursor.execute('''
            SELECT COUNT(*) as count FROM ledger
            WHERE entry_type = 'PAYMENT'
            AND is_voided = 0
            AND is_deleted = 0
            AND DATE(created_at) = ?
        ''', (date,))
        payment_count = cursor.fetchone()['count']

        return {
            'date': date,
            'total_debt': debt_added,
            'total_payments': payments_collected,
            'write_offs': write_offs,
            'adjustments': adjustments,
            'net_change': debt_added - payments_collected - write_offs + adjustments,
            'transaction_count': transaction_count,
            'debt_count': debt_count,
            'payment_count': payment_count
        }

def get_recent_activity(limit=20):
    """Get recent ledger activity with items (excludes deleted entries)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.*, c.name as customer_name, u.full_name as created_by_name
            FROM ledger l
            JOIN customers c ON l.customer_id = c.id
            LEFT JOIN users u ON l.created_by = u.id
            WHERE l.is_deleted = 0
            ORDER BY l.created_at DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        entries = []
        for row in rows:
            entry = dict(row)
            # Get items for debt entries
            if entry.get('entry_type') == 'NEW_DEBT':
                try:
                    items = get_ledger_items(entry['id'])
                    entry['items'] = items
                except Exception as e:
                    print(f"Error getting items for ledger {entry['id']}: {e}")
                    entry['items'] = []
            else:
                entry['items'] = []
            entries.append(entry)
        
        return entries

def get_overdue_customers(days=30):
    """Get customers with debt older than specified days"""
    with get_db() as conn:
        cursor = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        cursor.execute('''
            SELECT DISTINCT c.*,
                (SELECT SUM(
                    CASE
                        WHEN entry_type IN ('NEW_DEBT') AND is_voided = 0 THEN amount
                        WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') AND is_voided = 0 THEN -amount
                        WHEN entry_type = 'ADJUSTMENT' AND is_voided = 0 THEN amount
                        ELSE 0
                    END
                ) FROM ledger WHERE customer_id = c.id) as debt,
                (SELECT MIN(created_at) FROM ledger WHERE customer_id = c.id AND entry_type = 'NEW_DEBT' AND is_voided = 0) as oldest_debt
            FROM customers c
            WHERE c.is_active = 1
            AND EXISTS (
                SELECT 1 FROM ledger l
                WHERE l.customer_id = c.id
                AND l.entry_type = 'NEW_DEBT'
                AND l.is_voided = 0
                AND DATE(l.created_at) < ?
            )
            HAVING debt > 0
            ORDER BY oldest_debt ASC
        ''', (cutoff_date,))
        return [dict(row) for row in cursor.fetchall()]

def get_over_limit_customers():
    """Get customers who are over their credit limit"""
    customers = get_customers_with_debt()
    return [c for c in customers if c['debt'] > c['credit_limit']]

def get_transactions_by_date(start_date, end_date, customer_id=None):
    """Get transactions within a date range (excludes deleted entries)"""
    with get_db() as conn:
        cursor = conn.cursor()

        if customer_id:
            cursor.execute('''
                SELECT l.*, c.name as customer_name
                FROM ledger l
                JOIN customers c ON l.customer_id = c.id
                WHERE l.is_voided = 0 AND l.is_deleted = 0
                AND DATE(l.created_at) BETWEEN ? AND ?
                AND l.customer_id = ?
                ORDER BY l.created_at DESC
            ''', (start_date, end_date, customer_id))
        else:
            cursor.execute('''
                SELECT l.*, c.name as customer_name
                FROM ledger l
                JOIN customers c ON l.customer_id = c.id
                WHERE l.is_voided = 0 AND l.is_deleted = 0
                AND DATE(l.created_at) BETWEEN ? AND ?
                ORDER BY l.created_at DESC
            ''', (start_date, end_date))

        return [dict(row) for row in cursor.fetchall()]

# ============== CREDIT LIMIT CHECKS ==============

def check_credit_limit(customer_id, additional_amount=0):
    """Check if adding debt would exceed credit limit"""
    customer = get_customer(customer_id)
    if not customer:
        return {'allowed': False, 'message': 'Customer not found'}

    current_balance = get_customer_balance(customer_id)
    new_balance = current_balance + additional_amount

    percentage = (current_balance / customer['credit_limit'] * 100) if customer['credit_limit'] > 0 else 0
    if new_balance > customer['credit_limit']:
        return {
            'allowed': False,
            'current_balance': current_balance,
            'credit_limit': customer['credit_limit'],
            'requested_amount': additional_amount,
            'over_by': new_balance - customer['credit_limit'],
            'available': max(0, customer['credit_limit'] - current_balance),
            'percentage': percentage,
            'message': f"Credit limit exceeded. Current: ${current_balance:.2f}, Limit: ${customer['credit_limit']:.2f}"
        }

    percentage = (current_balance / customer['credit_limit'] * 100) if customer['credit_limit'] > 0 else 0
    return {
        'allowed': True,
        'current_balance': current_balance,
        'credit_limit': customer['credit_limit'],
        'available': customer['credit_limit'] - current_balance,
        'percentage': percentage,
        'message': 'OK'
    }

# ============== AUDIT LOGGING ==============

def log_audit(user_id, action, table_name, record_id, old_values=None, new_values=None, ip_address=None, conn=None):
    """Log an audit entry"""
    def _log(cursor):
        cursor.execute('''
            INSERT INTO audit_log (user_id, action, table_name, record_id, old_values, new_values, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, action, table_name, record_id, old_values, new_values, ip_address))

    if conn:
        _log(conn.cursor())
    else:
        with get_db() as conn:
            _log(conn.cursor())
            conn.commit()

def get_audit_log(limit=100, user_id=None, table_name=None):
    """Get audit log entries"""
    with get_db() as conn:
        cursor = conn.cursor()

        query = '''
            SELECT a.*, u.full_name as user_name
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            WHERE 1=1
        '''
        params = []

        if user_id:
            query += ' AND a.user_id = ?'
            params.append(user_id)

        if table_name:
            query += ' AND a.table_name = ?'
            params.append(table_name)

        query += ' ORDER BY a.created_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

# ============== SETTINGS ==============

def get_setting(key):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        return row['value'] if row else None

def set_setting(key, value):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', (key, value, datetime.now()))
        conn.commit()

# ============== BACKWARD COMPATIBILITY ==============
# These functions maintain compatibility with old code

def get_customer_total_debt(customer_id):
    """Alias for get_customer_balance for backward compatibility"""
    return get_customer_balance(customer_id)

def get_customer_transactions(customer_id):
    """Get debt transactions for a customer (backward compatibility)"""
    ledger = get_customer_ledger(customer_id)
    return [e for e in ledger if e['entry_type'] == 'NEW_DEBT']

def get_customer_payments(customer_id):
    """Get payment entries for a customer (backward compatibility)"""
    ledger = get_customer_ledger(customer_id)
    return [e for e in ledger if e['entry_type'] == 'PAYMENT']

def delete_customer(customer_id):
    """Alias for deactivate_customer"""
    deactivate_customer(customer_id)

def add_transaction(customer_id, items, notes=None):
    """Backward compatibility wrapper for add_debt"""
    return add_debt(customer_id, items, notes=notes)

def delete_transaction(transaction_id):
    """Void a transaction instead of deleting"""
    void_entry(transaction_id, "Deleted via legacy interface")

def delete_payment(payment_id):
    """Void a payment instead of deleting"""
    void_entry(payment_id, "Deleted via legacy interface")

def update_debt_entry(ledger_id, items, notes=None):
    """Update a debt entry with new items and notes"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get customer_id and current entry info
        cursor.execute('SELECT customer_id FROM ledger WHERE id = ?', (ledger_id,))
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Ledger entry {ledger_id} not found")
        customer_id = result['customer_id']
        
        # Calculate new total
        new_total = sum(item['price'] * item.get('quantity', 1) for item in items)
        
        # Get old amount
        cursor.execute('SELECT amount FROM ledger WHERE id = ?', (ledger_id,))
        old_amount = cursor.fetchone()['amount']
        amount_diff = new_total - old_amount
        
        # Update ledger entry
        cursor.execute('''
            UPDATE ledger 
            SET amount = ?, notes = ?
            WHERE id = ?
        ''', (new_total, notes, ledger_id))
        
        # Delete old items
        cursor.execute('DELETE FROM ledger_items WHERE ledger_id = ?', (ledger_id,))
        
        # Insert new items
        for item in items:
            cursor.execute('''
                INSERT INTO ledger_items (ledger_id, product_name, price, quantity)
                VALUES (?, ?, ?, ?)
            ''', (ledger_id, item['product_name'], item['price'], item.get('quantity', 1)))
        
        # Recalculate all balances after this entry
        recalculate_balances_after_entry(customer_id, ledger_id, amount_diff, conn)
        
        conn.commit()

def update_payment_entry(ledger_id, amount, notes=None):
    """Update a payment entry"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get customer_id and old amount
        cursor.execute('SELECT customer_id, amount FROM ledger WHERE id = ?', (ledger_id,))
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Ledger entry {ledger_id} not found")
        customer_id = result['customer_id']
        old_amount = result['amount']
        amount_diff = amount - old_amount
        
        # Update ledger entry
        cursor.execute('''
            UPDATE ledger 
            SET amount = ?, notes = ?
            WHERE id = ?
        ''', (amount, notes, ledger_id))
        
        # Recalculate all balances after this entry
        recalculate_balances_after_entry(customer_id, ledger_id, amount_diff, conn)
        
        conn.commit()

def recalculate_all_customer_balances(customer_id, conn):
    """Recalculate balance_after for all entries of a customer (voided and deleted entries still count)"""
    cursor = conn.cursor()
    
    # Get all entries in chronological order (voided and deleted entries still count in balance)
    cursor.execute('''
        SELECT id, entry_type, amount
        FROM ledger
        WHERE customer_id = ?
        ORDER BY id ASC
    ''', (customer_id,))
    
    entries = cursor.fetchall()
    current_balance = 0
    
    for entry in entries:
        # Include all entries in balance calculation (voiding is just visual)
        if entry['entry_type'] in ('NEW_DEBT', 'ADJUSTMENT'):
            current_balance += entry['amount']
        elif entry['entry_type'] in ('PAYMENT', 'WRITE_OFF', 'REFUND'):
            current_balance -= entry['amount']
        
        # Update balance_after for this entry
        cursor.execute('UPDATE ledger SET balance_after = ? WHERE id = ?', 
                      (current_balance, entry['id']))

def recalculate_balances_after_entry(customer_id, ledger_id, amount_diff, conn=None):
    """Recalculate balances for all entries after a modified entry"""
    if conn is None:
        with get_db() as conn:
            _recalculate_balances(customer_id, ledger_id, conn)
            conn.commit()
    else:
        _recalculate_balances(customer_id, ledger_id, conn)

def _recalculate_balances(customer_id, ledger_id, conn):
    """Internal function to recalculate balances"""
    cursor = conn.cursor()
    
    # Get current balance before the modified entry
    cursor.execute('''
        SELECT COALESCE(SUM(
            CASE
                WHEN entry_type IN ('NEW_DEBT', 'ADJUSTMENT') THEN amount
                WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') THEN -amount
                ELSE 0
            END
        ), 0) as balance
        FROM ledger 
        WHERE customer_id = ? AND id < ?
    ''', (customer_id, ledger_id))
    balance_before = cursor.fetchone()['balance']
    
    # Get the modified entry's new amount
    cursor.execute('SELECT entry_type, amount FROM ledger WHERE id = ?', (ledger_id,))
    entry = cursor.fetchone()
    entry_type = entry['entry_type']
    entry_amount = entry['amount']
    
    # Calculate balance after this entry
    if entry_type in ('NEW_DEBT', 'ADJUSTMENT'):
        balance_after = balance_before + entry_amount
    else:
        balance_after = balance_before - entry_amount
    
    # Update this entry's balance
    cursor.execute('UPDATE ledger SET balance_after = ? WHERE id = ?', (balance_after, ledger_id))
    
    # Update all subsequent entries
    cursor.execute('''
        SELECT id, entry_type, amount 
        FROM ledger 
        WHERE customer_id = ? AND id > ?
        ORDER BY id ASC
    ''', (customer_id, ledger_id))
    
    current_balance = balance_after
    for row in cursor.fetchall():
        # Calculate balance based on entry type (deleted entries won't be here)
        if row['entry_type'] in ('NEW_DEBT', 'ADJUSTMENT'):
            current_balance += row['amount']
        elif row['entry_type'] in ('PAYMENT', 'WRITE_OFF', 'REFUND'):
            current_balance -= row['amount']
        cursor.execute('UPDATE ledger SET balance_after = ? WHERE id = ?', (current_balance, row['id']))

def delete_ledger_entry(ledger_id):
    """Mark a ledger entry as deleted (hidden from UI but still counts in balance)"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get entry to verify it exists
        cursor.execute('SELECT customer_id FROM ledger WHERE id = ? AND is_deleted = 0', (ledger_id,))
        result = cursor.fetchone()
        if not result:
            return False
        
        # Mark as deleted instead of actually deleting (keeps balance intact)
        cursor.execute('''
            UPDATE ledger 
            SET is_deleted = 1, deleted_at = ?
            WHERE id = ?
        ''', (datetime.now(), ledger_id))
        
        conn.commit()
        return True

def delete_all_customer_data():
    """Delete all customer data including customers, ledger entries, and related records"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # Delete in order to respect foreign key constraints
            # 1. Delete ledger items (references ledger)
            cursor.execute('DELETE FROM ledger_items')
            
            # 2. Delete donation usage (references customers)
            cursor.execute('DELETE FROM donation_usage')
            
            # 3. Delete ledger entries (references customers)
            cursor.execute('DELETE FROM ledger')
            
            # 4. Delete customers
            cursor.execute('DELETE FROM customers')
            
            # 5. Delete audit log entries related to customers/ledger
            cursor.execute('DELETE FROM audit_log WHERE table_name IN ("customers", "ledger")')
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e

def get_recent_transactions(limit=10):
    """Get recent debt transactions"""
    activity = get_recent_activity(limit * 2)
    debts = [a for a in activity if a['entry_type'] == 'NEW_DEBT'][:limit]
    # Transform to match old format
    for d in debts:
        d['total'] = d['amount']
        d['date'] = d['created_at']
        d['customer_id'] = d['customer_id']
    return debts

def get_debt_by_date(start_date, end_date, customer_id=None):
    """Get total debt added in a date range"""
    transactions = get_transactions_by_date(start_date, end_date, customer_id)
    return sum(t['amount'] for t in transactions if t['entry_type'] == 'NEW_DEBT')

def get_customers_with_debt_by_date_range(start_date, end_date, customer_id=None):
    """Get customers with their debt totals for a specific date range (only debts, not payments in the report)"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Build the query to get customers with debt entries in the date range
        # Only include customers who have NEW_DEBT entries in the range
        # Calculate net debt (debts - payments) for transactions in the date range
        base_query = '''
            SELECT * FROM (
                SELECT c.id, c.name, c.phone,
                    COALESCE((
                        SELECT SUM(
                            CASE
                                WHEN entry_type = 'NEW_DEBT' AND is_voided = 0 AND is_deleted = 0 THEN amount
                                WHEN entry_type = 'PAYMENT' AND is_voided = 0 AND is_deleted = 0 THEN -amount
                                WHEN entry_type = 'ADJUSTMENT' AND is_voided = 0 AND is_deleted = 0 THEN amount
                                ELSE 0
                            END
                        ) FROM ledger 
                        WHERE customer_id = c.id
                        AND DATE(created_at) BETWEEN ? AND ?
                    ), 0) as debt
                FROM customers c
                WHERE c.is_active = 1
                AND EXISTS (
                    SELECT 1 FROM ledger l
                    WHERE l.customer_id = c.id
                    AND l.entry_type = 'NEW_DEBT'
                    AND l.is_voided = 0
                    AND l.is_deleted = 0
                    AND DATE(l.created_at) BETWEEN ? AND ?
                )
        '''
        
        params = [start_date, end_date, start_date, end_date]
        
        if customer_id:
            base_query += ' AND c.id = ?'
            params.append(customer_id)
        
        base_query += ') WHERE debt > 0'
        base_query += ' ORDER BY name'
        
        cursor.execute(base_query, params)
        customers = [dict(row) for row in cursor.fetchall()]
        
        # Get items for each customer from their debt entries in the date range
        for customer in customers:
            cursor.execute('''
                SELECT li.product_name, li.price, li.quantity
                FROM ledger_items li
                INNER JOIN ledger l ON li.ledger_id = l.id
                WHERE l.customer_id = ?
                AND l.entry_type = 'NEW_DEBT'
                AND l.is_voided = 0
                AND l.is_deleted = 0
                AND DATE(l.created_at) BETWEEN ? AND ?
                ORDER BY l.created_at DESC
            ''', (customer['id'], start_date, end_date))
            customer['items'] = [dict(row) for row in cursor.fetchall()]
        
        return customers

# ============== DONATIONS OPERATIONS ==============

def get_unique_donor_names():
    """Get all unique donor names from donations"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT donor_name 
            FROM donations 
            WHERE donor_name IS NOT NULL AND donor_name != ''
            ORDER BY donor_name
        ''')
        return [row[0] for row in cursor.fetchall()]

def add_donation(amount, donor_name=None, notes=None):
    """Add a new donation"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO donations (amount, donor_name, notes)
            VALUES (?, ?, ?)
        ''', (amount, donor_name, notes))
        conn.commit()
        return cursor.lastrowid

def get_all_donations():
    """Get all donations with usage information"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.*,
                COALESCE((
                    SELECT SUM(amount_used) 
                    FROM donation_usage 
                    WHERE donation_id = d.id
                ), 0) as amount_used,
                (d.amount - COALESCE((
                    SELECT SUM(amount_used) 
                    FROM donation_usage 
                    WHERE donation_id = d.id
                ), 0)) as amount_remaining
            FROM donations d
            ORDER BY d.created_at DESC
        ''')
        return [dict(row) for row in cursor.fetchall()]

def get_donation(donation_id):
    """Get a specific donation"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.*,
                COALESCE((
                    SELECT SUM(amount_used) 
                    FROM donation_usage 
                    WHERE donation_id = d.id
                ), 0) as amount_used,
                (d.amount - COALESCE((
                    SELECT SUM(amount_used) 
                    FROM donation_usage 
                    WHERE donation_id = d.id
                ), 0)) as amount_remaining
            FROM donations d
            WHERE d.id = ?
        ''', (donation_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_available_donations():
    """Get donations that still have available funds"""
    donations = get_all_donations()
    return [d for d in donations if d['amount_remaining'] > 0]

def use_donation(donation_id, customer_id, amount, notes=None):
    """Use a donation to help pay a customer's debt"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if donation exists and get donor name
        cursor.execute('SELECT amount, donor_name FROM donations WHERE id = ?', (donation_id,))
        donation_row = cursor.fetchone()
        if not donation_row:
            return {'success': False, 'message': 'Donation not found'}
        
        donation_amount = donation_row['amount']
        donor_name = donation_row['donor_name']
        
        # Calculate remaining amount using the same connection
        cursor.execute('''
            SELECT COALESCE(SUM(amount_used), 0) as amount_used
            FROM donation_usage 
            WHERE donation_id = ?
        ''', (donation_id,))
        amount_used = cursor.fetchone()['amount_used']
        amount_remaining = donation_amount - amount_used
        
        if amount_remaining < amount:
            return {'success': False, 'message': f'Not enough remaining. Available: ${amount_remaining:.2f}'}
        
        # Calculate current customer balance to check if amount exceeds debt
        cursor.execute('''
            SELECT COALESCE(SUM(
                CASE
                    WHEN entry_type IN ('NEW_DEBT') AND is_voided = 0 THEN amount
                    WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') AND is_voided = 0 THEN -amount
                    WHEN entry_type = 'ADJUSTMENT' AND is_voided = 0 THEN amount
                    ELSE 0
                END
            ), 0) as balance
            FROM ledger WHERE customer_id = ?
        ''', (customer_id,))
        current_balance = cursor.fetchone()['balance']
        
        # Check if donation amount exceeds customer's debt
        if amount > current_balance:
            return {'success': False, 'message': f'Cannot apply more than the customer owes. Customer owes: ${current_balance:.2f}'}
        
        # Record the usage
        cursor.execute('''
            INSERT INTO donation_usage (donation_id, customer_id, amount_used, notes)
            VALUES (?, ?, ?, ?)
        ''', (donation_id, customer_id, amount, notes))
        usage_id = cursor.lastrowid
        
        # Calculate new balance after payment
        new_balance = current_balance - amount
        
        # Apply the donation as a payment for the customer (within the same connection)
        # Show donor name or "Anonymous" instead of usage ID
        donor_display = donor_name if donor_name and donor_name.strip() else 'Anonymous'
        payment_notes = f'Donation from {donor_display}' + (f' - {notes}' if notes else '')
        cursor.execute('''
            INSERT INTO ledger (customer_id, entry_type, amount, balance_after, payment_method, notes, created_by, created_at)
            VALUES (?, 'PAYMENT', ?, ?, ?, ?, ?, ?)
        ''', (customer_id, amount, new_balance, 'CASH', payment_notes, None, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ledger_id = cursor.lastrowid
        
        # Log audit
        log_audit(None, 'ADD_PAYMENT', 'ledger', ledger_id, None, f'Amount: {amount} (Donation)', conn=conn)
        
        conn.commit()
        return {'success': True, 'usage_id': usage_id}

def get_donation_usage_history(donation_id=None):
    """Get history of donation usage"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if donation_id:
            cursor.execute('''
                SELECT du.*, c.name as customer_name, d.amount as donation_amount, d.donor_name
                FROM donation_usage du
                JOIN customers c ON du.customer_id = c.id
                JOIN donations d ON du.donation_id = d.id
                WHERE du.donation_id = ?
                ORDER BY du.created_at DESC
            ''', (donation_id,))
        else:
            cursor.execute('''
                SELECT du.*, c.name as customer_name, d.amount as donation_amount, d.donor_name
                FROM donation_usage du
                JOIN customers c ON du.customer_id = c.id
                JOIN donations d ON du.donation_id = d.id
                ORDER BY du.created_at DESC
            ''')
        
        return [dict(row) for row in cursor.fetchall()]

def get_total_donations():
    """Get total amount of all donations"""
    donations = get_all_donations()
    return sum(d['amount'] for d in donations)

def get_total_donations_used():
    """Get total amount of donations used"""
    usage_history = get_donation_usage_history()
    return sum(u['amount_used'] for u in usage_history)

def get_total_donations_available():
    """Get total amount of donations still available"""
    return get_total_donations() - get_total_donations_used()

# ============== BACKUP & RESTORE ==============

def export_all_data_to_csv():
    """Export all data to CSV format and return as string"""
    output = io.StringIO()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Export Customers with calculated financial data
        output.write("=== CUSTOMERS ===\n")
        writer = csv.writer(output)
        cursor.execute('''
            SELECT c.*,
                COALESCE((
                    SELECT SUM(
                        CASE
                            WHEN entry_type IN ('NEW_DEBT', 'ADJUSTMENT') THEN amount
                            WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') THEN -amount
                            ELSE 0
                        END
                    ) FROM ledger WHERE customer_id = c.id AND is_voided = 0 AND is_deleted = 0
                ), 0) as current_balance,
                COALESCE((
                    SELECT SUM(amount) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'NEW_DEBT' AND is_voided = 0 AND is_deleted = 0
                ), 0) as total_debt_added,
                COALESCE((
                    SELECT SUM(amount) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'PAYMENT' AND is_voided = 0 AND is_deleted = 0
                ), 0) as total_paid,
                COALESCE((
                    SELECT SUM(amount) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'ADJUSTMENT' AND is_voided = 0 AND is_deleted = 0
                ), 0) as total_adjustments,
                COALESCE((
                    SELECT COUNT(*) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'NEW_DEBT' AND is_voided = 0 AND is_deleted = 0
                ), 0) as total_debt_transactions,
                COALESCE((
                    SELECT COUNT(*) FROM ledger 
                    WHERE customer_id = c.id AND entry_type = 'PAYMENT' AND is_voided = 0 AND is_deleted = 0
                ), 0) as total_payment_transactions
            FROM customers c
            WHERE c.is_active = 1
        ''')
        customers = [dict(row) for row in cursor.fetchall()]
        if customers:
            writer.writerow(customers[0].keys())
            for customer in customers:
                writer.writerow(customer.values())
        output.write("\n")
        
        # Export Products
        output.write("=== PRODUCTS ===\n")
        cursor.execute('SELECT * FROM products')
        products = [dict(row) for row in cursor.fetchall()]
        if products:
            writer.writerow(products[0].keys())
            for product in products:
                writer.writerow(product.values())
        output.write("\n")
        
        # Export Ledger (all entries including voided/deleted for complete history)
        output.write("=== LEDGER ===\n")
        cursor.execute('SELECT * FROM ledger ORDER BY created_at')
        ledger = [dict(row) for row in cursor.fetchall()]
        if ledger:
            writer.writerow(ledger[0].keys())
            for entry in ledger:
                writer.writerow(entry.values())
        output.write("\n")
        
        # Export Ledger Summary (calculated totals by customer)
        output.write("=== LEDGER_SUMMARY ===\n")
        cursor.execute('''
            SELECT 
                c.id as customer_id,
                c.name as customer_name,
                c.phone as customer_phone,
                COALESCE(SUM(
                    CASE
                        WHEN l.entry_type IN ('NEW_DEBT', 'ADJUSTMENT') AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.amount
                        WHEN l.entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') AND l.is_voided = 0 AND l.is_deleted = 0 THEN -l.amount
                        ELSE 0
                    END
                ), 0) as current_balance,
                COALESCE(SUM(CASE WHEN l.entry_type = 'NEW_DEBT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.amount ELSE 0 END), 0) as total_debt_added,
                COALESCE(SUM(CASE WHEN l.entry_type = 'PAYMENT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.amount ELSE 0 END), 0) as total_paid,
                COALESCE(SUM(CASE WHEN l.entry_type = 'ADJUSTMENT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.amount ELSE 0 END), 0) as total_adjustments,
                COALESCE(SUM(CASE WHEN l.entry_type = 'WRITE_OFF' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.amount ELSE 0 END), 0) as total_write_offs,
                COALESCE(SUM(CASE WHEN l.entry_type = 'REFUND' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.amount ELSE 0 END), 0) as total_refunds,
                COUNT(CASE WHEN l.entry_type = 'NEW_DEBT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN 1 END) as debt_count,
                COUNT(CASE WHEN l.entry_type = 'PAYMENT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN 1 END) as payment_count,
                MIN(CASE WHEN l.entry_type = 'NEW_DEBT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.created_at END) as first_debt_date,
                MAX(CASE WHEN l.entry_type = 'NEW_DEBT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.created_at END) as last_debt_date,
                MAX(CASE WHEN l.entry_type = 'PAYMENT' AND l.is_voided = 0 AND l.is_deleted = 0 THEN l.created_at END) as last_payment_date
            FROM customers c
            LEFT JOIN ledger l ON c.id = l.customer_id
            WHERE c.is_active = 1
            GROUP BY c.id, c.name, c.phone
            HAVING COUNT(l.id) > 0
            ORDER BY c.name
        ''')
        summary = [dict(row) for row in cursor.fetchall()]
        if summary:
            writer.writerow(summary[0].keys())
            for row in summary:
                writer.writerow(row.values())
        output.write("\n")
        
        # Export Ledger Items
        output.write("=== LEDGER_ITEMS ===\n")
        cursor.execute('SELECT * FROM ledger_items')
        items = [dict(row) for row in cursor.fetchall()]
        if items:
            writer.writerow(items[0].keys())
            for item in items:
                writer.writerow(item.values())
        output.write("\n")
        
        # Export Donations
        output.write("=== DONATIONS ===\n")
        cursor.execute('SELECT * FROM donations WHERE is_active = 1')
        donations = [dict(row) for row in cursor.fetchall()]
        if donations:
            writer.writerow(donations[0].keys())
            for donation in donations:
                writer.writerow(donation.values())
        output.write("\n")
        
        # Export Donation Usage
        output.write("=== DONATION_USAGE ===\n")
        cursor.execute('SELECT * FROM donation_usage')
        usage = [dict(row) for row in cursor.fetchall()]
        if usage:
            writer.writerow(usage[0].keys())
            for u in usage:
                writer.writerow(u.values())
        output.write("\n")
    
    return output.getvalue()

def import_data_from_csv(csv_content):
    """Import data from CSV backup file - clears existing data first"""
    errors = []
    imported = {
        'customers': 0,
        'products': 0,
        'ledger': 0,
        'ledger_items': 0,
        'donations': 0,
        'donation_usage': 0
    }
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Clear existing data (except users and settings)
        try:
            cursor.execute('DELETE FROM donation_usage')
            cursor.execute('DELETE FROM donations')
            cursor.execute('DELETE FROM ledger_items')
            cursor.execute('DELETE FROM ledger')
            cursor.execute('DELETE FROM products')
            cursor.execute('DELETE FROM customers')
            conn.commit()
        except Exception as e:
            errors.append(f"Error clearing existing data: {str(e)}")
            return {'success': False, 'imported': imported, 'errors': errors}
        
        # Parse CSV content by sections
        sections = csv_content.split('=== ')
        id_mapping = {'customers': {}, 'products': {}, 'donations': {}}
        ledger_id_mapping = {}
        ledger_items_to_import = []
        
        # First pass: Import customers, products, donations
        for section in sections:
            if not section.strip():
                continue
                
            lines = section.strip().split('\n')
            if not lines:
                continue
                
            section_name = lines[0].replace(' ===', '').strip()
            if len(lines) < 2:
                continue
                
            # Read CSV data
            reader = csv.reader(lines[1:])
            rows = list(reader)
            if not rows:
                continue
                
            headers = rows[0]
            data_rows = rows[1:]
            
            try:
                if section_name == 'CUSTOMERS':
                    for row in data_rows:
                        if len(row) != len(headers):
                            continue
                        row_dict = dict(zip(headers, row))
                        old_id = row_dict.get('id')
                        cursor.execute('''
                            INSERT INTO customers (name, phone, email, address, credit_limit, grace_period_days, is_active, notes, profile_image, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row_dict.get('name'),
                            row_dict.get('phone'),
                            row_dict.get('email'),
                            row_dict.get('address'),
                            float(row_dict.get('credit_limit', 500.00)) if row_dict.get('credit_limit') else 500.00,
                            int(row_dict.get('grace_period_days', 7)) if row_dict.get('grace_period_days') else 7,
                            int(row_dict.get('is_active', 1)) if row_dict.get('is_active') else 1,
                            row_dict.get('notes'),
                            row_dict.get('profile_image'),
                            row_dict.get('created_at')
                        ))
                        new_id = cursor.lastrowid
                        if old_id:
                            id_mapping['customers'][str(old_id)] = new_id
                        imported['customers'] += 1
                        
                elif section_name == 'PRODUCTS':
                    for row in data_rows:
                        if len(row) != len(headers):
                            continue
                        row_dict = dict(zip(headers, row))
                        old_id = row_dict.get('id')
                        cursor.execute('''
                            INSERT INTO products (name, price, category, is_prescription, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            row_dict.get('name'),
                            float(row_dict.get('price', 0)) if row_dict.get('price') else 0,
                            row_dict.get('category'),
                            int(row_dict.get('is_prescription', 0)) if row_dict.get('is_prescription') else 0,
                            row_dict.get('created_at')
                        ))
                        new_id = cursor.lastrowid
                        if old_id:
                            id_mapping['products'][str(old_id)] = new_id
                        imported['products'] += 1
                        
                elif section_name == 'DONATIONS':
                    for row in data_rows:
                        if len(row) != len(headers):
                            continue
                        row_dict = dict(zip(headers, row))
                        old_id = row_dict.get('id')
                        cursor.execute('''
                            INSERT INTO donations (amount, donor_name, notes, is_active, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            float(row_dict.get('amount', 0)) if row_dict.get('amount') else 0,
                            row_dict.get('donor_name'),
                            row_dict.get('notes'),
                            int(row_dict.get('is_active', 1)) if row_dict.get('is_active') else 1,
                            row_dict.get('created_at')
                        ))
                        new_id = cursor.lastrowid
                        if old_id:
                            id_mapping['donations'][str(old_id)] = new_id
                        imported['donations'] += 1
                        
                elif section_name == 'LEDGER_ITEMS':
                    # Collect items to import after ledger is imported
                    for row in data_rows:
                        if len(row) != len(headers):
                            continue
                        row_dict = dict(zip(headers, row))
                        ledger_items_to_import.append(row_dict)
            except Exception as e:
                errors.append(f"Error importing {section_name}: {str(e)}")
        
        # Commit first pass (customers, products, donations) before importing ledger
        conn.commit()
                        
        # Second pass: Import ledger entries (need customer IDs first)
        for section in sections:
            if not section.strip():
                continue
            lines = section.strip().split('\n')
            if not lines:
                continue
            section_name = lines[0].replace(' ===', '').strip()
            if len(lines) < 2:
                continue
            reader = csv.reader(lines[1:])
            rows = list(reader)
            if not rows:
                continue
            headers = rows[0]
            data_rows = rows[1:]
            
            try:
                if section_name == 'LEDGER':
                    # First pass: collect all ledger entries with old IDs
                    ledger_entries = []
                    for row in data_rows:
                        if len(row) != len(headers):
                            continue
                        row_dict = dict(zip(headers, row))
                        old_customer_id = row_dict.get('customer_id')
                        
                        # Try to find the customer ID in mapping (handle both string and int)
                        new_customer_id = None
                        if old_customer_id:
                            # Try as string first
                            new_customer_id = id_mapping['customers'].get(str(old_customer_id))
                            # If not found, try as int
                            if not new_customer_id:
                                try:
                                    new_customer_id = id_mapping['customers'].get(str(int(float(old_customer_id))))
                                except (ValueError, TypeError):
                                    pass
                        
                        if not new_customer_id:
                            # Skip entries without valid customer
                            continue
                        
                        ledger_entries.append({
                            'old_id': row_dict.get('id'),
                            'row_dict': row_dict,
                            'new_customer_id': new_customer_id
                        })
                    
                    # Second pass: import and map ledger IDs (need to do in order for reference_id)
                    for entry in ledger_entries:
                        row_dict = entry['row_dict']
                        old_ledger_id = entry['old_id']
                        old_reference_id = row_dict.get('reference_id')
                        
                        # Verify customer exists before inserting
                        cursor.execute('SELECT id FROM customers WHERE id = ?', (entry['new_customer_id'],))
                        if not cursor.fetchone():
                            errors.append(f"Customer {entry['new_customer_id']} does not exist for ledger entry {old_ledger_id}")
                            continue
                        
                        # Map reference_id if it exists
                        new_reference_id = None
                        if old_reference_id and str(old_reference_id).strip() and str(old_reference_id).lower() not in ['', 'none', 'null']:
                            new_reference_id = ledger_id_mapping.get(str(old_reference_id))
                            if not new_reference_id:
                                try:
                                    new_reference_id = ledger_id_mapping.get(str(int(float(old_reference_id))))
                                except (ValueError, TypeError):
                                    pass
                        
                        # Check and set created_by/voided_by to NULL if user doesn't exist
                        created_by = row_dict.get('created_by')
                        if created_by and str(created_by).strip() and str(created_by).lower() not in ['', 'none', 'null']:
                            try:
                                created_by_int = int(float(created_by))
                                cursor.execute('SELECT id FROM users WHERE id = ?', (created_by_int,))
                                if not cursor.fetchone():
                                    created_by = None
                            except (ValueError, TypeError):
                                created_by = None
                        else:
                            created_by = None
                        
                        voided_by = row_dict.get('voided_by')
                        if voided_by and str(voided_by).strip() and str(voided_by).lower() not in ['', 'none', 'null']:
                            try:
                                voided_by_int = int(float(voided_by))
                                cursor.execute('SELECT id FROM users WHERE id = ?', (voided_by_int,))
                                if not cursor.fetchone():
                                    voided_by = None
                            except (ValueError, TypeError):
                                voided_by = None
                        else:
                            voided_by = None
                        
                        try:
                            cursor.execute('''
                                INSERT INTO ledger (customer_id, entry_type, amount, balance_after, rx_number, description, notes, payment_method, reference_id, created_by, created_at, is_voided, voided_by, voided_at, void_reason, is_deleted, deleted_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                entry['new_customer_id'],
                                row_dict.get('entry_type'),
                                float(row_dict.get('amount', 0)) if row_dict.get('amount') and str(row_dict.get('amount')).strip() else 0,
                                float(row_dict.get('balance_after')) if row_dict.get('balance_after') and str(row_dict.get('balance_after')).strip() and str(row_dict.get('balance_after')).lower() not in ['', 'none', 'null'] else None,
                                row_dict.get('rx_number'),
                                row_dict.get('description'),
                                row_dict.get('notes'),
                                row_dict.get('payment_method'),
                                new_reference_id,
                                created_by,
                                row_dict.get('created_at'),
                                int(row_dict.get('is_voided', 0)) if row_dict.get('is_voided') and str(row_dict.get('is_voided')).strip() and str(row_dict.get('is_voided')).lower() not in ['', 'none', 'null', '0', 'false'] else 0,
                                voided_by,
                                row_dict.get('voided_at'),
                                row_dict.get('void_reason'),
                                int(row_dict.get('is_deleted', 0)) if row_dict.get('is_deleted') and str(row_dict.get('is_deleted')).strip() and str(row_dict.get('is_deleted')).lower() not in ['', 'none', 'null', '0', 'false'] else 0,
                                row_dict.get('deleted_at')
                            ))
                            new_ledger_id = cursor.lastrowid
                            if old_ledger_id:
                                ledger_id_mapping[str(old_ledger_id)] = new_ledger_id
                            imported['ledger'] += 1
                        except Exception as e:
                            errors.append(f"Error importing ledger entry {old_ledger_id}: {str(e)}")
                            continue
                            
                elif section_name == 'LEDGER_SUMMARY':
                    # Skip LEDGER_SUMMARY - it's a calculated section, not raw data
                    pass
            except Exception as e:
                errors.append(f"Error importing {section_name}: {str(e)}")
                        
        # Third pass: Import ledger items (after ledger entries are imported)
        for item_dict in ledger_items_to_import:
            old_ledger_id = item_dict.get('ledger_id')
            new_ledger_id = ledger_id_mapping.get(str(old_ledger_id)) if old_ledger_id else None
            if not new_ledger_id:
                continue
            try:
                cursor.execute('''
                    INSERT INTO ledger_items (ledger_id, product_name, price, quantity, rx_number)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    new_ledger_id,
                    item_dict.get('product_name'),
                    float(item_dict.get('price', 0)) if item_dict.get('price') else 0,
                    int(item_dict.get('quantity', 1)) if item_dict.get('quantity') else 1,
                    item_dict.get('rx_number')
                ))
                imported['ledger_items'] += 1
            except Exception as e:
                errors.append(f"Error importing ledger item: {str(e)}")
        
        # Fourth pass: Import donation usage (after donations and customers are imported)
        for section in sections:
            if not section.strip():
                continue
            lines = section.strip().split('\n')
            if not lines:
                continue
            section_name = lines[0].replace(' ===', '').strip()
            if len(lines) < 2:
                continue
            reader = csv.reader(lines[1:])
            rows = list(reader)
            if not rows:
                continue
            headers = rows[0]
            data_rows = rows[1:]
            
            try:
                if section_name == 'DONATION_USAGE':
                    for row in data_rows:
                        if len(row) != len(headers):
                            continue
                        row_dict = dict(zip(headers, row))
                        old_donation_id = row_dict.get('donation_id')
                        old_customer_id = row_dict.get('customer_id')
                        new_donation_id = id_mapping['donations'].get(str(old_donation_id)) if old_donation_id else None
                        new_customer_id = id_mapping['customers'].get(str(old_customer_id)) if old_customer_id else None
                        if not new_donation_id or not new_customer_id:
                            continue
                        cursor.execute('''
                            INSERT INTO donation_usage (donation_id, customer_id, amount_used, notes, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            new_donation_id,
                            new_customer_id,
                            float(row_dict.get('amount_used', 0)) if row_dict.get('amount_used') else 0,
                            row_dict.get('notes'),
                            row_dict.get('created_at')
                        ))
                        imported['donation_usage'] += 1
            except Exception as e:
                errors.append(f"Error importing {section_name}: {str(e)}")
        
        conn.commit()
    
    return {'success': len(errors) == 0, 'imported': imported, 'errors': errors}

def create_demo_data():
    """Create demo data for testing"""
    import random
    from datetime import datetime, timedelta
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute('DELETE FROM donation_usage')
        cursor.execute('DELETE FROM donations')
        cursor.execute('DELETE FROM ledger_items')
        cursor.execute('DELETE FROM ledger')
        cursor.execute('DELETE FROM products')
        cursor.execute('DELETE FROM customers')
        conn.commit()
        
        # Add products
        products_data = [
            ("Paracetamol 500mg", 5.00, "Pain Relief", 0),
            ("Ibuprofen 400mg", 8.50, "Pain Relief", 0),
            ("Amoxicillin 500mg", 12.00, "Antibiotics", 1),
            ("Vitamin D3 1000IU", 15.00, "Vitamins", 0),
            ("Cough Syrup", 10.00, "Respiratory", 0),
        ]
        product_ids = []
        for name, price, category, is_prescription in products_data:
            cursor.execute('''
                INSERT INTO products (name, price, category, is_prescription, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, price, category, is_prescription, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            product_ids.append(cursor.lastrowid)
        
        # Add customers
        customers_data = [
            ("Ahmad Ghandour", "+961 03 441 339", "ahmad@example.com", "Beirut", 1000.00, "Regular customer"),
            ("Mariam Khoury", "+961 70 123 456", None, "Tripoli", 500.00, None),
            ("George Saad", "+961 71 789 012", "george@example.com", None, 750.00, "Family discount"),
            ("Layla Fadel", "+961 76 345 678", None, "Sidon", 600.00, None),
        ]
        customer_ids = []
        for name, phone, email, address, credit_limit, notes in customers_data:
            cursor.execute('''
                INSERT INTO customers (name, phone, email, address, credit_limit, grace_period_days, is_active, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, phone, email, address, credit_limit, 7, 1, notes, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            customer_ids.append(cursor.lastrowid)
        
        # Add debts for customers
        for i, customer_id in enumerate(customer_ids):
            # Each customer gets 1-3 debt transactions
            num_debts = random.randint(1, 3)
            for j in range(num_debts):
                days_ago = random.randint(0, 30)
                debt_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                
                # Create debt with items
                items = []
                num_items = random.randint(1, 3)
                for _ in range(num_items):
                    product_idx = random.randint(0, len(product_ids) - 1)
                    product = products_data[product_idx]
                    quantity = random.randint(1, 2)
                    items.append({
                        'product_name': product[0],
                        'price': product[1],
                        'quantity': quantity
                    })
                
                # Calculate total
                total = sum(item['price'] * item['quantity'] for item in items)
                
                # Get current balance
                cursor.execute('''
                    SELECT COALESCE(SUM(
                        CASE
                            WHEN entry_type IN ('NEW_DEBT', 'ADJUSTMENT') THEN amount
                            WHEN entry_type IN ('PAYMENT', 'WRITE_OFF', 'REFUND') THEN -amount
                            ELSE 0
                        END
                    ), 0) as balance
                    FROM ledger WHERE customer_id = ?
                ''', (customer_id,))
                current_balance = cursor.fetchone()['balance']
                new_balance = current_balance + total
                
                # Insert ledger entry
                cursor.execute('''
                    INSERT INTO ledger (customer_id, entry_type, amount, balance_after, notes, created_at)
                    VALUES (?, 'NEW_DEBT', ?, ?, ?, ?)
                ''', (customer_id, total, new_balance, f"Debt transaction {j+1}", debt_date + " 10:00:00"))
                ledger_id = cursor.lastrowid
                
                # Insert ledger items
                for item in items:
                    cursor.execute('''
                        INSERT INTO ledger_items (ledger_id, product_name, price, quantity)
                        VALUES (?, ?, ?, ?)
                    ''', (ledger_id, item['product_name'], item['price'], item['quantity']))
                
                # Some customers make payments
                if random.random() < 0.5 and new_balance > 0:
                    payment_amount = min(random.uniform(10, new_balance * 0.5), new_balance)
                    payment_method = random.choice(['CASH', 'CARD', 'CHECK'])
                    payment_date = (datetime.now() - timedelta(days=random.randint(0, days_ago))).strftime('%Y-%m-%d %H:%M:%S')
                    
                    new_balance_after = new_balance - payment_amount
                    cursor.execute('''
                        INSERT INTO ledger (customer_id, entry_type, amount, balance_after, payment_method, notes, created_at)
                        VALUES (?, 'PAYMENT', ?, ?, ?, ?, ?)
                    ''', (customer_id, payment_amount, new_balance_after, payment_method, f"{payment_method} payment", payment_date))
        
        # Add a donation
        cursor.execute('''
            INSERT INTO donations (amount, donor_name, notes, is_active, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (500.00, "Anonymous Donor", "Community support", 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
    
    return True
