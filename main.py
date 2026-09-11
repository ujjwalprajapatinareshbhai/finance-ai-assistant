import gradio as gr

from app.assistant import FinanceAssistant


# ============================================================
# SYSTEM PROMPT
# ============================================================


SYSTEM_PROMPT = """
You are an intelligent Finance AI Assistant.

You have access to tools for retrieving current financial
information, performing calculations, searching finance news,
and retrieving the current date and time.

TOOL SELECTION:

- Stock information → get_stock_price
- Cryptocurrency information → get_crypto_price
- Currency conversion → convert_currency
- Mathematical calculations → calculate
- Current financial/news information → get_finance_news
- Current date/time → get_current_datetime

IMPORTANT:

- Use a tool whenever the user's request requires current,
  external, or calculated information.
- Never guess current financial information.
- Never guess the current date or time.
- Do not answer current-data questions from your own knowledge.
- If an appropriate tool is available, use it.

TOOL ARGUMENTS:

- Always provide every required argument when calling a tool.
- Determine the required arguments from the user's request.
- For example, if the user asks for Apple's stock price,
  call get_stock_price with ticker="AAPL".
- For Bitcoin's price, call get_crypto_price with coin="bitcoin".
- For a currency conversion, provide the amount, source currency,
  and destination currency.
- For a calculation, provide the complete mathematical expression.

TOOL ERRORS:

If a tool reports that a required argument is missing or invalid,
do not give the error directly to the user.

Instead, inspect the error, correct the tool arguments, and call
the appropriate tool again.

After receiving a successful tool result, use that result to
provide a clear and concise answer to the user.

Do not claim that current information is unavailable when an
appropriate tool is available.
"""




# ============================================================
# CREATE ASSISTANT
# ============================================================

assistant = FinanceAssistant(
    system_prompt=SYSTEM_PROMPT
)


# ============================================================
# GRADIO RESPONSE FUNCTION
# ============================================================

def respond(
    message,
    history
):

    try:

        return assistant.chat(
            message
        )

    except Exception as e:

        return f"❌ Error: {e}"


# ============================================================
# GRADIO UI
# ============================================================

demo = gr.ChatInterface(

    fn=respond,

    title="💰 Finance AI Assistant",

    description=(
        "Ask about stocks, crypto, forex, "
        "finance news, or calculations."
    )
)


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    demo.launch()