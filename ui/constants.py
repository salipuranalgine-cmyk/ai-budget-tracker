from datetime import datetime

CURRENCY = "PHP"

# ---------------------------------------------------------------------------
# Expense categories — covers students, employees, freelancers, families, etc.
# ---------------------------------------------------------------------------
DEFAULT_CATEGORIES = [
    # Daily needs
    "Food & Groceries",
    "Eating Out / Lutong Labas",
    # Transport
    "Transport (Jeep/Bus)",
    "Grab / Taxi",
    # Communication
    "Load / Mobile Data",
    "Internet / WiFi",
    # Housing & Utilities
    "Rent / Boarding House",
    "Electricity (Meralco)",
    "Water Bill",
    "LPG / Gas",
    # Health
    "Health / Medicine",
    "Hospital / Clinic",
    # Education
    "School / Tuition",
    "School Supplies",
    # Personal
    "Personal Care / Hygiene",
    "Clothing / Shopping",
    # Family & Social
    "Family Support / Pasalubong",
    "Church / Donation",
    # Debt & Finance
    "Debt / Loan Payment",
    "Credit Card Payment",
    "Savings / Emergency Fund",
    # Lifestyle
    "Entertainment / Leisure",
    "Subscriptions (Netflix, etc.)",
    # Business
    "Business Expense",
    # Catch-all
    "Others",
]

# ---------------------------------------------------------------------------
# Income categories — covers employed, self-employed, OFW, student, etc.
# ---------------------------------------------------------------------------
INCOME_CATEGORIES = [
    # Employment
    "Salary / Sweldo",
    "Overtime / Bonus",
    "Commission",
    # Self-employment
    "Freelance / Sideline",
    "Online Selling / Negosyo",
    "Professional Fee",
    # Business
    "Business Revenue",
    # Government / Benefits
    "Pension / SSS / GSIS",
    "PhilHealth Refund",
    "Government Aid (4Ps / Ayuda)",
    # Family support
    "Allowance (from parents)",
    "OFW Remittance / Padala",
    # Passive income
    "Rental Income",
    "Investment / Dividends",
    "Bank / GCash Interest",
    # Windfall
    "Gift / Padala",
    "Scholarship / Grant",
    # Catch-all
    "Others",
]

# Emoji options for user profile avatars
AVATAR_EMOJIS = ["🧑", "👦", "👧", "👨", "👩", "👴", "👵", "🧒", "🧔", "👱"]


def now_month() -> str:
    return datetime.now().strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Multi-currency support
# ---------------------------------------------------------------------------
# Each entry: currency_code -> (symbol, decimal_places)
CURRENCIES: dict[str, tuple[str, int]] = {
    "PHP": ("₱",   2),
    "USD": ("$",   2),
    "EUR": ("€",   2),
    "GBP": ("£",   2),
    "SGD": ("S$",  2),
    "AUD": ("A$",  2),
    "CAD": ("C$",  2),
    "HKD": ("HK$", 2),
    "MYR": ("RM",  2),
    "THB": ("฿",   2),
    "VND": ("₫",   0),
    "IDR": ("Rp",  0),
    "JPY": ("¥",   0),
    "KRW": ("₩",   0),
    "CNY": ("¥",   2),
    "AED": ("AED", 2),
    "SAR": ("SAR", 2),
}

CURRENCY_LABELS: dict[str, str] = {
    "PHP": "PHP — Philippine Peso (₱)",
    "USD": "USD — US Dollar ($)",
    "EUR": "EUR — Euro (€)",
    "GBP": "GBP — British Pound (£)",
    "SGD": "SGD — Singapore Dollar (S$)",
    "AUD": "AUD — Australian Dollar (A$)",
    "CAD": "CAD — Canadian Dollar (C$)",
    "HKD": "HKD — Hong Kong Dollar (HK$)",
    "MYR": "MYR — Malaysian Ringgit (RM)",
    "THB": "THB — Thai Baht (฿)",
    "VND": "VND — Vietnamese Dong (₫)",
    "IDR": "IDR — Indonesian Rupiah (Rp)",
    "JPY": "JPY — Japanese Yen (¥)",
    "KRW": "KRW — South Korean Won (₩)",
    "CNY": "CNY — Chinese Yuan (¥)",
    "AED": "AED — UAE Dirham",
    "SAR": "SAR — Saudi Riyal",
}


def format_currency(amount: float, code: str = "PHP") -> str:
    """Format amount with the correct symbol and decimal places for the given currency code."""
    symbol, decimals = CURRENCIES.get(code, ("₱", 2))
    return f"{symbol}{amount:,.{decimals}f}"


def make_peso(code: str = "PHP"):
    """
    Return a formatting function that works exactly like peso() but for any currency.
    Use this at the top of screen/dialog functions to shadow the imported peso:
        peso = make_peso(db.get_currency())
    """
    symbol, decimals = CURRENCIES.get(code, ("₱", 2))
    def _fmt(amount: float) -> str:
        return f"{symbol}{amount:,.{decimals}f}"
    return _fmt


def peso(amount: float) -> str:
    """Legacy helper — prefer make_peso(db.get_currency()) in screen functions."""
    return f"₱{amount:,.2f}"