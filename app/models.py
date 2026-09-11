from typing import Optional

from pydantic import BaseModel


# ============================================================
# BASE TOOL RESPONSE
# ============================================================

class ToolResponse(BaseModel):

    success: bool
    message: str


# ============================================================
# STOCK
# ============================================================

class StockQuote(ToolResponse):

    ticker: str
    company: Optional[str] = None
    price_usd: Optional[float] = None
    change_percent: Optional[float] = None


# ============================================================
# CRYPTO
# ============================================================

class CryptoPrice(ToolResponse):

    coin: str
    price_usd: Optional[float] = None
    resolved_coin_id: Optional[str] = None
    resolved_symbol: Optional[str] = None
    resolved_name: Optional[str] = None


# ============================================================
# FOREX
# ============================================================

class ForexRate(ToolResponse):

    amount: float
    from_currency: str
    to_currency: str
    converted_amount: Optional[float] = None


# ============================================================
# CALCULATION
# ============================================================

class CalculationResult(ToolResponse):

    expression: str
    result: Optional[float] = None


# ============================================================
# NEWS
# ============================================================

class NewsResult(ToolResponse):

    title: str
    summary: str
    source: Optional[str] = None


# ============================================================
# DATE / TIME
# ============================================================

class DateTimeResponse(ToolResponse):

    date: str
    day: str
    time: str


# ============================================================
# CHAT MESSAGE
# ============================================================

class ChatMessage(BaseModel):

    role: str
    content: str