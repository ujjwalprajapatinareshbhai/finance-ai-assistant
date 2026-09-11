TOOLS = [


# ========================================================
# STOCK PRICE
# ========================================================

{
    "type": "function",
    "function": {
        "name": "get_stock_price",
        "description": (
            "Get the latest/current market price of a "
            "PUBLICLY TRADED COMPANY STOCK or EQUITY. "
            "Use this tool ONLY for company stocks such as "
            "Apple (AAPL), Microsoft (MSFT), Tesla (TSLA), "
            "Amazon (AMZN), Nvidia (NVDA), Google/Alphabet "
            "(GOOGL/GOOG), Meta (META), and similar publicly "
            "traded companies. "
            "DO NOT use this tool for cryptocurrencies. "
            "Bitcoin, BTC, Ethereum, ETH, Solana, XRP, "
            "Dogecoin, and other digital currencies MUST use "
            "get_crypto_price instead. "
            "If the user asks for a stock price without "
            "specifying a historical date or period, interpret "
            "the request as asking for the latest/current "
            "available stock price."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": (
                        "The stock ticker symbol of a publicly "
                        "traded company. Examples: AAPL, MSFT, "
                        "TSLA, AMZN, NVDA."
                    )
                }
            },
            "required": [
                "ticker"
            ]
        }
    }
},

# ========================================================
# CRYPTO PRICE
# ========================================================

{
    "type": "function",
    "function": {
        "name": "get_crypto_price",
        "description": (
            "Get the latest/current market price of a "
            "CRYPTOCURRENCY or DIGITAL ASSET. "
            "Use this tool for Bitcoin (BTC), Ethereum (ETH), "
            "Solana (SOL), XRP, Dogecoin (DOGE), and other "
            "cryptocurrencies. "
            "IMPORTANT: Bitcoin is a cryptocurrency and MUST "
            "use this tool. Do NOT use get_stock_price for "
            "Bitcoin or any other cryptocurrency. "
            "Do NOT use this tool for publicly traded company "
            "stocks such as Apple, Microsoft, Tesla, Amazon, "
            "or Nvidia. "
            "If the user asks for a crypto price without "
            "specifying a historical date or period, interpret "
            "the request as asking for the latest/current "
            "available crypto price."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "coin": {
                    "type": "string",
                    "description": (
                        "The cryptocurrency name or CoinGecko "
                        "coin ID. Examples: bitcoin, ethereum, "
                        "solana, ripple, dogecoin."
                    )
                }
            },
            "required": [
                "coin"
            ]
        }
    }
},

# ========================================================
# CURRENCY CONVERSION
# ========================================================

{
    "type": "function",
    "function": {
        "name": "convert_currency",
        "description": (
            "Convert a specified amount from one currency to "
            "another using the latest/current exchange rate. "
            "If the user does not specify a historical date "
            "or period, use the latest/current available rate. "
            "Only treat the request as historical when the "
            "user explicitly asks for a past date or period."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {
                    "type": "number",
                    "description": (
                        "The amount of money to convert."
                    )
                },
                "from_currency": {
                    "type": "string",
                    "description": (
                        "Three-letter source currency code, "
                        "such as USD, EUR, GBP, or INR."
                    )
                },
                "to_currency": {
                    "type": "string",
                    "description": (
                        "Three-letter destination currency "
                        "code, such as USD, EUR, GBP, or INR."
                    )
                }
            },
            "required": [
                "amount",
                "from_currency",
                "to_currency"
            ]
        }
    }
},

# ========================================================
# CALCULATOR
# ========================================================

{
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Perform a mathematical calculation or arithmetic "
            "expression. Use this tool when an exact numerical "
            "calculation is required. Do not use this tool for "
            "current financial market data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "A mathematical expression such as "
                        "125 * 30, 1000 / 8, or sqrt(144)."
                    )
                }
            },
            "required": [
                "expression"
            ]
        }
    }
},

# ========================================================
# FINANCE NEWS
# ========================================================

{
    "type": "function",
    "function": {
        "name": "get_finance_news",
        "description": (
            "Get current/recent financial news about a "
            "specified company, cryptocurrency, market, "
            "economic topic, or financial subject. "
            "If the user asks for finance news without "
            "specifying a date or historical period, interpret "
            "the request as asking for the latest/current "
            "available news. "
            "If the user explicitly specifies a historical "
            "date or period, preserve that request."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": (
                        "The company, cryptocurrency, market, "
                        "economic topic, or financial subject "
                        "for which news is requested."
                    )
                }
            },
            "required": [
                "topic"
            ]
        }
    }
},

# ========================================================
# CURRENT DATE AND TIME
# ========================================================

{
    "type": "function",
    "function": {
        "name": "get_current_datetime",
        "description": (
            "Get the actual current date, day, and time. "
            "Use this tool when the user asks for the current "
            "date/time or when an exact current date is needed "
            "to interpret a relative date such as today, "
            "yesterday, tomorrow, this week, this month, "
            "or this year. "
            "Do not use this tool unnecessarily for ordinary "
            "requests that do not depend on the current date "
            "or time."
        ),
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}


]
