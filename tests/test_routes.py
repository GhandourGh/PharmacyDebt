"""End-to-end tests — simulate real user actions through Flask routes."""

import pytest
import database as db


# ══════════════════════════════════════════════════════════════════
#  DASHBOARD & NAVIGATION
# ══════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_dashboard_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"dashboard" in resp.data.lower() or b"total" in resp.data.lower()

    def test_analytics_loads(self, client):
        resp = client.get("/analytics")
        assert resp.status_code == 200

    def test_dashboard_stats_api(self, client):
        resp = client.get("/api/dashboard-stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "weekly" in data
        assert "top_debtors" in data
        assert "monthly" in data


# ══════════════════════════════════════════════════════════════════
#  SEARCH API
# ══════════════════════════════════════════════════════════════════

class TestSearchAPI:
    def test_search_returns_json(self, client):
        db.add_customer("Searchable Person", phone="555-9876")
        resp = client.get("/api/search?q=Searchable")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1
        assert data[0]["name"] == "Searchable Person"

    def test_search_empty_query(self, client):
        resp = client.get("/api/search?q=")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  CUSTOMER ROUTES
# ══════════════════════════════════════════════════════════════════

class TestCustomerRoutes:
    def test_customers_list_page(self, client):
        resp = client.get("/customers")
        assert resp.status_code == 200

    def test_add_customer_get(self, client):
        resp = client.get("/customers/add")
        assert resp.status_code == 200

    def test_add_customer_post(self, client):
        resp = client.post("/customers/add", data={
            "name": "New Customer",
            "phone": "555-0001",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"New Customer" in resp.data
        customers = db.get_all_customers()
        assert any(c["name"] == "New Customer" for c in customers)

    def test_add_customer_missing_name(self, client):
        resp = client.post("/customers/add", data={
            "name": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"required" in resp.data.lower() or b"error" in resp.data.lower()

    def test_customer_detail_page(self, client, sample_customer):
        resp = client.get(f"/customers/{sample_customer['id']}")
        assert resp.status_code == 200
        assert sample_customer["name"].encode() in resp.data

    def test_customer_detail_nonexistent(self, client):
        resp = client.get("/customers/99999", follow_redirects=True)
        assert resp.status_code == 200

    def test_edit_customer_get(self, client, sample_customer):
        resp = client.get(f"/customers/{sample_customer['id']}/edit")
        assert resp.status_code == 200

    def test_edit_customer_post(self, client, sample_customer):
        resp = client.post(
            f"/customers/{sample_customer['id']}/edit",
            data={"name": "Updated Name", "phone": "555-9999"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        c = db.get_customer(sample_customer["id"])
        assert c["name"] == "Updated Name"

    def test_delete_customer(self, client, sample_customer):
        resp = client.post(
            f"/customers/{sample_customer['id']}/delete",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert all(c["id"] != sample_customer["id"] for c in db.get_all_customers())

    def test_customers_pagination(self, client):
        for i in range(15):
            db.add_customer(f"Customer {i}")
        resp = client.get("/customers?page=1&per_page=5")
        assert resp.status_code == 200
        resp2 = client.get("/customers?page=2&per_page=5")
        assert resp2.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  DEBT ROUTES
# ══════════════════════════════════════════════════════════════════

class TestDebtRoutes:
    def test_add_debt_post(self, client, sample_customer):
        cid = sample_customer["id"]
        resp = client.post(f"/customers/{cid}/add-debt", data={
            "product_name_0": "TestDrug",
            "price_0": "25.00",
            "quantity_0": "1",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(25.0)

    def test_add_debt_multiple_items(self, client, sample_customer):
        cid = sample_customer["id"]
        resp = client.post(f"/customers/{cid}/add-debt", data={
            "product_name_0": "Drug A",
            "price_0": "10.00",
            "quantity_0": "2",
            "product_name_1": "Drug B",
            "price_1": "5.00",
            "quantity_1": "1",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(25.0)

    def test_add_debt_with_date(self, client, sample_customer):
        cid = sample_customer["id"]
        resp = client.post(f"/customers/{cid}/add-debt", data={
            "product_name_0": "Dated Drug",
            "price_0": "15.00",
            "quantity_0": "1",
            "debt_date": "2025-01-20",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_add_debt_no_items_fails(self, client, sample_customer):
        cid = sample_customer["id"]
        resp = client.post(f"/customers/{cid}/add-debt", data={},
                           follow_redirects=True)
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  PAYMENT ROUTES
# ══════════════════════════════════════════════════════════════════

class TestPaymentRoutes:
    def test_add_payment_post(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        resp = client.post(f"/customers/{cid}/add-payment", data={
            "amount": "10.00",
            "payment_method": "CASH",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(15.98, abs=0.01)

    def test_add_payment_overpayment_error(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        resp = client.post(f"/customers/{cid}/add-payment", data={
            "amount": "999.99",
            "payment_method": "CASH",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"exceeds" in resp.data.lower() or b"error" in resp.data.lower()

    def test_mark_paid(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        resp = client.post(f"/customers/{cid}/mark-paid", follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(0.0, abs=0.01)

    def test_mark_paid_zero_balance(self, client, sample_customer):
        cid = sample_customer["id"]
        resp = client.post(f"/customers/{cid}/mark-paid", follow_redirects=True)
        assert resp.status_code == 200

    def test_add_payment_ajax(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        resp = client.post(
            f"/customers/{cid}/add-payment",
            data={"amount": "5.00", "payment_method": "CARD"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True


# ══════════════════════════════════════════════════════════════════
#  CREDIT ROUTES
# ══════════════════════════════════════════════════════════════════

class TestCreditRoutes:
    def test_add_credit(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        original = db.get_customer_balance(cid)
        resp = client.post(f"/customers/{cid}/add-credit", data={
            "amount": "10.00",
            "payer_name": "InsuranceCo",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(original - 10.0, abs=0.01)


# ══════════════════════════════════════════════════════════════════
#  LEDGER EDIT / VOID / DELETE ROUTES
# ══════════════════════════════════════════════════════════════════

class TestLedgerRoutes:
    def test_void_entry(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        resp = client.post(f"/ledger/{lid}/void", data={
            "customer_id": str(cid),
            "reason": "mistake",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_unvoid_entry(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        db.void_entry(lid, "mistake")
        resp = client.post(f"/ledger/{lid}/unvoid", data={
            "customer_id": str(cid),
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_entry(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        resp = client.post(f"/ledger/{lid}/delete", data={
            "customer_id": str(cid),
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_edit_debt_entry(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        resp = client.post(f"/ledger/{lid}/edit", data={
            "customer_id": str(cid),
            "entry_type": "NEW_DEBT",
            "items[0][product_name]": "Updated Drug",
            "items[0][price]": "50.00",
            "items[0][quantity]": "1",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_edit_payment_entry(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        db.add_payment(cid, 10.0)
        ledger = db.get_customer_ledger(cid, include_voided=True)
        payment = next(e for e in ledger if e["entry_type"] == "PAYMENT")
        resp = client.post(f"/ledger/{payment['id']}/edit", data={
            "customer_id": str(cid),
            "entry_type": "PAYMENT",
            "amount": "15.00",
        }, follow_redirects=True)
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  PRODUCT ROUTES
# ══════════════════════════════════════════════════════════════════

class TestProductRoutes:
    def test_products_page(self, client):
        resp = client.get("/products")
        assert resp.status_code == 200

    def test_add_product_get(self, client):
        resp = client.get("/products/add")
        assert resp.status_code == 200

    def test_add_product_post(self, client):
        resp = client.post("/products/add", data={
            "name": "NewDrug",
            "price": "19.99",
        }, follow_redirects=True)
        assert resp.status_code == 200
        products = db.get_all_products()
        assert any(p["name"] == "NewDrug" for p in products)

    def test_add_product_missing_name(self, client):
        resp = client.post("/products/add", data={
            "name": "",
            "price": "10",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_edit_product_get(self, client, sample_product):
        resp = client.get(f"/products/{sample_product['id']}/edit")
        assert resp.status_code == 200

    def test_edit_product_post(self, client, sample_product):
        pid = sample_product["id"]
        resp = client.post(f"/products/{pid}/edit", data={
            "name": "Aspirin Plus",
            "price": "14.99",
        }, follow_redirects=True)
        assert resp.status_code == 200
        p = db.get_product(pid)
        assert p["name"] == "Aspirin Plus"

    def test_delete_product(self, client, sample_product):
        pid = sample_product["id"]
        resp = client.post(f"/products/{pid}/delete", follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_product(pid) is None

    def test_product_api(self, client, sample_product):
        resp = client.get(f"/api/products/{sample_product['id']}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Aspirin"

    def test_product_api_not_found(self, client):
        resp = client.get("/api/products/99999")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════
#  REPORTS ROUTES
# ══════════════════════════════════════════════════════════════════

class TestReportRoutes:
    def test_reports_transactions(self, client):
        resp = client.get("/reports")
        assert resp.status_code == 200

    def test_reports_aging(self, client):
        resp = client.get("/reports?type=aging")
        assert resp.status_code == 200

    def test_reports_overdue(self, client):
        resp = client.get("/reports?type=overdue")
        assert resp.status_code == 200

    def test_reports_daily(self, client):
        resp = client.get("/reports?type=daily")
        assert resp.status_code == 200

    def test_reports_with_date_range(self, client):
        resp = client.get("/reports?start_date=2025-01-01&end_date=2025-12-31")
        assert resp.status_code == 200

    def test_reports_invalid_date_range(self, client):
        resp = client.get("/reports?start_date=2025-12-31&end_date=2025-01-01",
                          follow_redirects=True)
        assert resp.status_code == 200

    def test_reports_with_customer_filter(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        resp = client.get(f"/reports?customer_id={cid}")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  PDF EXPORT ROUTES
# ══════════════════════════════════════════════════════════════════

class TestPDFExportRoutes:
    def test_export_report_pdf(self, client, customer_with_debt):
        resp = client.get("/reports/export-pdf?start_date=2020-01-01&end_date=2030-12-31")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_export_customer_pdf(self, client, customer_with_debt):
        cid = customer_with_debt["id"]
        resp = client.get(f"/customers/{cid}/export-pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_export_aging_pdf(self, client, customer_with_debt):
        resp = client.get("/reports/export-aging-pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

    def test_export_overdue_pdf(self, client, customer_with_debt):
        resp = client.get("/reports/export-overdue-pdf")
        assert resp.status_code == 200

    def test_download_all_debts_pdf(self, client, customer_with_debt):
        resp = client.get("/reports/download-all-debts")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"


# ══════════════════════════════════════════════════════════════════
#  DONATION ROUTES
# ══════════════════════════════════════════════════════════════════

class TestDonationRoutes:
    def test_donations_page(self, client):
        resp = client.get("/donations")
        assert resp.status_code == 200

    def test_add_donation_get(self, client):
        resp = client.get("/donations/add")
        assert resp.status_code == 200

    def test_add_donation_post(self, client):
        resp = client.post("/donations/add", data={
            "amount": "250.00",
            "donor_name": "Test Donor",
            "notes": "Monthly",
        }, follow_redirects=True)
        assert resp.status_code == 200
        donations = db.get_all_donations()
        assert any(d["donor_name"] == "Test Donor" for d in donations)

    def test_add_donation_invalid(self, client):
        resp = client.post("/donations/add", data={
            "amount": "",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_use_donation_get(self, client, sample_donation):
        resp = client.get(f"/donations/{sample_donation['id']}/use")
        assert resp.status_code == 200

    def test_use_donation_post(self, client, sample_donation, customer_with_debt):
        cid = customer_with_debt["id"]
        resp = client.post(f"/donations/{sample_donation['id']}/use", data={
            "customer_id": str(cid),
            "amount": "10.00",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(15.98, abs=0.01)

    def test_use_donation_invalid_customer(self, client, sample_donation):
        resp = client.post(f"/donations/{sample_donation['id']}/use", data={
            "customer_id": "",
            "amount": "10.00",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_use_donation_nonexistent(self, client):
        resp = client.get("/donations/99999/use", follow_redirects=True)
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  SETTINGS & ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════

class TestSettingsRoutes:
    def test_settings_page(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200

    def test_export_backup(self, client, customer_with_debt):
        resp = client.get("/settings/export-backup")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type

    def test_import_backup_no_file(self, client):
        resp = client.post("/settings/import-backup", follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_all_customers_requires_confirm(self, client, customer_with_debt):
        resp = client.post("/admin/delete-all-customers", data={
            "confirm": "no",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert len(db.get_all_customers()) > 0

    def test_delete_all_customers_confirmed(self, client, customer_with_debt):
        resp = client.post("/admin/delete-all-customers", data={
            "confirm": "delete all",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert len(db.get_all_customers()) == 0

    def test_create_demo_data(self, client):
        resp = client.post("/admin/create-demo-data", follow_redirects=True)
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  FULL USER JOURNEY (E2E scenario)
# ══════════════════════════════════════════════════════════════════

class TestFullUserJourney:
    """Simulates a pharmacist's typical session."""

    def test_pharmacist_daily_workflow(self, client):
        # 1. Open dashboard
        resp = client.get("/")
        assert resp.status_code == 200

        # 2. Add a new customer
        resp = client.post("/customers/add", data={
            "name": "Ahmad Hassan",
            "phone": "555-0200",
        }, follow_redirects=True)
        assert resp.status_code == 200
        customer = db.search_customers("Ahmad")[0]
        cid = customer["id"]

        # 3. Add products
        client.post("/products/add", data={"name": "Amoxicillin", "price": "15.50"})
        client.post("/products/add", data={"name": "Paracetamol", "price": "3.00"})

        # 4. Record a debt (prescription)
        resp = client.post(f"/customers/{cid}/add-debt", data={
            "product_name_0": "Amoxicillin",
            "price_0": "15.50",
            "quantity_0": "1",
            "product_name_1": "Paracetamol",
            "price_1": "3.00",
            "quantity_1": "2",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(21.50)

        # 5. Customer makes partial payment
        resp = client.post(f"/customers/{cid}/add-payment", data={
            "amount": "10.00",
            "payment_method": "CASH",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(11.50)

        # 6. Check customer detail page
        resp = client.get(f"/customers/{cid}")
        assert resp.status_code == 200
        assert b"Ahmad Hassan" in resp.data

        # 7. View reports
        resp = client.get("/reports?type=daily")
        assert resp.status_code == 200

        # 8. Export PDF
        resp = client.get(f"/customers/{cid}/export-pdf")
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"

        # 9. Mark as paid
        resp = client.post(f"/customers/{cid}/mark-paid", follow_redirects=True)
        assert resp.status_code == 200
        assert db.get_customer_balance(cid) == pytest.approx(0.0, abs=0.01)

        # 10. Check dashboard stats
        resp = client.get("/api/dashboard-stats")
        assert resp.status_code == 200
