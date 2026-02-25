"""Unit tests for database.py — CRUD operations, balance calc, FIFO, and helpers."""

import pytest
import database as db


# ══════════════════════════════════════════════════════════════════
#  SCHEMA & INIT
# ══════════════════════════════════════════════════════════════════

class TestInitDB:
    def test_default_admin_created(self):
        user = db.authenticate_user("admin", "admin123")
        assert user is not None
        assert user["role"] == "admin"

    def test_default_settings_exist(self):
        assert db.get_setting("default_credit_limit") == "500.00"
        assert db.get_setting("default_grace_period") == "7"

    def test_reinit_is_idempotent(self):
        db.init_db()
        users = db.get_all_users()
        admin_count = sum(1 for u in users if u["username"] == "admin")
        assert admin_count == 1


# ══════════════════════════════════════════════════════════════════
#  USER OPERATIONS
# ══════════════════════════════════════════════════════════════════

class TestUserOps:
    def test_add_and_get_user(self):
        uid = db.add_user("clerk1", "pass", "First Clerk", "clerk")
        user = db.get_user(uid)
        assert user["username"] == "clerk1"
        assert user["role"] == "clerk"

    def test_authenticate_valid(self):
        db.add_user("authtest", "secret", "Auth User", "manager")
        user = db.authenticate_user("authtest", "secret")
        assert user is not None
        assert user["full_name"] == "Auth User"

    def test_authenticate_wrong_password(self):
        db.add_user("authtest2", "right", "User", "clerk")
        assert db.authenticate_user("authtest2", "wrong") is None

    def test_authenticate_inactive_user(self):
        uid = db.add_user("inactive", "pass", "Gone", "clerk")
        db.update_user(uid, "Gone", "clerk", 0)
        assert db.authenticate_user("inactive", "pass") is None

    def test_update_user(self):
        uid = db.add_user("u1", "p", "Name", "clerk")
        db.update_user(uid, "New Name", "manager", 1)
        user = db.get_user(uid)
        assert user["full_name"] == "New Name"
        assert user["role"] == "manager"

    def test_change_password(self):
        uid = db.add_user("cptest", "old", "CP", "clerk")
        db.change_password(uid, "new")
        assert db.authenticate_user("cptest", "new") is not None
        assert db.authenticate_user("cptest", "old") is None

    def test_get_all_users(self):
        before = len(db.get_all_users())
        db.add_user("extra1", "p", "E1", "clerk")
        db.add_user("extra2", "p", "E2", "manager")
        assert len(db.get_all_users()) == before + 2


# ══════════════════════════════════════════════════════════════════
#  CUSTOMER OPERATIONS
# ══════════════════════════════════════════════════════════════════

class TestCustomerOps:
    def test_add_and_get(self, sample_customer):
        assert sample_customer["name"] == "John Doe"
        assert sample_customer["phone"] == "555-0100"
        assert sample_customer["credit_limit"] == 1000.0

    def test_update_customer(self, sample_customer):
        cid = sample_customer["id"]
        db.update_customer(cid, "Jane Doe", phone="555-9999", credit_limit=2000)
        updated = db.get_customer(cid)
        assert updated["name"] == "Jane Doe"
        assert updated["phone"] == "555-9999"
        assert updated["credit_limit"] == 2000.0

    def test_deactivate_customer(self, sample_customer):
        cid = sample_customer["id"]
        db.deactivate_customer(cid)
        active = db.get_all_customers()
        assert all(c["id"] != cid for c in active)

    def test_get_all_customers_excludes_inactive(self):
        c1 = db.add_customer("Active")
        c2 = db.add_customer("Inactive")
        db.deactivate_customer(c2)
        customers = db.get_all_customers()
        ids = [c["id"] for c in customers]
        assert c1 in ids
        assert c2 not in ids

    def test_search_by_name(self):
        db.add_customer("Alice Smith", phone="111")
        db.add_customer("Bob Jones", phone="222")
        results = db.search_customers("Alice")
        assert len(results) == 1
        assert results[0]["name"] == "Alice Smith"

    def test_search_by_phone(self):
        db.add_customer("Charlie", phone="555-1234")
        results = db.search_customers("1234")
        assert len(results) == 1

    def test_get_nonexistent(self):
        assert db.get_customer(99999) is None

    def test_profile_image(self):
        cid = db.add_customer("WithImage", profile_image="pic.jpg")
        c = db.get_customer(cid)
        assert c["profile_image"] == "pic.jpg"


# ══════════════════════════════════════════════════════════════════
#  PRODUCT OPERATIONS
# ══════════════════════════════════════════════════════════════════

class TestProductOps:
    def test_add_and_get(self, sample_product):
        assert sample_product["name"] == "Aspirin"
        assert sample_product["price"] == 9.99

    def test_update_product(self, sample_product):
        pid = sample_product["id"]
        db.update_product(pid, "Aspirin Extra", 12.99, category="OTC")
        p = db.get_product(pid)
        assert p["name"] == "Aspirin Extra"
        assert p["price"] == 12.99

    def test_delete_product(self, sample_product):
        pid = sample_product["id"]
        db.delete_product(pid)
        assert db.get_product(pid) is None

    def test_get_all_products(self):
        db.add_product("P1", 1.0)
        db.add_product("P2", 2.0)
        products = db.get_all_products()
        names = [p["name"] for p in products]
        assert "P1" in names and "P2" in names


# ══════════════════════════════════════════════════════════════════
#  BALANCE CALCULATION
# ══════════════════════════════════════════════════════════════════

class TestBalance:
    def test_zero_balance_initially(self, sample_customer):
        assert db.get_customer_balance(sample_customer["id"]) == 0.0

    def test_balance_after_debt(self, customer_with_debt):
        bal = db.get_customer_balance(customer_with_debt["id"])
        assert bal == pytest.approx(25.98, abs=0.01)

    def test_balance_after_payment(self, customer_with_debt):
        cid = customer_with_debt["id"]
        db.add_payment(cid, 10.0)
        assert db.get_customer_balance(cid) == pytest.approx(15.98, abs=0.01)

    def test_balance_after_full_payment(self, customer_with_debt):
        cid = customer_with_debt["id"]
        bal = db.get_customer_balance(cid)
        db.add_payment(cid, bal)
        assert db.get_customer_balance(cid) == pytest.approx(0.0, abs=0.01)

    def test_balance_after_write_off(self, customer_with_debt):
        cid = customer_with_debt["id"]
        db.write_off_debt(cid, 5.0, "uncollectable")
        assert db.get_customer_balance(cid) == pytest.approx(20.98, abs=0.01)

    def test_balance_after_adjustment(self, customer_with_debt):
        cid = customer_with_debt["id"]
        db.add_adjustment(cid, 10.0, "fee")
        assert db.get_customer_balance(cid) == pytest.approx(35.98, abs=0.01)

    def test_balance_after_refund(self, customer_with_debt):
        cid = customer_with_debt["id"]
        db.add_refund(cid, 5.0, "return")
        assert db.get_customer_balance(cid) == pytest.approx(20.98, abs=0.01)


# ══════════════════════════════════════════════════════════════════
#  DEBT OPERATIONS
# ══════════════════════════════════════════════════════════════════

class TestDebtOps:
    def test_add_debt_creates_ledger_entry(self, sample_customer):
        cid = sample_customer["id"]
        items = [{"product_name": "Med", "price": 20.0, "quantity": 1}]
        lid = db.add_debt(cid, items)
        ledger = db.get_customer_ledger(cid)
        assert any(e["id"] == lid for e in ledger)

    def test_add_debt_creates_line_items(self, sample_customer):
        cid = sample_customer["id"]
        items = [
            {"product_name": "A", "price": 10, "quantity": 2},
            {"product_name": "B", "price": 5, "quantity": 1},
        ]
        lid = db.add_debt(cid, items)
        line_items = db.get_ledger_items(lid)
        assert len(line_items) == 2
        names = {li["product_name"] for li in line_items}
        assert names == {"A", "B"}

    def test_add_debt_with_custom_date(self, sample_customer):
        cid = sample_customer["id"]
        items = [{"product_name": "X", "price": 5, "quantity": 1}]
        lid = db.add_debt(cid, items, debt_date="2025-01-15")
        ledger = db.get_customer_ledger(cid)
        entry = next(e for e in ledger if e["id"] == lid)
        assert entry["created_at"].startswith("2025-01-15")

    def test_add_debt_inactive_customer_raises(self, sample_customer):
        cid = sample_customer["id"]
        db.deactivate_customer(cid)
        with pytest.raises(ValueError, match="deactivated"):
            db.add_debt(cid, [{"product_name": "X", "price": 5, "quantity": 1}])

    def test_add_debt_nonexistent_customer_raises(self):
        with pytest.raises(ValueError, match="not found"):
            db.add_debt(99999, [{"product_name": "X", "price": 5, "quantity": 1}])

    def test_add_debt_empty_items_raises(self, sample_customer):
        with pytest.raises(ValueError, match="(?i)at least one"):
            db.add_debt(sample_customer["id"], [])


# ══════════════════════════════════════════════════════════════════
#  PAYMENT OPERATIONS
# ══════════════════════════════════════════════════════════════════

class TestPaymentOps:
    def test_add_payment(self, customer_with_debt):
        cid = customer_with_debt["id"]
        lid = db.add_payment(cid, 10.0, payment_method="CASH")
        assert lid is not None
        ledger = db.get_customer_ledger(cid)
        payment = next(e for e in ledger if e["id"] == lid)
        assert payment["entry_type"] == "PAYMENT"
        assert payment["amount"] == 10.0

    def test_overpayment_raises(self, customer_with_debt):
        cid = customer_with_debt["id"]
        bal = db.get_customer_balance(cid)
        with pytest.raises(ValueError, match="exceeds"):
            db.add_payment(cid, bal + 100)

    def test_payment_zero_balance_raises(self, sample_customer):
        with pytest.raises(ValueError, match="no outstanding"):
            db.add_payment(sample_customer["id"], 10.0)

    def test_payment_inactive_customer_raises(self, customer_with_debt):
        cid = customer_with_debt["id"]
        db.deactivate_customer(cid)
        with pytest.raises(ValueError, match="deactivated"):
            db.add_payment(cid, 5.0)


# ══════════════════════════════════════════════════════════════════
#  CREDIT OPERATIONS
# ══════════════════════════════════════════════════════════════════

class TestCreditOps:
    def test_add_credit_reduces_debt(self, customer_with_debt):
        cid = customer_with_debt["id"]
        original = db.get_customer_balance(cid)
        db.add_credit(cid, 10.0, payer_name="InsuranceCo")
        assert db.get_customer_balance(cid) == pytest.approx(original - 10.0, abs=0.01)

    def test_credit_creates_negative_balance(self, sample_customer):
        cid = sample_customer["id"]
        db.add_credit(cid, 50.0, payer_name="Govt")
        assert db.get_customer_balance(cid) == pytest.approx(-50.0, abs=0.01)

    def test_credit_auto_applies_to_future_debt(self, sample_customer):
        cid = sample_customer["id"]
        db.add_credit(cid, 100.0)
        items = [{"product_name": "Med", "price": 30.0, "quantity": 1}]
        db.add_debt(cid, items)
        assert db.get_customer_balance(cid) == pytest.approx(-70.0, abs=0.01)


# ══════════════════════════════════════════════════════════════════
#  FIFO LOGIC
# ══════════════════════════════════════════════════════════════════

class TestFIFO:
    def test_oldest_debt_paid_first(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "OldDebt", "price": 10, "quantity": 1}])
        db.add_debt(cid, [{"product_name": "NewDebt", "price": 20, "quantity": 1}])

        db.add_payment(cid, 10.0)

        unpaid = db.get_unpaid_debts(cid)
        assert len(unpaid) == 1
        assert unpaid[0]["items"][0]["product_name"] == "NewDebt"

    def test_partial_payment(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "Debt1", "price": 50, "quantity": 1}])

        db.add_payment(cid, 20.0)

        unpaid = db.get_unpaid_debts(cid)
        assert len(unpaid) == 1
        assert unpaid[0]["remaining_amount"] == pytest.approx(30.0, abs=0.01)
        assert unpaid[0]["payment_status"] == "PARTIAL"

    def test_full_payment_marks_paid(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "D", "price": 25, "quantity": 1}])
        db.add_payment(cid, 25.0)

        unpaid = db.get_unpaid_debts(cid)
        assert len(unpaid) == 0

    def test_payment_spans_multiple_debts(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "D1", "price": 10, "quantity": 1}])
        db.add_debt(cid, [{"product_name": "D2", "price": 10, "quantity": 1}])
        db.add_debt(cid, [{"product_name": "D3", "price": 10, "quantity": 1}])

        db.add_payment(cid, 15.0)

        unpaid = db.get_unpaid_debts(cid)
        assert len(unpaid) == 2
        remaining = [u["remaining_amount"] for u in unpaid]
        assert pytest.approx(5.0, abs=0.01) in remaining
        assert pytest.approx(10.0, abs=0.01) in remaining


# ══════════════════════════════════════════════════════════════════
#  VOID / UNVOID / DELETE
# ══════════════════════════════════════════════════════════════════

class TestVoidOps:
    def test_void_entry(self, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        assert db.void_entry(lid, "mistake") is True

    def test_void_hides_from_default_ledger(self, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        db.void_entry(lid, "mistake")
        visible = db.get_customer_ledger(cid, include_voided=False)
        assert all(e["id"] != lid for e in visible)

    def test_void_appears_when_include_voided(self, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        db.void_entry(lid, "mistake")
        all_entries = db.get_customer_ledger(cid, include_voided=True)
        voided = [e for e in all_entries if e["is_voided"]]
        assert len(voided) == 1

    def test_unvoid_restores(self, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        db.void_entry(lid, "mistake")
        db.unvoid_entry(lid)
        visible = db.get_customer_ledger(cid, include_voided=False)
        assert any(e["id"] == lid for e in visible)

    def test_void_already_voided_returns_false(self, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        db.void_entry(lid, "first")
        assert db.void_entry(lid, "second") is False

    def test_delete_ledger_entry(self, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        assert db.delete_ledger_entry(lid) is True
        visible = db.get_customer_ledger(cid, include_voided=True)
        assert all(e["id"] != lid for e in visible)


# ══════════════════════════════════════════════════════════════════
#  REPORTING
# ══════════════════════════════════════════════════════════════════

class TestReporting:
    def test_total_debt_all(self, customer_with_debt):
        total = db.get_total_debt_all()
        assert total == pytest.approx(25.98, abs=0.01)

    def test_total_debt_excludes_paid_customers(self, customer_with_debt):
        cid = customer_with_debt["id"]
        bal = db.get_customer_balance(cid)
        db.add_payment(cid, bal)
        assert db.get_total_debt_all() == pytest.approx(0.0, abs=0.01)

    def test_daily_reconciliation(self, customer_with_debt):
        stats = db.get_daily_reconciliation()
        assert stats["total_debt"] >= 0
        assert stats["total_payments"] >= 0
        assert "transaction_count" in stats

    def test_aging_report_structure(self, customer_with_debt):
        aging = db.get_aging_report()
        assert len(aging) >= 1
        entry = aging[0]
        assert "days_0_30" in entry
        assert "days_31_60" in entry
        assert "days_61_90" in entry
        assert "days_90_plus" in entry

    def test_recent_activity(self, customer_with_debt):
        activity = db.get_recent_activity(5)
        assert len(activity) >= 1
        assert activity[0]["entry_type"] == "NEW_DEBT"

    def test_customers_with_debt(self, customer_with_debt):
        cwd = db.get_customers_with_debt()
        found = [c for c in cwd if c["id"] == customer_with_debt["id"]]
        assert len(found) == 1
        assert found[0]["debt"] == pytest.approx(25.98, abs=0.01)

    def test_transactions_by_date(self, customer_with_debt):
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        txns = db.get_transactions_by_date(today, today)
        assert len(txns) >= 1


# ══════════════════════════════════════════════════════════════════
#  DONATION OPERATIONS
# ══════════════════════════════════════════════════════════════════

class TestDonationOps:
    def test_add_donation(self, sample_donation):
        assert sample_donation["amount"] == 500.0
        assert sample_donation["donor_name"] == "Charity Fund"
        assert sample_donation["amount_remaining"] == 500.0

    def test_get_all_donations(self):
        db.add_donation(100)
        db.add_donation(200)
        donations = db.get_all_donations()
        assert len(donations) >= 2

    def test_use_donation(self, sample_donation, customer_with_debt):
        result = db.use_donation(
            sample_donation["id"],
            customer_with_debt["id"],
            10.0,
            notes="test"
        )
        assert result["success"] is True
        updated = db.get_donation(sample_donation["id"])
        assert updated["amount_remaining"] == pytest.approx(490.0, abs=0.01)

    def test_use_donation_exceeds_remaining(self, customer_with_debt):
        did = db.add_donation(5.0)
        result = db.use_donation(did, customer_with_debt["id"], 10.0)
        assert result["success"] is False

    def test_donation_usage_history(self, sample_donation, customer_with_debt):
        db.use_donation(sample_donation["id"], customer_with_debt["id"], 5.0)
        history = db.get_donation_usage_history(sample_donation["id"])
        assert len(history) == 1
        assert history[0]["amount_used"] == 5.0

    def test_total_donations(self):
        db.add_donation(100)
        db.add_donation(200)
        assert db.get_total_donations() >= 300.0

    def test_unique_donor_names(self):
        db.add_donation(10, donor_name="Alice")
        db.add_donation(20, donor_name="Bob")
        db.add_donation(30, donor_name="Alice")
        names = db.get_unique_donor_names()
        assert "Alice" in names
        assert "Bob" in names


# ══════════════════════════════════════════════════════════════════
#  SETTINGS & AUDIT
# ══════════════════════════════════════════════════════════════════

class TestSettingsAudit:
    def test_get_set_setting(self):
        db.set_setting("test_key", "test_value")
        assert db.get_setting("test_key") == "test_value"

    def test_setting_update(self):
        db.set_setting("k", "v1")
        db.set_setting("k", "v2")
        assert db.get_setting("k") == "v2"

    def test_audit_log_created_on_debt(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "X", "price": 10, "quantity": 1}])
        logs = db.get_audit_log(limit=5)
        actions = [l["action"] for l in logs]
        assert "ADD_DEBT" in actions

    def test_audit_log_filter_by_table(self, sample_customer):
        cid = sample_customer["id"]
        db.add_debt(cid, [{"product_name": "X", "price": 10, "quantity": 1}])
        logs = db.get_audit_log(table_name="ledger")
        assert all(l["table_name"] == "ledger" for l in logs)


# ══════════════════════════════════════════════════════════════════
#  CREDIT LIMIT CHECK
# ══════════════════════════════════════════════════════════════════

class TestCreditLimit:
    def test_within_limit(self, sample_customer):
        result = db.check_credit_limit(sample_customer["id"], 100)
        assert result["allowed"] is True

    def test_exceeds_limit(self, sample_customer):
        result = db.check_credit_limit(sample_customer["id"], 2000)
        assert result["allowed"] is False
        assert result["over_by"] > 0

    def test_nonexistent_customer(self):
        result = db.check_credit_limit(99999)
        assert result["allowed"] is False


# ══════════════════════════════════════════════════════════════════
#  UPDATE / EDIT ENTRIES
# ══════════════════════════════════════════════════════════════════

class TestEntryUpdates:
    def test_update_debt_entry(self, customer_with_debt):
        cid = customer_with_debt["id"]
        ledger = db.get_customer_ledger(cid, include_voided=True)
        lid = ledger[0]["id"]
        new_items = [{"product_name": "Updated", "price": 50.0, "quantity": 1}]
        db.update_debt_entry(lid, new_items, notes="updated")
        items = db.get_ledger_items(lid)
        assert items[0]["product_name"] == "Updated"
        assert items[0]["price"] == 50.0

    def test_update_payment_entry(self, customer_with_debt):
        cid = customer_with_debt["id"]
        db.add_payment(cid, 10.0)
        ledger = db.get_customer_ledger(cid, include_voided=True)
        payment = next(e for e in ledger if e["entry_type"] == "PAYMENT")
        db.update_payment_entry(payment["id"], 15.0, notes="corrected")
        updated_ledger = db.get_customer_ledger(cid, include_voided=True)
        updated_payment = next(e for e in updated_ledger if e["entry_type"] == "PAYMENT")
        assert updated_payment["amount"] == 15.0


# ══════════════════════════════════════════════════════════════════
#  BACKWARD COMPAT ALIASES
# ══════════════════════════════════════════════════════════════════

class TestBackwardCompat:
    def test_get_customer_total_debt_alias(self, customer_with_debt):
        cid = customer_with_debt["id"]
        assert db.get_customer_total_debt(cid) == db.get_customer_balance(cid)

    def test_delete_customer_alias(self, sample_customer):
        cid = sample_customer["id"]
        db.delete_customer(cid)
        assert all(c["id"] != cid for c in db.get_all_customers())

    def test_add_transaction_alias(self, sample_customer):
        cid = sample_customer["id"]
        lid = db.add_transaction(cid, [{"product_name": "X", "price": 5, "quantity": 1}])
        assert lid is not None
