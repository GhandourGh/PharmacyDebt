"""Build print-ready outstanding statement rows from ledger data.

Uses the same entry types and sign rules as database.get_customer_balance:
- NEW_DEBT / ADJUSTMENT increase what is owed
- PAYMENT / WRITE_OFF / REFUND decrease what is owed
Voided and deleted entries are excluded so the running balance reconciles
with the application's outstanding balance.
"""

from __future__ import annotations

from typing import Any


CHARGE_TYPES = frozenset({"NEW_DEBT", "ADJUSTMENT"})
PAYMENT_TYPES = frozenset({"PAYMENT", "WRITE_OFF", "REFUND"})

ACTIVITY_LABELS = {
    "NEW_DEBT": "Charge",
    "PAYMENT": "Payment",
    "ADJUSTMENT": "Adjustment",
    "WRITE_OFF": "Write-off",
    "REFUND": "Refund",
}


def _format_date(created_at: str | None) -> str:
    if not created_at:
        return "—"
    date_part = created_at[:10]
    try:
        year, month, day = date_part.split("-")
        return f"{month}/{day}/{year}"
    except ValueError:
        return date_part


def _debt_details(entry: dict[str, Any]) -> str:
    items = entry.get("items") or []
    parts: list[str] = []
    for item in items:
        name = (item.get("product_name") or "Item").strip() or "Item"
        qty = int(item.get("quantity") or 1)
        parts.append(f"{name} (x{qty})" if qty > 1 else name)

    details = ", ".join(parts) if parts else ""
    description = (entry.get("description") or "").strip()
    notes = (entry.get("notes") or "").strip()

    if not details:
        details = description or notes or "Purchase"
    elif description and description not in details:
        details = f"{details} — {description}"
    elif notes and notes not in details and not description:
        details = f"{details} — {notes}"

    return details


def _payment_details(entry: dict[str, Any]) -> str:
    notes = (entry.get("notes") or "").strip()
    if notes:
        return notes
    method = (entry.get("payment_method") or "").strip()
    if method and method.upper() == "CREDIT":
        return "Credit applied"
    return "Payment received"


def _entry_sort_key(entry: dict[str, Any]) -> tuple[str, int]:
    return (entry.get("created_at") or "", int(entry.get("id") or 0))


def build_outstanding_statement(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    """Build chronological account activity with a running balance.

    Returns:
        activity: rows oldest-first with charge/payment/balance fields
        total_charges: sum of charge-side amounts
        total_payments: sum of payment-side amounts
        balance_due: final running balance (reconciles with app balance)
    """
    active = [
        e
        for e in ledger
        if not e.get("is_voided")
        and not e.get("is_deleted")
        and e.get("entry_type") in CHARGE_TYPES | PAYMENT_TYPES
    ]
    active.sort(key=_entry_sort_key)

    activity: list[dict[str, Any]] = []
    running = 0.0
    total_charges = 0.0
    total_payments = 0.0

    for entry in active:
        entry_type = entry.get("entry_type")
        amount = round(abs(float(entry.get("amount") or 0)), 2)
        charge: float | None = None
        payment: float | None = None

        if entry_type in CHARGE_TYPES:
            # ADJUSTMENT uses the same balance rule as NEW_DEBT (+amount).
            signed = round(float(entry.get("amount") or 0), 2)
            if signed < 0:
                payment = abs(signed)
                running -= abs(signed)
                total_payments += abs(signed)
            else:
                charge = amount
                running += amount
                total_charges += amount
            details = (
                _debt_details(entry)
                if entry_type == "NEW_DEBT"
                else ((entry.get("notes") or entry.get("description") or "Account adjustment").strip())
            )
        else:
            payment = amount
            running -= amount
            total_payments += amount
            if entry_type == "PAYMENT":
                details = _payment_details(entry)
            elif entry_type == "WRITE_OFF":
                details = (entry.get("notes") or "Write-off").strip() or "Write-off"
            else:
                details = (entry.get("notes") or "Refund").strip() or "Refund"

        running = round(running, 2)
        activity.append(
            {
                "id": entry.get("id"),
                "date": _format_date(entry.get("created_at")),
                "created_at": entry.get("created_at"),
                "activity": ACTIVITY_LABELS.get(entry_type, entry_type or "Entry"),
                "details": details,
                "charge": charge,
                "payment": payment,
                "balance": running,
                "entry_type": entry_type,
            }
        )

    return {
        "activity": activity,
        "total_charges": round(total_charges, 2),
        "total_payments": round(total_payments, 2),
        "balance_due": round(running, 2),
    }
