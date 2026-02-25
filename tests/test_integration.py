"""Integration tests — multi-step database flows that mirror real-world usage."""

import pytest
from datetime import datetime, timedelta
import database as db


class TestDebtPaymentLifecycle:
    """Full lifecycle: customer → debt → partial pay → more debt → full pay."""

    def test_complete_lifecycle(self, sample_customer):
        cid = sample_customer["id"]

        # 1. Add first debt ($50)
        db.add_debt(cid, [
            {"product_name": "Medicine A", "price": 30, "quantity": 1},
            {"product_name": "Medicine B", "price": 20, "quantity": 1},
        ])
        assert db.get_customer_balance(cid) == pytest.approx(50.0)

        # 2. Partial payment ($20)
        db.add_payment(cid, 20.0, payment_method="CASH")
        assert db.get_customer_balance(cid) == pytest.approx(30.0)

        # FIFO: $20 should be applied to the $50 debt
        unpaid = db.get_unpaid_debts(cid)
        assert len(unpaid) == 1
        assert unpaid[0]["remaining_amount"] == pytest.approx(30.0)
        assert unpaid[0]["payment_status"] == "PARTIAL"

        # 3. Add second debt ($25)
        db.add_debt(cid, [{"product_name": "Supplements", "price": 25, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(55.0)

        # 4. Pay off everything
        db.add_payment(cid, 55.0, payment_method="CARD")
        assert db.get_customer_balance(cid) == pytest.approx(0.0)

        unpaid = db.get_unpaid_debts(cid)
        assert len(unpaid) == 0

    def test_multiple_small_payments(self, sample_customer):
        """Several small payments chip away at one debt via FIFO."""
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "Big Rx", "price": 100, "quantity": 1}])

        for i in range(10):
            db.add_payment(cid, 10.0)

        assert db.get_customer_balance(cid) == pytest.approx(0.0)
        assert len(db.get_unpaid_debts(cid)) == 0


class TestCreditFlow:
    """Third-party credit applied before and after debts."""

    def test_credit_before_debt(self, sample_customer):
        cid = sample_customer["id"]

        # Credit first → negative balance
        db.add_credit(cid, 100.0, payer_name="InsuranceCo")
        assert db.get_customer_balance(cid) == pytest.approx(-100.0)

        # Debt of $60 → automatically consumed by credit
        db.add_debt(cid, [{"product_name": "Rx", "price": 60, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(-40.0)

        # Another debt of $50 → uses remaining $40 credit + $10 owed
        db.add_debt(cid, [{"product_name": "Rx2", "price": 50, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(10.0)

    def test_credit_after_debt_reduces_balance(self, sample_customer):
        cid = sample_customer["id"]

        db.add_debt(cid, [{"product_name": "Rx", "price": 80, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(80.0)

        db.add_credit(cid, 30.0, payer_name="Gov")
        assert db.get_customer_balance(cid) == pytest.approx(50.0)

    def test_credit_exceeding_debt(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "Small", "price": 10, "quantity": 1}])
        db.add_credit(cid, 50.0)
        assert db.get_customer_balance(cid) == pytest.approx(-40.0)


class TestDonationFlow:
    """Donation creation → applying to customer debt."""

    def test_donation_pays_customer_debt(self, sample_donation, sample_customer):
        cid = sample_customer["id"]

        # Give customer some debt
        db.add_debt(cid, [{"product_name": "RxA", "price": 100, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(100.0)

        # Use donation to pay $60
        result = db.use_donation(sample_donation["id"], cid, 60.0, notes="for patient")
        assert result["success"] is True

        # Customer balance reduced
        assert db.get_customer_balance(cid) == pytest.approx(40.0)

        # Donation remaining reduced
        d = db.get_donation(sample_donation["id"])
        assert d["amount_remaining"] == pytest.approx(440.0)

    def test_donation_cannot_exceed_debt(self, sample_donation, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "X", "price": 20, "quantity": 1}])

        result = db.use_donation(sample_donation["id"], cid, 50.0)
        assert result["success"] is False
        assert "owes" in result["message"]

    def test_donation_split_across_customers(self, sample_donation):
        c1 = db.add_customer("Patient A")
        c2 = db.add_customer("Patient B")
        db.add_debt(c1, [{"product_name": "RxA", "price": 100, "quantity": 1}])
        db.add_debt(c2, [{"product_name": "RxB", "price": 200, "quantity": 1}])

        db.use_donation(sample_donation["id"], c1, 50.0)
        db.use_donation(sample_donation["id"], c2, 100.0)

        d = db.get_donation(sample_donation["id"])
        assert d["amount_remaining"] == pytest.approx(350.0)
        assert db.get_customer_balance(c1) == pytest.approx(50.0)
        assert db.get_customer_balance(c2) == pytest.approx(100.0)


class TestVoidAndDeleteFlow:
    """Voiding and deleting entries in realistic scenarios."""

    def test_void_excludes_from_balance(self, sample_customer):
        """Voided entries are excluded from balance by get_customer_balance (is_voided=0 filter)."""
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "A", "price": 50, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(50.0)

        ledger = db.get_customer_ledger(cid, include_voided=True)
        db.void_entry(ledger[0]["id"], "error")

        assert db.get_customer_balance(cid) == pytest.approx(0.0)

    def test_void_then_unvoid(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "B", "price": 30, "quantity": 1}])
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]

        db.void_entry(lid, "mistake")
        assert len(db.get_customer_ledger(cid, include_voided=False)) == 0

        db.unvoid_entry(lid)
        assert len(db.get_customer_ledger(cid, include_voided=False)) == 1


class TestEditEntryRebalancing:
    """Editing entries triggers balance recalculation."""

    def test_edit_debt_amount_updates_balance(self, sample_customer):
        cid = sample_customer["id"]
        lid = db.add_debt(cid, [{"product_name": "X", "price": 100, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(100.0)

        db.update_debt_entry(lid, [{"product_name": "X", "price": 150, "quantity": 1}])
        assert db.get_customer_balance(cid) == pytest.approx(150.0)

    def test_edit_payment_amount_updates_balance(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "X", "price": 100, "quantity": 1}])
        pid = db.add_payment(cid, 40.0)
        assert db.get_customer_balance(cid) == pytest.approx(60.0)

        db.update_payment_entry(pid, 60.0)
        assert db.get_customer_balance(cid) == pytest.approx(40.0)

    def test_fifo_recalculated_after_debt_edit(self, sample_customer):
        cid = sample_customer["id"]
        d1 = db.add_debt(cid, [{"product_name": "D1", "price": 30, "quantity": 1}])
        db.add_debt(cid, [{"product_name": "D2", "price": 20, "quantity": 1}])
        db.add_payment(cid, 30.0)

        # D1 should be PAID, D2 OPEN
        unpaid = db.get_unpaid_debts(cid)
        assert len(unpaid) == 1

        # Increase D1 from 30→60: now FIFO must recalculate
        db.update_debt_entry(d1, [{"product_name": "D1", "price": 60, "quantity": 1}])
        unpaid = db.get_unpaid_debts(cid)
        remaining = sum(u["remaining_amount"] for u in unpaid)
        assert remaining == pytest.approx(50.0, abs=0.01)


class TestMultiCustomerIsolation:
    """Operations on one customer must not affect another."""

    def test_balances_isolated(self):
        c1 = db.add_customer("Customer A")
        c2 = db.add_customer("Customer B")

        db.add_debt(c1, [{"product_name": "A", "price": 100, "quantity": 1}])
        db.add_debt(c2, [{"product_name": "B", "price": 200, "quantity": 1}])

        assert db.get_customer_balance(c1) == pytest.approx(100.0)
        assert db.get_customer_balance(c2) == pytest.approx(200.0)

        db.add_payment(c1, 50.0)
        assert db.get_customer_balance(c1) == pytest.approx(50.0)
        assert db.get_customer_balance(c2) == pytest.approx(200.0)

    def test_total_debt_sums_all(self):
        c1 = db.add_customer("X")
        c2 = db.add_customer("Y")
        db.add_debt(c1, [{"product_name": "A", "price": 40, "quantity": 1}])
        db.add_debt(c2, [{"product_name": "B", "price": 60, "quantity": 1}])
        assert db.get_total_debt_all() == pytest.approx(100.0)


class TestBackupRestore:
    """CSV export and import round-trip."""

    def test_export_produces_csv(self, customer_with_debt):
        csv_data = db.export_all_data_to_csv()
        assert "=== CUSTOMERS ===" in csv_data
        assert "John Doe" in csv_data

    def test_import_restores_customers(self, customer_with_debt):
        csv_data = db.export_all_data_to_csv()
        db.delete_all_customer_data()
        assert len(db.get_all_customers()) == 0

        result = db.import_data_from_csv(csv_data)
        assert result["success"] is True
        customers = db.get_all_customers()
        assert any(c["name"] == "John Doe" for c in customers)


class TestDeleteAllCustomerData:
    def test_wipes_everything(self, customer_with_debt, sample_donation):
        cid = customer_with_debt["id"]
        db.use_donation(sample_donation["id"], cid, 5.0)

        db.delete_all_customer_data()
        assert len(db.get_all_customers()) == 0
        assert db.get_total_debt_all() == 0.0


# ══════════════════════════════════════════════════════════════════
#  REGRESSION: Overdue report (was crashing with HAVING without GROUP BY)
# ══════════════════════════════════════════════════════════════════

class TestOverdueReport:
    def test_overdue_empty_db(self):
        """get_overdue_customers must not crash on an empty database."""
        result = db.get_overdue_customers(30)
        assert result == []

    def test_overdue_no_old_debts(self, sample_customer):
        """Debts created today should not appear in the 30-day overdue report."""
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "Fresh", "price": 50, "quantity": 1}])
        result = db.get_overdue_customers(30)
        assert len(result) == 0

    def test_overdue_with_old_debt(self, sample_customer):
        """A debt older than the threshold must appear."""
        cid = sample_customer["id"]
        old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        db.add_debt(cid, [{"product_name": "Old Rx", "price": 40, "quantity": 1}],
                    debt_date=old_date)
        result = db.get_overdue_customers(30)
        assert len(result) == 1
        assert result[0]["id"] == cid
        assert result[0]["debt"] == pytest.approx(40.0)

    def test_overdue_excludes_paid_customers(self, sample_customer):
        """Customers whose old debts are fully paid should not appear."""
        cid = sample_customer["id"]
        old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        db.add_debt(cid, [{"product_name": "Paid Rx", "price": 30, "quantity": 1}],
                    debt_date=old_date)
        db.add_payment(cid, 30.0)
        result = db.get_overdue_customers(30)
        assert len(result) == 0

    def test_overdue_excludes_deleted_entries(self, sample_customer):
        """Deleted debts must not cause a customer to appear as overdue."""
        cid = sample_customer["id"]
        old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        lid = db.add_debt(cid, [{"product_name": "Deleted", "price": 20, "quantity": 1}],
                          debt_date=old_date)
        db.delete_ledger_entry(lid)
        result = db.get_overdue_customers(30)
        assert len(result) == 0


# ══════════════════════════════════════════════════════════════════
#  REGRESSION: is_deleted consistency across all balance queries
# ══════════════════════════════════════════════════════════════════

class TestDeletedEntryConsistency:
    """Deleted entries must be excluded from balance everywhere, not just get_customer_balance."""

    def test_deleted_excluded_from_recent_active(self):
        """get_recent_active_customers must not count deleted entries in debt."""
        cid = db.add_customer("DeletedDebtCustomer")
        lid = db.add_debt(cid, [{"product_name": "X", "price": 100, "quantity": 1}])
        db.delete_ledger_entry(lid)

        recent = db.get_recent_active_customers(10)
        match = [c for c in recent if c["id"] == cid]
        if match:
            assert match[0]["debt"] == pytest.approx(0.0)

    def test_deleted_excluded_from_donation_balance_check(self, sample_donation):
        """use_donation balance check must not count deleted entries."""
        cid = db.add_customer("DonationTest")
        lid = db.add_debt(cid, [{"product_name": "Y", "price": 50, "quantity": 1}])
        db.delete_ledger_entry(lid)

        result = db.use_donation(sample_donation["id"], cid, 10.0)
        assert result["success"] is False
        assert "owes" in result["message"]

    def test_balance_consistent_across_functions(self):
        """All balance-related functions must agree after a deletion."""
        cid = db.add_customer("ConsistencyTest")
        db.add_debt(cid, [{"product_name": "Keep", "price": 80, "quantity": 1}])
        lid2 = db.add_debt(cid, [{"product_name": "Remove", "price": 20, "quantity": 1}])
        db.delete_ledger_entry(lid2)

        balance = db.get_customer_balance(cid)
        assert balance == pytest.approx(80.0)

        cwd = db.get_customers_with_debt()
        match = [c for c in cwd if c["id"] == cid]
        assert match[0]["debt"] == pytest.approx(80.0)

        recent = db.get_recent_active_customers(10)
        match_r = [c for c in recent if c["id"] == cid]
        assert match_r[0]["debt"] == pytest.approx(80.0)
