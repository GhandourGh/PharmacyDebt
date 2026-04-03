"""
Safe backend action executor.

Maps chatbot intents to database operations.
Undo support via void_entry() on the last ledger_id.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List

import database as db
from chatbot import ollama_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ActionResult:
    success: bool
    response: str                          # Human-readable message
    data: dict = field(default_factory=dict)
    ledger_id: Optional[int] = None        # Set after write actions (for undo)
    undo_available: bool = False
    needs: Optional[str] = None            # Follow-up needed from user
    candidates: List[dict] = field(default_factory=list)
    action_preview: Optional[dict] = None  # For UI confirm cards

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'response': self.response,
            'data': self.data,
            'ledger_id': self.ledger_id,
            'undo_available': self.undo_available,
            'needs': self.needs,
            'candidates': self.candidates,
            'action_preview': self.action_preview,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(n: float) -> str:
    return f"${n:,.2f}"


def _amount_to_items(amount: float, description: str = "Via chatbot") -> list:
    """
    Convert a single chatbot amount into the items list format db.add_debt() expects.
    db.add_debt() requires: [{"product_name": str, "price": float, "quantity": int}]
    """
    return [{"product_name": description, "price": float(amount), "quantity": 1}]


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def check_balance(customer: dict, context: list = None,
                   language_hint: str = 'en',
                   use_rephrase: bool = True) -> ActionResult:
    """Return customer balance."""
    try:
        balance = db.get_customer_balance(customer['id'])
        name = customer['name']
        if balance > 0:
            fallback = f"**{name}** owes **{_fmt(balance)}**."
        elif balance < 0:
            fallback = f"**{name}** has a credit of **{_fmt(abs(balance))}**."
        else:
            fallback = f"**{name}** has no outstanding balance."

        data = {'balance': balance, 'customer': customer}
        if use_rephrase:
            rephrased = ollama_client.rephrase_action_response(
                'check_balance', {'name': name, 'balance': balance},
                context=context, language_hint=language_hint,
            )
            response = rephrased or fallback
        else:
            response = fallback
        return ActionResult(success=True, response=response, data=data)
    except Exception as e:
        logger.error("check_balance error: %s", e)
        return ActionResult(success=False, response="Could not retrieve balance. Please try again.")


def execute_add_payment(customer: dict, amount: float,
                         payment_method: str = 'CASH',
                         user_id: Optional[int] = None,
                         context: list = None,
                         language_hint: str = 'en',
                         use_rephrase: bool = True) -> ActionResult:
    """Record a payment in the database."""
    try:
        balance = db.get_customer_balance(customer['id'])
        if balance <= 0:
            return ActionResult(success=False,
                                response=f"**{customer['name']}** has no outstanding balance to pay.")
        if amount > balance:
            return ActionResult(
                success=False,
                response=f"Payment amount {_fmt(amount)} exceeds balance {_fmt(balance)}. "
                         f"Maximum payment is {_fmt(balance)}.",
            )

        ledger_id = db.add_payment(
            customer_id=customer['id'],
            amount=amount,
            payment_method=payment_method or 'CASH',
            notes="Via chatbot",
            user_id=user_id,
        )
        new_balance = db.get_customer_balance(customer['id'])
        fallback = (
            f"Payment of **{_fmt(amount)}** recorded for **{customer['name']}**. "
            f"New balance: **{_fmt(new_balance)}**."
        )
        data = {'balance': new_balance, 'customer': customer, 'amount': amount}
        if use_rephrase:
            rephrased = ollama_client.rephrase_action_response(
                'add_payment',
                {'name': customer['name'], 'amount': amount, 'new_balance': new_balance},
                context=context, language_hint=language_hint,
            )
            response = rephrased or fallback
        else:
            response = fallback
        return ActionResult(
            success=True,
            response=response,
            data=data,
            ledger_id=ledger_id,
            undo_available=True,
        )
    except Exception as e:
        logger.error("add_payment error: %s", e)
        return ActionResult(success=False, response=f"Payment failed: {e}")


def execute_add_debt(customer: dict, amount: float,
                      description: str = "Via chatbot",
                      user_id: Optional[int] = None,
                      context: list = None,
                      language_hint: str = 'en',
                      use_rephrase: bool = True) -> ActionResult:
    """Record a new debt in the database."""
    try:
        items = _amount_to_items(amount, description)
        ledger_id = db.add_debt(
            customer_id=customer['id'],
            items=items,
            description=description,
            notes="Via chatbot",
            user_id=user_id,
        )
        new_balance = db.get_customer_balance(customer['id'])
        fallback = (
            f"Debt of **{_fmt(amount)}** added for **{customer['name']}**. "
            f"Total balance: **{_fmt(new_balance)}**."
        )
        data = {'balance': new_balance, 'customer': customer, 'amount': amount}
        if use_rephrase:
            rephrased = ollama_client.rephrase_action_response(
                'add_debt',
                {'name': customer['name'], 'amount': amount, 'new_balance': new_balance},
                context=context, language_hint=language_hint,
            )
            response = rephrased or fallback
        else:
            response = fallback
        return ActionResult(
            success=True,
            response=response,
            data=data,
            ledger_id=ledger_id,
            undo_available=True,
        )
    except Exception as e:
        logger.error("add_debt error: %s", e)
        return ActionResult(success=False, response=f"Could not add debt: {e}")


def list_debtors(context: list = None,
                  language_hint: str = 'en',
                  use_rephrase: bool = True,
                  top_n: Optional[int] = None,
                  max_cap: int = 500) -> ActionResult:
    """
    List debtors sorted by balance (highest first).
    top_n: if set, show exactly this many (e.g. user said 'top 10').
    If None, show up to max_cap rows (still sorted by debt).
    """
    try:
        max_cap = max(1, min(int(max_cap), 2000))
        rows = db.get_customers_with_debt() or []
        owing = []
        for c in rows:
            try:
                bal = float(c.get('debt') or 0)
            except (TypeError, ValueError):
                bal = 0.0
            if bal > 0.005:
                c = dict(c)
                c['debt'] = bal
                owing.append(c)
        owing.sort(key=lambda x: float(x.get('debt') or 0), reverse=True)

        if not owing:
            return ActionResult(success=True, response="No customers have outstanding debt. Great news!")

        total_all = sum(float(c.get('debt') or 0) for c in owing)

        if top_n is not None:
            n = max(1, min(int(top_n), max_cap))
            shown = owing[:n]
            omitted = max(0, len(owing) - n)
            head = (
                f"Top **{len(shown)}** debtors by balance (of **{len(owing)}** owing **{_fmt(total_all)}** total):\n\n"
            )
        else:
            n_show = min(len(owing), max_cap)
            shown = owing[:n_show]
            omitted = len(owing) - n_show
            head = (
                f"**{len(owing)} customers** owe **{_fmt(total_all)}** total — "
                f"largest balances first (showing **{len(shown)}**):\n\n"
            )

        lines = [f"**{c['name']}** — {_fmt(float(c.get('debt') or 0))}" for c in shown]
        fallback = head + "\n".join(lines)
        if omitted > 0:
            fallback += (
                f"\n\n…**{omitted}** more debtor(s) not shown — say e.g. **top {min(omitted + len(shown), max_cap)} debtors** "
                f"to see more."
            )

        data = {
            'customers': owing,
            'customers_shown': shown,
            'owing_count': len(owing),
            'total_debt_all': total_all,
            'total': total_all,
        }
        if use_rephrase:
            rephrased = ollama_client.rephrase_action_response(
                'list_debtors',
                {'count': len(owing), 'total': total_all,
                 'top_debtors': [
                     {'name': c['name'], 'debt': c.get('debt', 0)} for c in shown[:5]
                 ]},
                context=context, language_hint=language_hint,
            )
            response = rephrased or fallback
            if rephrased and len(shown) > 0:
                response = rephrased + "\n\n" + "\n".join(lines)
                if omitted > 0:
                    response += (
                        f"\n\n…**{omitted}** more debtor(s) not listed — try **top {min(len(owing), max_cap)} debtors**."
                    )
        else:
            response = fallback
        return ActionResult(
            success=True,
            response=response,
            data=data,
        )
    except Exception as e:
        logger.error("list_debtors error: %s", e)
        return ActionResult(success=False, response="Could not retrieve debtor list.")


def execute_add_customer(name: str, phone: str = None,
                          user_id: Optional[int] = None) -> ActionResult:
    """Add a new customer to the database."""
    try:
        customer_id = db.add_customer(name=name, phone=phone)
        response = f"Customer **{name}** has been added successfully."
        return ActionResult(
            success=True,
            response=response,
            data={'customer_id': customer_id, 'name': name},
        )
    except Exception as e:
        logger.error("add_customer error: %s", e)
        return ActionResult(success=False, response=f"Could not add customer: {e}")


def undo_last_action(session_ctx: dict, user_id: Optional[int] = None) -> ActionResult:
    """Void the last written ledger entry (undo)."""
    ledger_id = session_ctx.get('last_ledger_id')
    last_action = session_ctx.get('last_action', 'action')
    customer_name = session_ctx.get('last_customer_name', '')
    amount = session_ctx.get('last_amount', 0)

    if not ledger_id:
        return ActionResult(success=False, response="Nothing to undo.")

    try:
        db.void_entry(ledger_id, reason="Undone via chatbot", user_id=user_id)
        # Clear undo state
        session_ctx['last_ledger_id'] = None
        session_ctx['last_action'] = None

        desc = f"{last_action}"
        if customer_name:
            desc += f" for **{customer_name}**"
        if amount:
            desc += f" ({_fmt(amount)})"

        return ActionResult(
            success=True,
            response=f"Undone: {desc} has been reversed.",
            undo_available=False,
        )
    except Exception as e:
        logger.error("undo error (ledger_id=%s): %s", ledger_id, e)
        return ActionResult(success=False, response=f"Could not undo: {e}")


# ---------------------------------------------------------------------------
# Confirmation card builder
# ---------------------------------------------------------------------------

def build_action_preview(intent: str, customer: dict, amount: Optional[float],
                          payment_method: str = None) -> dict:
    """Build the action_preview dict used by the UI to render a confirm card."""
    balance = None
    try:
        if customer:
            balance = db.get_customer_balance(customer['id'])
    except Exception:
        pass

    labels = {
        'add_payment': 'Record Payment',
        'add_debt': 'Add Debt',
        'add_customer': 'Add New Customer',
    }

    return {
        'action_type': intent,
        'action_label': labels.get(intent, intent.replace('_', ' ').title()),
        'customer_name': customer.get('name') if customer else None,
        'customer_id': customer.get('id') if customer else None,
        'current_balance': balance,
        'amount': amount,
        'payment_method': payment_method,
        'new_balance_preview': (balance - amount) if (balance is not None and amount and intent == 'add_payment') else
                               (balance + amount) if (balance is not None and amount and intent == 'add_debt') else None,
    }
