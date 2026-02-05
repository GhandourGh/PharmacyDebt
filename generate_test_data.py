#!/usr/bin/env python3
"""
Test Data Generation Script
Generates 500 customers, random medicine products, and transactions for testing
"""

import random
import sys
from datetime import datetime, timedelta
from database import init_db, add_customer, add_product, add_debt, add_payment, get_all_products, get_customer_balance

# Lebanese names for realistic test data
FIRST_NAMES = [
    "Ahmad", "Mohammad", "Ali", "Hassan", "Hussein", "Omar", "Khaled", "Tarek", "Fadi", "Rami",
    "Mariam", "Hala", "Layla", "Nour", "Sara", "Rania", "Lina", "Nadia", "Yara", "Dina",
    "Fatima", "Zeinab", "Aisha", "Salma", "Noor", "Leila", "Maya", "Rita", "Rima", "Nour",
    "George", "Joseph", "Michel", "Pierre", "Antoine", "Marc", "Paul", "Jean", "Charles", "Henri",
    "Marie", "Sophie", "Catherine", "Isabelle", "Claire", "Anne", "Julie", "Nathalie", "Elise", "Camille"
]

LAST_NAMES = [
    "Al-Nour", "Al-Amin", "Al-Hassan", "Al-Hussein", "Khoury", "Saad", "Fadel", "Ghandour",
    "Younes", "Mansour", "Farouk", "Ibrahim", "Mahmoud", "Salem", "Hamdan", "Nasser",
    "Khalil", "Bazzi", "Haddad", "Mouawad", "Rizk", "Salloum", "Tannous", "Chamoun",
    "Fakhry", "Makki", "Nasr", "Sfeir", "Rahhal", "Karam", "Zahra", "Moussa",
    "Daher", "Hajjar", "Maalouf", "Sarkis", "Boutros", "Touma", "Assaf", "Kanaan"
]

# Medicine/Pharmacy products
MEDICINE_NAMES = [
    "Paracetamol 500mg", "Ibuprofen 400mg", "Aspirin 100mg", "Amoxicillin 500mg",
    "Ciprofloxacin 500mg", "Azithromycin 250mg", "Metformin 500mg", "Atorvastatin 20mg",
    "Omeprazole 20mg", "Lansoprazole 30mg", "Pantoprazole 40mg", "Ranitidine 150mg",
    "Cetirizine 10mg", "Loratadine 10mg", "Fexofenadine 180mg", "Montelukast 10mg",
    "Salbutamol Inhaler", "Budesonide Inhaler", "Fluticasone Nasal Spray", "Beclomethasone",
    "Insulin Glargine", "Insulin Lispro", "Metformin XR 500mg", "Glibenclamide 5mg",
    "Amlodipine 5mg", "Losartan 50mg", "Enalapril 10mg", "Hydrochlorothiazide 25mg",
    "Warfarin 5mg", "Clopidogrel 75mg", "Aspirin 81mg", "Atorvastatin 40mg",
    "Simvastatin 20mg", "Rosuvastatin 10mg", "Levothyroxine 50mcg", "Prednisolone 5mg",
    "Dexamethasone 0.5mg", "Hydrocortisone Cream", "Clotrimazole Cream", "Miconazole Cream",
    "Vitamin D3 1000IU", "Calcium 500mg", "Iron 65mg", "Folic Acid 5mg",
    "Multivitamin", "Vitamin C 1000mg", "Zinc 50mg", "Magnesium 400mg",
    "Probiotics", "Lactulose Syrup", "Senna Tablets", "Bisacodyl 5mg",
    "Diazepam 5mg", "Alprazolam 0.5mg", "Sertraline 50mg", "Fluoxetine 20mg",
    "Amitriptyline 25mg", "Tramadol 50mg", "Codeine 30mg", "Morphine 10mg",
    "Eye Drops", "Ear Drops", "Nasal Drops", "Throat Lozenges",
    "Cough Syrup", "Expectorant", "Decongestant", "Antihistamine Syrup",
    "Bandages", "Gauze", "Medical Tape", "Antiseptic Solution",
    "Thermometer", "Blood Pressure Cuff", "Glucose Test Strips", "Syringes"
]

CATEGORIES = [
    "Pain Relief", "Antibiotics", "Cardiovascular", "Diabetes", "Respiratory",
    "Digestive", "Vitamins", "Skin Care", "Mental Health", "Medical Supplies"
]

def generate_phone():
    """Generate a Lebanese phone number"""
    prefixes = ["03", "70", "71", "76", "78", "79", "81"]
    prefix = random.choice(prefixes)
    number = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"+961 {prefix} {number[:3]} {number[3:]}"

def generate_email(name):
    """Generate an email from name"""
    name_parts = name.lower().replace(" ", ".")
    domains = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "live.com"]
    return f"{name_parts}@{random.choice(domains)}"

def generate_address():
    """Generate a random address"""
    streets = ["Main Street", "Beirut Street", "Corniche", "Hamra", "Achrafieh", "Verdun", "Badaro"]
    cities = ["Beirut", "Tripoli", "Sidon", "Tyre", "Jounieh", "Byblos", "Zahle"]
    return f"{random.randint(1, 200)} {random.choice(streets)}, {random.choice(cities)}"

def generate_test_data():
    """Generate comprehensive test data"""
    print("Initializing database...")
    init_db()
    
    print("\nGenerating test data...")
    print("=" * 50)
    
    # Step 1: Generate Products
    print("\n1. Generating medicine products...")
    products = []
    for i, medicine in enumerate(MEDICINE_NAMES):
        # Random price between $2 and $150
        price = round(random.uniform(2.0, 150.0), 2)
        category = random.choice(CATEGORIES)
        is_prescription = 1 if random.random() < 0.3 else 0  # 30% are prescription
        
        product_id = add_product(medicine, price, category, is_prescription)
        products.append({
            'id': product_id,
            'name': medicine,
            'price': price,
            'category': category
        })
        if (i + 1) % 10 == 0:
            print(f"   Created {i + 1} products...")
    
    print(f"✓ Created {len(products)} products")
    
    # Step 2: Generate Customers
    print("\n2. Generating customers...")
    customers = []
    for i in range(500):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"
        phone = generate_phone()
        email = generate_email(name) if random.random() < 0.7 else None  # 70% have email
        address = generate_address() if random.random() < 0.6 else None  # 60% have address
        credit_limit = round(random.uniform(200.0, 2000.0), 2)
        
        customer_id = add_customer(
            name=name,
            phone=phone,
            email=email,
            address=address,
            credit_limit=credit_limit
        )
        customers.append(customer_id)
        
        if (i + 1) % 50 == 0:
            print(f"   Created {i + 1} customers...")
    
    print(f"✓ Created {len(customers)} customers")
    
    # Step 3: Generate Transactions (Debts and Payments)
    print("\n3. Generating transactions...")
    
    # Get all products for transactions
    all_products = get_all_products()
    if not all_products:
        print("ERROR: No products found! Cannot generate transactions.")
        return
    
    total_transactions = 0
    total_payments = 0
    
    # Generate transactions for each customer
    for i, customer_id in enumerate(customers):
        # Each customer gets 0-10 debt transactions
        num_debts = random.randint(0, 10)
        
        # Generate transactions over the past 6 months
        start_date = datetime.now() - timedelta(days=180)
        
        for j in range(num_debts):
            # Random date in the past 6 months
            days_ago = random.randint(0, 180)
            transaction_date = start_date + timedelta(days=days_ago)
            debt_date = transaction_date.strftime('%Y-%m-%d')
            
            # Random number of items (1-5)
            num_items = random.randint(1, 5)
            items = []
            
            for _ in range(num_items):
                product = random.choice(all_products)
                quantity = random.randint(1, 3)
                items.append({
                    'product_name': product['name'],
                    'price': product['price'],
                    'quantity': quantity
                })
            
            # Add some notes occasionally
            notes = None
            if random.random() < 0.3:  # 30% have notes
                note_options = [
                    "Regular customer",
                    "Follow up needed",
                    "Insurance coverage",
                    "Family discount applied",
                    "Urgent delivery"
                ]
                notes = random.choice(note_options)
            
            try:
                add_debt(
                    customer_id=customer_id,
                    items=items,
                    notes=notes,
                    debt_date=debt_date
                )
                total_transactions += 1
            except Exception as e:
                print(f"   Warning: Could not add debt for customer {customer_id}: {e}")
        
        # Some customers make payments (60% of customers with debt)
        if num_debts > 0 and random.random() < 0.6:
            # Generate 0-5 payments per customer
            num_payments = random.randint(0, 5)
            
            for k in range(num_payments):
                # Get current balance to ensure payment doesn't exceed it
                current_balance = get_customer_balance(customer_id)
                
                # Skip if no balance
                if current_balance <= 0:
                    break
                
                # Payment amount between 10% and 100% of balance (but max $500)
                max_payment = min(current_balance, 500.0)
                min_payment = min(10.0, current_balance * 0.1)
                payment_amount = round(random.uniform(min_payment, max_payment), 2)
                
                # Ensure payment doesn't exceed balance
                if payment_amount > current_balance:
                    payment_amount = round(current_balance, 2)
                
                if payment_amount <= 0:
                    break
                
                payment_methods = ['CASH', 'CARD', 'CHECK']
                payment_method = random.choice(payment_methods)
                
                payment_notes = None
                if random.random() < 0.2:  # 20% have notes
                    payment_notes = random.choice([
                        "Partial payment",
                        "Full payment",
                        "Monthly installment",
                        "Cash payment"
                    ])
                
                try:
                    add_payment(
                        customer_id=customer_id,
                        amount=payment_amount,
                        payment_method=payment_method,
                        notes=payment_notes
                    )
                    total_payments += 1
                except Exception as e:
                    # Payment might fail due to validation - that's okay, skip it
                    break  # Break if payment fails (likely balance issue)
        
        if (i + 1) % 50 == 0:
            print(f"   Processed {i + 1} customers ({total_transactions} debts, {total_payments} payments)...")
    
    print(f"\n✓ Generated {total_transactions} debt transactions")
    print(f"✓ Generated {total_payments} payment transactions")
    
    print("\n" + "=" * 50)
    print("Test data generation complete!")
    print(f"\nSummary:")
    print(f"  - Customers: {len(customers)}")
    print(f"  - Products: {len(products)}")
    print(f"  - Debt Transactions: {total_transactions}")
    print(f"  - Payment Transactions: {total_payments}")
    print("\nYou can now test the application with this data!")

if __name__ == "__main__":
    print("=" * 50)
    print("TEST DATA GENERATION SCRIPT")
    print("=" * 50)
    print("\nThis script will generate:")
    print("  - 500 customers")
    print("  - ~70 medicine products")
    print("  - Thousands of debt transactions")
    print("  - Hundreds of payment transactions")
    print("\n⚠️  WARNING: This will add a large amount of data to your database!")
    print("   Make sure you have a backup if needed.\n")
    
    response = input("Do you want to continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Generation cancelled.")
        sys.exit(0)
    
    try:
        generate_test_data()
    except KeyboardInterrupt:
        print("\n\nGeneration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

