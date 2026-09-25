"""Tests for outstanding statement print builder."""

import pytest

import database as db
from statement_print import build_outstanding_statement


def _add_debt(cid, amount, name="Item"):
    return db.add_debt(
        cid,
        [{"product_name": name, "price": amount, "quantity": 1}],
    )


class TestOutstandingStatementBuilder:
    def test_example_sequence_running_balance(self, sample_customer):
        """Debt 200, pay 200, debt 100, pay 50 → balance 50 with clear running totals."""
        cid = sample_customer["id"]
        _add_debt(cid, 200.0, "Previous purchase")
        db.add_payment(cid, 200.0)
        _add_debt(cid, 100.0, "a")
        db.add_payment(cid, 50.0)

        ledger = db.get_customer_ledger(cid, include_voided=False)
        stmt = build_outstanding_statement(ledger)
        app_balance = db.get_customer_balance(cid)

        assert stmt["total_charges"] == pytest.approx(300.0)
        assert stmt["total_payments"] == pytest.approx(250.0)
        assert stmt["balance_due"] == pytest.approx(50.0)
        assert stmt["balance_due"] == pytest.approx(app_balance)

        balances = [row["balance"] for row in stmt["activity"]]
        assert balances == pytest.approx([200.0, 0.0, 100.0, 50.0])

        assert [row["activity"] for row in stmt["activity"]] == [
            "Charge",
            "Payment",
            "Charge",
            "Payment",
        ]
        assert stmt["activity"][0]["charge"] == pytest.approx(200.0)
        assert stmt["activity"][0]["payment"] is None
        assert stmt["activity"][1]["payment"] == pytest.approx(200.0)
        assert stmt["activity"][1]["charge"] is None

    def test_debt_with_no_payments(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 75.0, "Solo")
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["total_charges"] == pytest.approx(75.0)
        assert stmt["total_payments"] == pytest.approx(0.0)
        assert stmt["balance_due"] == pytest.approx(75.0)
        assert len(stmt["activity"]) == 1
        assert stmt["activity"][0]["balance"] == pytest.approx(75.0)

    def test_partial_payment(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 100.0)
        db.add_payment(cid, 40.0)
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["balance_due"] == pytest.approx(60.0)
        assert stmt["balance_due"] == pytest.approx(db.get_customer_balance(cid))
        assert [r["balance"] for r in stmt["activity"]] == pytest.approx([100.0, 60.0])

    def test_fully_paid_then_new_debt(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 80.0, "Old")
        db.add_payment(cid, 80.0)
        _add_debt(cid, 25.0, "New")
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["total_charges"] == pytest.approx(105.0)
        assert stmt["total_payments"] == pytest.approx(80.0)
        assert stmt["balance_due"] == pytest.approx(25.0)
        assert [r["balance"] for r in stmt["activity"]] == pytest.approx([80.0, 0.0, 25.0])

    def test_multiple_debts_before_payment(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 30.0, "A")
        _add_debt(cid, 20.0, "B")
        db.add_payment(cid, 40.0)
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["balance_due"] == pytest.approx(10.0)
        assert [r["balance"] for r in stmt["activity"]] == pytest.approx([30.0, 50.0, 10.0])

    def test_multiple_partial_payments(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 100.0)
        db.add_payment(cid, 25.0)
        db.add_payment(cid, 25.0)
        db.add_payment(cid, 10.0)
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["total_payments"] == pytest.approx(60.0)
        assert stmt["balance_due"] == pytest.approx(40.0)
        assert [r["balance"] for r in stmt["activity"]] == pytest.approx(
            [100.0, 75.0, 50.0, 40.0]
        )

    def test_zero_outstanding_balance(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 50.0)
        db.add_payment(cid, 50.0)
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["balance_due"] == pytest.approx(0.0)
        assert stmt["balance_due"] == pytest.approx(db.get_customer_balance(cid))
        assert stmt["activity"][-1]["balance"] == pytest.approx(0.0)

    def test_excludes_voided_and_reconciles(self, sample_customer):
        cid = sample_customer["id"]
        lid = _add_debt(cid, 90.0, "Keep")
        void_id = _add_debt(cid, 15.0, "VoidMe")
        db.void_entry(void_id, "mistake")
        db.add_payment(cid, 40.0)

        ledger_with_voided = db.get_customer_ledger(cid, include_voided=True)
        stmt = build_outstanding_statement(ledger_with_voided)
        assert all(r["details"] != "VoidMe" for r in stmt["activity"])
        assert stmt["balance_due"] == pytest.approx(db.get_customer_balance(cid))
        assert stmt["total_charges"] == pytest.approx(90.0)

    def test_oldest_first_order(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 10.0, "First")
        _add_debt(cid, 20.0, "Second")
        db.add_payment(cid, 5.0)
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["activity"][0]["details"] == "First"
        assert stmt["activity"][1]["details"] == "Second"
        assert stmt["activity"][2]["activity"] == "Payment"

    def test_mark_paid_note_preserved(self, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 12.0)
        db.add_payment(
            cid, 12.0, notes="Marked as paid (auto full payment)"
        )
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert stmt["activity"][-1]["details"] == "Marked as paid (auto full payment)"

    def test_long_history_balance_matches_app(self, sample_customer):
        cid = sample_customer["id"]
        for i in range(40):
            _add_debt(cid, 10.0, f"Item{i}")
            if i % 3 == 2:
                db.add_payment(cid, 15.0)
        stmt = build_outstanding_statement(db.get_customer_ledger(cid))
        assert len(stmt["activity"]) > 40
        assert stmt["balance_due"] == pytest.approx(db.get_customer_balance(cid), abs=0.01)


class TestOutstandingStatementRoute:
    def test_customer_detail_includes_account_activity(self, client, sample_customer):
        cid = sample_customer["id"]
        _add_debt(cid, 200.0, "Previous purchase")
        db.add_payment(cid, 200.0)
        _add_debt(cid, 100.0, "a")
        db.add_payment(cid, 50.0)

        resp = client.get(f"/customers/{cid}")
        assert resp.status_code == 200
        assert b"Account Activity" in resp.data
        assert b"CURRENT BALANCE DUE" in resp.data
        assert b"Total Charges" in resp.data
        assert b"Payments Received" in resp.data
        assert b"$300.00" in resp.data
        assert b"$250.00" in resp.data
        assert b"Outstanding Items" not in resp.data or b"print-receipt-unpaid" in resp.data
        # Unpaid print block should not use the old split section titles
        unpaid_html = resp.data.split(b"print-receipt-unpaid")[1].split(b"print-receipt-full")[0]
        assert b"Outstanding Items" not in unpaid_html
        assert b"Payment History" not in unpaid_html
        assert b"Account Activity" in unpaid_html
        assert b"Outstanding Statement" in unpaid_html
        assert b"Payments shown above have already been deducted" in unpaid_html

        full_html = resp.data.split(b"print-receipt-full")[1].split(b"page-header")[0]
        assert b"Account Statement" in full_html
        assert b"Account Activity" in full_html
        assert b"All Items" not in full_html
        assert b"Payment History" not in full_html
        assert b"CURRENT BALANCE DUE" in full_html
        assert b"$50.00" in full_html
