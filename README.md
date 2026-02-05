# Pharmacy Debt Management System

A comprehensive Flask-based web application for managing customer debts, payments, products, and donations for a pharmacy.

## Features

- **Customer Management**: Add, edit, and manage customer profiles with profile images
- **Debt Tracking**: Record customer debts with multiple items per transaction
- **Payment Processing**: Record payments with multiple payment methods (Cash, Card, Check, Credit, Split)
- **Product Management**: Maintain a catalog of products with prices
- **Reports & Analytics**: Generate reports and view analytics with charts
- **Donation Management**: Track donations and apply them to customer debts
- **PDF Export**: Export customer reports and debt reports as PDFs
- **Daily Reconciliation**: Track daily debt additions and payments

## Requirements

- Python 3.7+
- Flask
- ReportLab (for PDF generation)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/GhandourGh/PharmacyDebt.git
cd PharmacyDebt/pharmacy-debt-system
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Initialize the database (runs automatically on first start):
The database will be created automatically when you run the application.

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Access the application:
Open your browser and navigate to `http://localhost:5001`

## Project Structure

```
pharmacy-debt-system/
├── app.py                 # Main Flask application
├── database.py            # Database operations
├── validators.py          # Input validation
├── pdf_export.py          # PDF generation
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
├── static/               # CSS, JS, and uploaded files
└── pharmacy.db           # SQLite database (created automatically)
```

## Features Overview

### Dashboard
- View total outstanding debt
- See recent customer activity
- Daily reconciliation statistics
- Quick access to common actions

### Customers
- Add new customers with profile images
- View customer details and transaction history
- Record debts and payments
- Edit customer information
- Export customer reports as PDF

### Products
- Add, edit, and delete products
- Product catalog management

### Reports
- Transaction reports by date range
- Aging reports (0-30, 31-60, 61-90, 90+ days)
- Overdue customer reports
- Daily reconciliation reports
- PDF export functionality

### Analytics
- Weekly and monthly trends
- Top debtors visualization
- Debt vs payments comparison

### Donations
- Track donations received
- Apply donations to customer debts
- View donation usage history

## Database Schema

The system uses SQLite with the following main tables:
- `customers` - Customer information
- `products` - Product catalog
- `ledger` - All financial transactions
- `ledger_items` - Line items for debt entries
- `donations` - Donation records
- `donation_usage` - Donation application tracking
- `settings` - System configuration

## Security Notes

- Secret key should be set via environment variable `SECRET_KEY` in production
- Admin routes should be protected in production environments
- File uploads are validated for type and size (max 5MB)

## License

This project is for internal pharmacy use.

