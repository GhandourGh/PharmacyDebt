"""
AI Chatbot module for Pharmacy Debt System.
Uses Ollama (local LLM) to convert natural language into structured JSON actions.
"""

import json
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

# All valid actions the chatbot can produce
VALID_ACTIONS = {
    # Debt & Payment
    "add_debt", "pay_debt", "get_debt", "add_credit",
    # Customer
    "list_customers", "customer_detail", "add_customer", "remove_customer", "top_debtors",
    # Products
    "list_products", "product_detail", "add_product",
    # Donations
    "donation_balance", "add_donation", "use_donation",
    # Reports & Stats
    "total_debt", "daily_summary", "overdue_customers", "over_limit_customers",
    "recent_activity", "aging_report", "weekly_stats", "customer_history",
    "date_lookup", "today_debts", "today_payments", "today_customers",
    # Help
    "help",
    # Fallback
    "unknown",
}

# Actions that require a "name" field (customer name)
ACTIONS_NEED_NAME = {"add_debt", "pay_debt", "get_debt", "customer_detail", "add_customer", "customer_history", "add_credit", "use_donation", "remove_customer"}

# Actions that require an "amount" field
ACTIONS_NEED_AMOUNT = {"add_debt", "pay_debt", "add_donation", "add_credit", "use_donation"}

SYSTEM_PROMPT = """You are a pharmacy debt management assistant. Your ONLY job is to convert user messages into a single JSON object. Output ONLY valid JSON, nothing else — no explanation, no markdown, no extra text.

Allowed actions:

--- DEBT & PAYMENTS ---
1. add_debt — someone owes money / bought on credit
   {"action": "add_debt", "name": "<name>", "amount": <number>, "product": "<product name or empty>"}
2. pay_debt — someone paid money
   {"action": "pay_debt", "name": "<name>", "amount": <number>}
3. get_debt — ask how much someone owes
   {"action": "get_debt", "name": "<name>"}
4. add_credit — a third party pays on behalf of a customer
   {"action": "add_credit", "name": "<customer name>", "amount": <number>, "payer": "<who is paying>"}

--- CUSTOMERS ---
4. list_customers — list all customers
   {"action": "list_customers"}
5. customer_detail — show full info about a customer
   {"action": "customer_detail", "name": "<name>"}
6. add_customer — add a new customer (optionally with phone)
   {"action": "add_customer", "name": "<name>", "phone": "<phone or empty>"}
7. remove_customer — remove/delete a customer
   {"action": "remove_customer", "name": "<name>"}
8. top_debtors — who owes the most
   {"action": "top_debtors"}
8. customer_history — show transaction history for a customer
   {"action": "customer_history", "name": "<name>"}

--- PRODUCTS ---
9. list_products — list all products
   {"action": "list_products"}
10. product_detail — look up a product by name
    {"action": "product_detail", "name": "<product name>"}
11. add_product — add a new product with price
    {"action": "add_product", "name": "<product name>", "amount": <price>}

--- DONATIONS ---
12. donation_balance — how much donation money is available
    {"action": "donation_balance"}
13. add_donation — record a new donation
    {"action": "add_donation", "amount": <number>, "donor": "<donor name or empty>"}
14. use_donation — apply donation money to pay a customer's debt
    {"action": "use_donation", "name": "<customer name>", "amount": <number>}

--- REPORTS & STATS ---
14. total_debt — total debt across all customers
    {"action": "total_debt"}
15. daily_summary — today's summary (debts added, payments received)
    {"action": "daily_summary"}
16. overdue_customers — customers with overdue debt (30+ days)
    {"action": "overdue_customers"}
17. over_limit_customers — customers who exceeded their credit limit
    {"action": "over_limit_customers"}
18. recent_activity — show recent transactions system-wide
    {"action": "recent_activity"}
19. aging_report — debt aging breakdown
    {"action": "aging_report"}
20. weekly_stats — weekly debt vs payments summary
    {"action": "weekly_stats"}
21. date_lookup — what happened on a specific date
    {"action": "date_lookup", "date": "<YYYY-MM-DD>"}
22. today_debts — who took on debt today / who owes from today
    {"action": "today_debts"}
23. today_payments — who paid today
    {"action": "today_payments"}
24. today_customers — who was added as a customer today
    {"action": "today_customers"}

--- HELP ---
21. help — user asks what you can do, or says hello/hi
    {"action": "help"}

--- FALLBACK ---
22. unknown — message is unclear or unrelated to the system
    {"action": "unknown"}

Rules:
- Extract names exactly as mentioned.
- Extract amounts as positive numbers (no currency symbols).
- "owes", "bought", "purchased", "on credit" → add_debt. If a product name is mentioned, include it in "product". If no product mentioned, leave "product" empty.
- "paid", "returned", "payment" → pay_debt
- "how much", "balance", "check" about a person → get_debt
- "all customers", "list customers", "show customers" → list_customers
- "details", "info about", "show me [name]" → customer_detail
- "history", "transactions for", "ledger for" → customer_history
- "remove", "delete", "remove customer" → remove_customer
- "who owes the most", "top debtors", "biggest debts" → top_debtors
- "all products", "list products", "show products" → list_products
- "price of", "how much is [product]" → product_detail
- "add product" → add_product
- "total debt", "total owed", "how much is owed" → total_debt
- "today", "daily summary", "today's report" → daily_summary
- "who owes today", "who took debt today", "debts today", "today's debts" → today_debts
- "who paid today", "payments today", "today's payments" → today_payments
- "who was added today", "new customers today", "customers added today" → today_customers
- "overdue", "late payments" → overdue_customers
- "over limit", "exceeded limit" → over_limit_customers
- "recent", "latest activity", "what happened" → recent_activity
- "aging", "aging report" → aging_report
- "weekly", "this week", "week summary" → weekly_stats
- "donations", "donation balance", "available donations" → donation_balance
- "add donation", "new donation", "donate" → add_donation
- "credit from", "his uncle paid", "someone paid for", "third party" → add_credit
- "use donation for", "apply donation to", "help [name] with donation" → use_donation
- "what happened on", "show me [date]", "transactions on [date]" → date_lookup (date MUST be YYYY-MM-DD format)
- For date_lookup, convert any date to YYYY-MM-DD. "March 15" in 2026 → "2026-03-15", "yesterday" → calculate the date.
- "help", "what can you do", "hello", "hi" → help
- If unclear → unknown
- NEVER output anything except a single JSON object.

Examples:
User: Ahmad owes 20 dollars
{"action": "add_debt", "name": "Ahmad", "amount": 20, "product": ""}

User: add 50 panadol for Alex
{"action": "add_debt", "name": "Alex", "amount": 50, "product": "panadol"}

User: Sara bought Aspirin for 15.5
{"action": "add_debt", "name": "Sara", "amount": 15.5, "product": "Aspirin"}

User: Ahmad paid 10
{"action": "pay_debt", "name": "Ahmad", "amount": 10}

User: How much does Ahmad owe?
{"action": "get_debt", "name": "Ahmad"}

User: أحمد عليه 50
{"action": "add_debt", "name": "أحمد", "amount": 50, "product": ""}

User: أحمد دفع 30
{"action": "pay_debt", "name": "أحمد", "amount": 30}

User: كم عليه أحمد؟
{"action": "get_debt", "name": "أحمد"}

User: show all customers
{"action": "list_customers"}

User: who owes the most?
{"action": "top_debtors"}

User: show me details about Sara
{"action": "customer_detail", "name": "Sara"}

User: add a new customer named Omar
{"action": "add_customer", "name": "Omar", "phone": ""}

User: show Ahmad's history
{"action": "customer_history", "name": "Ahmad"}

User: remove customer Sara
{"action": "remove_customer", "name": "Sara"}

User: delete Omar
{"action": "remove_customer", "name": "Omar"}

User: list all products
{"action": "list_products"}

User: what's the price of Panadol?
{"action": "product_detail", "name": "Panadol"}

User: add product Aspirin at 3.5
{"action": "add_product", "name": "Aspirin", "amount": 3.5}

User: what's the total debt?
{"action": "total_debt"}

User: show today's summary
{"action": "daily_summary"}

User: who is overdue?
{"action": "overdue_customers"}

User: who exceeded their credit limit?
{"action": "over_limit_customers"}

User: show recent activity
{"action": "recent_activity"}

User: show aging report
{"action": "aging_report"}

User: weekly stats
{"action": "weekly_stats"}

User: how much donations available?
{"action": "donation_balance"}

User: add a donation of 100 from Khalid
{"action": "add_donation", "amount": 100, "donor": "Khalid"}

User: Ahmad's uncle paid 50 for him
{"action": "add_credit", "name": "Ahmad", "amount": 50, "payer": "his uncle"}

User: add credit 30 for Sara from her father
{"action": "add_credit", "name": "Sara", "amount": 30, "payer": "her father"}

User: use donation for Ahmad 20
{"action": "use_donation", "name": "Ahmad", "amount": 20}

User: apply donation to Sara for 15
{"action": "use_donation", "name": "Sara", "amount": 15}

User: what happened on March 15?
{"action": "date_lookup", "date": "2026-03-15"}

User: show transactions on 2026-03-17
{"action": "date_lookup", "date": "2026-03-17"}

User: what can you do?
{"action": "help"}

User: hello
{"action": "help"}

User: who owes today?
{"action": "today_debts"}

User: who took debt today?
{"action": "today_debts"}

User: who paid today?
{"action": "today_payments"}

User: any payments today?
{"action": "today_payments"}

User: who was added today?
{"action": "today_customers"}

User: new customers today?
{"action": "today_customers"}

User: مين اخذ دين اليوم؟
{"action": "today_debts"}

User: مين دفع اليوم؟
{"action": "today_payments"}

Remember: output ONLY the JSON object, nothing else."""


def query_ollama(user_message):
    """Send user message to Ollama and return the raw response text."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_message,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.1,
        }
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=90)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except requests.ConnectionError:
        return None
    except requests.Timeout:
        return None
    except Exception:
        return None


def extract_json(text):
    """Try to extract a JSON object from LLM output, handling extra text around it."""
    if not text:
        return None

    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    match = re.search(r'\{[^{}]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def validate_action(data):
    """Validate parsed JSON has required fields and correct types."""
    if not isinstance(data, dict):
        return None

    action = data.get("action", "unknown")

    if action not in VALID_ACTIONS:
        return {"action": "unknown"}

    if action in ("unknown", "help", "list_customers", "list_products",
                   "top_debtors", "total_debt", "daily_summary",
                   "overdue_customers", "over_limit_customers",
                   "recent_activity", "aging_report", "weekly_stats",
                   "donation_balance", "today_debts", "today_payments",
                   "today_customers"):
        return {"action": action}

    # Actions that need a name
    if action in ACTIONS_NEED_NAME:
        name = str(data.get("name", "")).strip()
        if not name:
            return {"action": "unknown"}
        result = {"action": action, "name": name}

        # add_customer may have phone
        if action == "add_customer":
            result["phone"] = str(data.get("phone", "")).strip()
            return result

        # Actions that also need amount
        if action in ACTIONS_NEED_AMOUNT:
            try:
                amount = float(data.get("amount", 0))
            except (TypeError, ValueError):
                return {"action": "unknown"}
            if amount <= 0:
                return {"action": "unknown"}
            result["amount"] = round(amount, 2)

        # add_debt has an optional product field
        if action == "add_debt":
            result["product"] = str(data.get("product", "")).strip()

        # add_credit has an optional payer field
        if action == "add_credit":
            result["payer"] = str(data.get("payer", "")).strip()

        return result

    # add_product needs name + amount
    if action == "add_product":
        name = str(data.get("name", "")).strip()
        if not name:
            return {"action": "unknown"}
        try:
            amount = float(data.get("amount", 0))
        except (TypeError, ValueError):
            return {"action": "unknown"}
        if amount <= 0:
            return {"action": "unknown"}
        return {"action": "add_product", "name": name, "amount": round(amount, 2)}

    # product_detail needs name
    if action == "product_detail":
        name = str(data.get("name", "")).strip()
        if not name:
            return {"action": "unknown"}
        return {"action": "product_detail", "name": name}

    # add_donation needs amount, optionally donor
    if action == "add_donation":
        try:
            amount = float(data.get("amount", 0))
        except (TypeError, ValueError):
            return {"action": "unknown"}
        if amount <= 0:
            return {"action": "unknown"}
        donor = str(data.get("donor", "")).strip()
        return {"action": "add_donation", "amount": round(amount, 2), "donor": donor}

    # date_lookup needs a date in YYYY-MM-DD format
    if action == "date_lookup":
        date = str(data.get("date", "")).strip()
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
            return {"action": "unknown"}
        return {"action": "date_lookup", "date": date}

    return {"action": "unknown"}


def process_message(user_message):
    """
    Main entry point. Takes a user message, queries Ollama, and returns
    a validated action dict or an error dict.
    """
    if not user_message or not user_message.strip():
        return {"action": "unknown", "error": "Empty message"}

    raw = query_ollama(user_message)

    if raw is None:
        return {
            "action": "error",
            "error": "Cannot connect to Ollama. Make sure Ollama is running (ollama serve) and the llama3 model is pulled (ollama pull llama3)."
        }

    parsed = extract_json(raw)

    if parsed is None:
        return {"action": "unknown", "error": "Could not understand the request. Please try again."}

    validated = validate_action(parsed)
    return validated
