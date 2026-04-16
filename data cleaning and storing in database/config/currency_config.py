"""
Конфигурация валют и курсов для конвертации цен.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Базовая валюта, в которой хранятся цены в БД (если не указано иное)
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "USD")

# Курсы валют относительно базовой (USD)
EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": float(os.getenv("RATE_EUR", "0.92")),   # 1 EUR = 0.92 USD
    "INR": float(os.getenv("RATE_INR", "0.012")),  # 1 INR = 0.012 USD
    "GBP": float(os.getenv("RATE_GBP", "1.26")),   # 1 GBP = 1.26 USD
    "RUB": float(os.getenv("RATE_RUB", "0.011")),  # 1 RUB ≈ 0.011 USD
}

# Символы валют, которые могут встретиться в тексте
CURRENCY_SYMBOLS = {
    "€": "EUR",
    "$": "USD",
    "£": "GBP",
    "₹": "INR",
    "₽": "RUB",
    "EUR": "EUR",
    "USD": "USD",
    "INR": "INR",
    "GBP": "GBP",
    "RUB": "RUB",
}


def get_currency_from_text(text: str) -> str:
    """Определяет валюту по символу или коду в тексте."""
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    return BASE_CURRENCY


def convert_to_base(amount: float, from_currency: str) -> float:
    """Конвертирует сумму в базовую валюту (USD)."""
    rate = EXCHANGE_RATES.get(from_currency)
    if rate is None:
        rate = 1.0  # fallback
    return amount * rate


def convert_from_base(amount: float, to_currency: str) -> float:
    """Конвертирует сумму из базовой валюты в целевую."""
    rate = EXCHANGE_RATES.get(to_currency)
    if rate is None or rate == 0:
        rate = 1.0
    return amount / rate