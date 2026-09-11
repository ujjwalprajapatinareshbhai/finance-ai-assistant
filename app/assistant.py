import json
import re
import difflib

import ollama

from app.config import OLLAMA_HOST, OLLAMA_MODEL
from app.memory import Memory
from app.models import CryptoPrice
from app.safety import is_flagged
from app.tool_manager import ToolManager
from app.tools.definitions import TOOLS


class FinanceAssistant:
    """
    Finance AI Assistant powered by Ollama.

    Responsibilities:
    - Let the LLM select the appropriate finance tool.
    - Execute external tools through ToolManager.
    - Validate tool arguments and results.
    - Resolve and verify cryptocurrency results.
    - Prevent cryptocurrency entity substitution during retries.
    - Keep the CURRENT user request authoritative.
    - Prevent previous conversation memory from contaminating
      initial tool selection.
    - Never invent financial numbers.
    - Return deterministic responses from verified tool results.
    """

    MAX_TOOL_ROUNDS = 5

    FINANCIAL_TOOLS = {
        "get_stock_price",
        "get_crypto_price",
        "convert_currency",
        "calculate",
    }

    AVAILABLE_TOOL_NAMES = {
        tool.get("function", {}).get("name")
        for tool in TOOLS
        if isinstance(tool, dict)
    }

    def __init__(self, system_prompt: str = ""):
        self.client = ollama.Client(host=OLLAMA_HOST)

        self.memory = Memory()
        self.tool_manager = ToolManager()

        self.system_prompt = system_prompt.strip()

    # ============================================================
    # SYSTEM PROMPT
    # ============================================================

    def _build_system_prompt(self) -> str:

        base_prompt = """
You are a finance AI assistant.

You have access to tools for:
- publicly traded company stocks/equities
- cryptocurrencies/digital assets
- currency conversion
- mathematical calculations
- current/recent finance news
- current date and time

============================================================
CURRENT REQUEST HAS HIGHEST PRIORITY
============================================================

The CURRENT USER REQUEST is the only authoritative request
for the current task.

Do NOT use a previous conversation request as the basis for
tool selection.

Do NOT reuse:
- previous numbers
- previous currencies
- previous stocks
- previous cryptocurrencies
- previous tickers
- previous tool arguments
- previous entities

unless the CURRENT USER REQUEST explicitly refers to them.

If the current user asks for a new value, entity, amount,
currency, stock, cryptocurrency, expression, topic, date,
or time, use the value from the CURRENT USER REQUEST.

============================================================
TOOL SELECTION
============================================================

1. Use the available tools whenever the user asks for:
   - current or latest information
   - external financial information
   - stock prices
   - cryptocurrency prices
   - currency conversion
   - calculations
   - current/recent finance news
   - the current date or time

2. Choose the tool according to the semantic type of the
   CURRENT USER REQUEST.

3. Do NOT assume every financial asset is a stock.

4. For stock/equity requests:
   use get_stock_price.

5. For cryptocurrency/digital-asset requests:
   use get_crypto_price.

6. For currency conversion requests:
   use convert_currency.

7. For mathematical expressions:
   use calculate.

8. For finance news:
   use get_finance_news.

9. For current date/time:
   use get_current_datetime.

============================================================
CURRENCY CONVERSION
============================================================

For currency conversion, use:

convert_currency

with concrete arguments:

{
    "amount": <actual numeric amount>,
    "from_currency": "<source currency>",
    "to_currency": "<destination currency>"
}

Example:

User:
100000 USD to INR

Correct tool call:

{
    "amount": 100000,
    "from_currency": "USD",
    "to_currency": "INR"
}

Do NOT reuse an amount from an earlier request.

For example, if an earlier request was:

90000 USD to INR

and the CURRENT request is:

100000 USD to INR

you MUST use:

100000

NOT:

90000

============================================================
CRYPTOCURRENCY
============================================================

For cryptocurrency requests, use get_crypto_price.

The cryptocurrency requested by the CURRENT USER REQUEST
must remain unchanged.

Never replace one cryptocurrency with another cryptocurrency.

If a cryptocurrency tool attempt fails, retry using the
SAME cryptocurrency requested by the current user.

Do not use a different cryptocurrency from conversation
history.

get_crypto_price requires only:

{
    "coin": "<actual cryptocurrency>"
}

Do not add unrelated arguments.

============================================================
STOCKS
============================================================

For stock/equity requests, use get_stock_price.

The ticker must come from the CURRENT USER REQUEST.

Do not reuse a ticker from an earlier request unless the
CURRENT USER REQUEST explicitly refers to it.

============================================================
GENERAL TOOL RULES
============================================================

1. Do not invent financial numbers.

2. Do not answer current market-data questions from your own
   knowledge.

3. If a tool returns valid data, the application will use the
   verified tool result directly.

4. Never fabricate a tool result.

5. When a tool requires no arguments, call it with {}.

6. Tool arguments must contain actual values.

7. Never output a tool JSON schema instead of making a tool call.

8. Never output function definitions or parameter schemas as
   the final answer.

9. If a tool is required, make a native tool call.

10. Tool arguments must contain only actual parameters required
    by the selected tool.

11. Do not wrap actual arguments inside:
    - function
    - type
    - name
    - tool-definition
    - parameters
    - properties

12. For currency conversion, amount must be an actual numeric
    value.

13. If necessary, convert a numeric string such as "100000"
    into the number 100000.

14. For datetime, provide {}.

15. The CURRENT USER REQUEST always has priority over previous
    conversation history.

16. If a previous tool attempt was invalid, re-evaluate the
    CURRENT USER REQUEST.

17. Do not switch entities because of previous tool results.

18. Do not answer from memory when a tool is required.

19. If you cannot make a valid tool call, do not invent an answer.

============================================================
IMPORTANT FOR SMALL MODELS
============================================================

Before making a tool call, identify the semantic category of
the CURRENT USER REQUEST.

Choose exactly the appropriate tool.

Then extract concrete arguments ONLY from the CURRENT USER
REQUEST.

Do not output all available functions.

Do not output function schemas.

Do not call multiple unrelated finance tools simply because
they are available.

If the user asks for currency conversion, do not call a stock
tool.

If the user asks for cryptocurrency price, do not call a stock
tool.

If the user asks for stock price, do not call a cryptocurrency
tool.

If the user asks for calculation, do not call a market-data
tool.
"""

        if self.system_prompt:

            return (
                base_prompt
                + "\nAdditional instructions:\n"
                + self.system_prompt
            )

        return base_prompt

    # ============================================================
    # TEXT NORMALIZATION
    # ============================================================

    @staticmethod
    def _normalize_text(value) -> str:
        """
        Normalize text for generic entity comparison.

        This intentionally contains no hard-coded asset names,
        symbols, or aliases.
        """

        if value is None:
            return ""

        value = str(value).lower().strip()

        value = re.sub(
            r"[^a-z0-9]+",
            " ",
            value
        )

        return " ".join(value.split())

    # ============================================================
    # TEXT SIMILARITY
    # ============================================================

    @classmethod
    def _text_similarity(
        cls,
        first,
        second
    ) -> float:

        first = cls._normalize_text(first)
        second = cls._normalize_text(second)

        if not first or not second:
            return 0.0

        if first == second:
            return 1.0

        return difflib.SequenceMatcher(
            None,
            first,
            second
        ).ratio()

    # ============================================================
    # RESPONSE HELPERS
    # ============================================================

    @staticmethod
    def _message_to_dict(message):

        """
        Convert an Ollama Message object into a normal dictionary.
        """

        if message is None:
            return {}

        if isinstance(message, dict):
            return message

        if hasattr(message, "model_dump"):

            try:
                return message.model_dump()

            except Exception:
                pass

        result = {}

        for field in [
            "role",
            "content",
            "thinking",
            "images",
            "tool_name",
            "tool_calls",
        ]:

            if hasattr(message, field):
                result[field] = getattr(
                    message,
                    field
                )

        return result

    @staticmethod
    def _tool_call_to_dict(tool_call):

        """
        Convert Ollama ToolCall object into a dictionary.
        """

        if isinstance(tool_call, dict):
            return tool_call

        if hasattr(tool_call, "model_dump"):

            try:
                return tool_call.model_dump()

            except Exception:
                pass

        function = getattr(
            tool_call,
            "function",
            None
        )

        if function is not None:

            if hasattr(function, "model_dump"):

                try:
                    function_data = function.model_dump()

                except Exception:
                    function_data = {}

            elif isinstance(function, dict):

                function_data = function

            else:

                function_data = {}

                if hasattr(function, "name"):
                    function_data["name"] = function.name

                if hasattr(function, "arguments"):
                    function_data["arguments"] = function.arguments

            return {
                "function": function_data
            }

        return {}

    # ============================================================
    # TOOL SCHEMA RECOVERY
    # ============================================================

    @staticmethod
    def _extract_schema_tool_name(content: str):

        """
        Detect when the small model outputs a function schema as
        plain text instead of producing a native tool call.

        This does NOT perform keyword routing.
        """

        if not content or not content.strip():
            return None

        text = content.strip()

        if (
            '"type":"function"' not in text
            and
            '"type": "function"' not in text
        ):
            return None

        if '"function"' not in text:
            return None

        matches = re.findall(
            r'"name"\s*:\s*"([^"]+)"',
            text
        )

        if not matches:
            return None

        for name in matches:

            name = name.strip()

            if (
                name
                in FinanceAssistant.AVAILABLE_TOOL_NAMES
            ):
                return name

        return None

    @staticmethod
    def _is_tool_schema_content(content: str) -> bool:

        """
        Determine whether LLM content appears to be a tool schema
        rather than a normal assistant response.
        """

        if not content or not content.strip():
            return False

        text = content.strip()

        schema_markers = [
            '"type":"function"',
            '"type": "function"',
        ]

        function_marker = (
            '"function"' in text
        )

        parameters_marker = (
            '"parameters"' in text
            or
            '"properties"' in text
        )

        return (
            any(
                marker in text
                for marker in schema_markers
            )
            and
            function_marker
            and
            parameters_marker
        )

    @staticmethod
    def _looks_like_tool_schema(arguments: dict) -> bool:

        """
        Detect when Ollama puts a function schema inside the tool
        arguments instead of providing concrete argument values.
        """

        if not isinstance(arguments, dict):
            return False

        # --------------------------------------------------------
        # Standard JSON schema object
        # --------------------------------------------------------

        if (
            arguments.get("type") == "object"
            and
            (
                "properties" in arguments
                or
                "required" in arguments
            )
        ):
            return True

        # --------------------------------------------------------
        # Another common schema form
        # --------------------------------------------------------

        if (
            "required" in arguments
            and
            "properties" in arguments
        ):
            return True

        # --------------------------------------------------------
        # Parameters wrapper
        # --------------------------------------------------------

        if (
            "parameters" in arguments
            and
            isinstance(
                arguments.get("parameters"),
                dict
            )
        ):
            return True

        # --------------------------------------------------------
        # Function wrapper
        # --------------------------------------------------------

        if (
            "function" in arguments
            and
            isinstance(
                arguments.get("function"),
                str
            )
        ):
            return True

        return False

    # ============================================================
    # TOOL ARGUMENT HELPERS
    # ============================================================

    @staticmethod
    def _normalize_arguments(arguments):

        """
        Normalize tool arguments returned by Ollama.

        Supports:

        1. Normal dictionary.
        2. JSON string.
        3. Parameters wrapper.
        4. Arguments wrapper.
        5. Properties wrapper.

        This method is generic.

        It does NOT determine which tool should be used.
        It does NOT inspect asset names.
        It does NOT perform keyword routing.
        """

        if arguments is None:
            return {}

        # --------------------------------------------------------
        # JSON string
        # --------------------------------------------------------

        if isinstance(arguments, str):

            text = arguments.strip()

            if not text:
                return {}

            try:

                parsed = json.loads(text)

            except Exception:

                return {}

            return FinanceAssistant._normalize_arguments(
                parsed
            )

        # --------------------------------------------------------
        # Dictionary
        # --------------------------------------------------------

        if not isinstance(arguments, dict):
            return {}

        # --------------------------------------------------------
        # Empty object
        # --------------------------------------------------------

        if not arguments:
            return {}

        # --------------------------------------------------------
        # PARAMETERS WRAPPER
        # --------------------------------------------------------

        parameters = arguments.get(
            "parameters"
        )

        if isinstance(parameters, dict):

            return FinanceAssistant._normalize_arguments(
                parameters
            )

        # --------------------------------------------------------
        # ARGUMENTS WRAPPER
        # --------------------------------------------------------

        nested_arguments = arguments.get(
            "arguments"
        )

        if isinstance(
            nested_arguments,
            (dict, str)
        ):

            return FinanceAssistant._normalize_arguments(
                nested_arguments
            )

        # --------------------------------------------------------
        # PROPERTIES WRAPPER
        # --------------------------------------------------------

        properties = arguments.get(
            "properties"
        )

        if isinstance(properties, dict):

            return FinanceAssistant._normalize_arguments(
                properties
            )

        # --------------------------------------------------------
        # Normal argument object
        # --------------------------------------------------------

        return arguments

    def _get_tool_name(
        self,
        tool_call
    ):

        function = tool_call.get(
            "function",
            {}
        )

        if not isinstance(
            function,
            dict
        ):
            return None

        name = function.get(
            "name"
        )

        if isinstance(name, str):

            return name.strip()

        return None

    def _get_tool_arguments(
        self,
        tool_call
    ):

        function = tool_call.get(
            "function",
            {}
        )

        if not isinstance(
            function,
            dict
        ):
            return {}

        arguments = function.get(
            "arguments"
        )

        return self._normalize_arguments(
            arguments
        )

    # ============================================================
    # TOOL ARGUMENT FILTERING
    # ============================================================

    def _filter_tool_arguments(
        self,
        tool_name: str,
        arguments: dict
    ) -> dict:

        """
        Keep only arguments declared by the selected tool.

        This prevents accidental cross-tool arguments.

        No asset names are inspected here.
        """

        if not isinstance(
            arguments,
            dict
        ):
            return {}

        tool_definition = None

        for tool in TOOLS:

            if not isinstance(
                tool,
                dict
            ):
                continue

            function = tool.get(
                "function",
                {}
            )

            if not isinstance(
                function,
                dict
            ):
                continue

            if function.get(
                "name"
            ) == tool_name:

                tool_definition = tool
                break

        if not tool_definition:
            return dict(arguments)

        function = tool_definition.get(
            "function",
            {}
        )

        parameters = function.get(
            "parameters",
            {}
        )

        properties = parameters.get(
            "properties",
            {}
        )

        if not isinstance(
            properties,
            dict
        ):
            return dict(arguments)

        allowed_keys = set(
            properties.keys()
        )

        return {
            key: value
            for key, value in arguments.items()
            if key in allowed_keys
        }

    # ============================================================
    # ARGUMENT VALIDATION
    # ============================================================

    def _validate_arguments(
        self,
        tool_name: str,
        arguments: dict
    ):

        """
        Validate actual runtime arguments.

        No cryptocurrency or stock name lists are used.
        """

        if tool_name not in self.AVAILABLE_TOOL_NAMES:

            return (
                False,
                f"Unknown tool: {tool_name}"
            )

        if not isinstance(
            arguments,
            dict
        ):

            return (
                False,
                "Tool arguments must be a JSON object."
            )

        # --------------------------------------------------------
        # TOOL SCHEMA
        # --------------------------------------------------------

        if self._looks_like_tool_schema(
            arguments
        ):

            return (
                False,
                "The model provided a tool schema instead "
                "of concrete argument values."
            )

        # ========================================================
        # DATETIME
        # ========================================================

        if tool_name == "get_current_datetime":

            if arguments:

                return (
                    False,
                    "The datetime tool requires an empty "
                    "argument object {}."
                )

            return True, None

        # ========================================================
        # STOCK
        # ========================================================

        if tool_name == "get_stock_price":

            ticker = arguments.get(
                "ticker"
            )

            if (
                not isinstance(
                    ticker,
                    str
                )
                or
                not ticker.strip()
            ):

                return (
                    False,
                    "The stock tool requires a concrete ticker."
                )

            arguments["ticker"] = (
                ticker.strip().upper()
            )

            return True, None

        # ========================================================
        # CRYPTO
        # ========================================================

        if tool_name == "get_crypto_price":

            coin = arguments.get(
                "coin"
            )

            if (
                not isinstance(
                    coin,
                    str
                )
                or
                not coin.strip()
            ):

                return (
                    False,
                    "The cryptocurrency tool requires "
                    "a concrete coin."
                )

            arguments["coin"] = (
                coin.strip()
            )

            return True, None

        # ========================================================
        # FOREX
        # ========================================================

        if tool_name == "convert_currency":

            amount = arguments.get(
                "amount"
            )

            from_currency = arguments.get(
                "from_currency"
            )

            to_currency = arguments.get(
                "to_currency"
            )

            # ----------------------------------------------------
            # Convert numeric strings.
            # ----------------------------------------------------

            if isinstance(
                amount,
                bool
            ):

                return (
                    False,
                    "The currency conversion amount "
                    "must be numeric."
                )

            if isinstance(
                amount,
                str
            ):

                amount_text = amount.strip()

                if not amount_text:

                    return (
                        False,
                        "The currency conversion requires "
                        "a numeric amount."
                    )

                try:

                    amount = float(
                        amount_text
                    )

                except ValueError:

                    return (
                        False,
                        "The currency conversion requires "
                        "a numeric amount."
                    )

                arguments["amount"] = amount

            if not isinstance(
                amount,
                (int, float)
            ):

                return (
                    False,
                    "The currency conversion requires "
                    "a numeric amount."
                )

            if amount < 0:

                return (
                    False,
                    "The currency conversion amount "
                    "cannot be negative."
                )

            # ----------------------------------------------------
            # Source currency.
            # ----------------------------------------------------

            if (
                not isinstance(
                    from_currency,
                    str
                )
                or
                not from_currency.strip()
            ):

                return (
                    False,
                    "The source currency is missing."
                )

            # ----------------------------------------------------
            # Destination currency.
            # ----------------------------------------------------

            if (
                not isinstance(
                    to_currency,
                    str
                )
                or
                not to_currency.strip()
            ):

                return (
                    False,
                    "The destination currency is missing."
                )

            arguments["from_currency"] = (
                from_currency.strip().upper()
            )

            arguments["to_currency"] = (
                to_currency.strip().upper()
            )

            return True, None

        # ========================================================
        # CALCULATOR
        # ========================================================

        if tool_name == "calculate":

            expression = arguments.get(
                "expression"
            )

            if (
                not isinstance(
                    expression,
                    str
                )
                or
                not expression.strip()
            ):

                return (
                    False,
                    "The calculator requires "
                    "a concrete expression."
                )

            arguments["expression"] = (
                expression.strip()
            )

            return True, None

        # ========================================================
        # NEWS
        # ========================================================

        if tool_name == "get_finance_news":

            topic = arguments.get(
                "topic"
            )

            if (
                not isinstance(
                    topic,
                    str
                )
                or
                not topic.strip()
            ):

                return (
                    False,
                    "The finance news tool requires "
                    "a concrete topic."
                )

            arguments["topic"] = (
                topic.strip()
            )

            return True, None

        return True, None

    # ============================================================
    # CRYPTO REQUEST EXTRACTION
    # ============================================================

    def _extract_requested_crypto(
        self,
        tool_name: str,
        arguments: dict
    ):

        """
        Extract the cryptocurrency identifier from a crypto
        tool call.

        This does NOT determine whether the tool itself is correct.

        It only records the asset the model attempted to use so
        that retries cannot silently substitute another asset.
        """

        if tool_name != "get_crypto_price":
            return None

        if not isinstance(
            arguments,
            dict
        ):
            return None

        coin = arguments.get(
            "coin"
        )

        if not isinstance(
            coin,
            str
        ):
            return None

        coin = coin.strip()

        if not coin:
            return None

        return coin

    # ============================================================
    # CRYPTO RESULT MATCHING
    # ============================================================

    def _crypto_result_matches_request(
        self,
        requested_crypto: str,
        tool_result
    ):
        """
        Verify that the cryptocurrency returned by CoinGecko
        actually corresponds to the cryptocurrency requested.

        The provider supplies:

        - resolved_coin_id
        - resolved_symbol
        - resolved_name

        No cryptocurrency list or hard-coded alias table is used.
        """

        if not requested_crypto:

            return (
                True,
                None
            )

        if not isinstance(
            tool_result,
            CryptoPrice
        ):

            return (
                False,
                "The cryptocurrency tool returned "
                "an invalid response object."
            )

        requested = self._normalize_text(
            requested_crypto
        )

        provider_values = [
            tool_result.resolved_coin_id,
            tool_result.resolved_symbol,
            tool_result.resolved_name,
        ]

        normalized_provider_values = [
            self._normalize_text(value)
            for value in provider_values
            if value
        ]

        # --------------------------------------------------------
        # Exact canonical match.
        # --------------------------------------------------------

        if requested in normalized_provider_values:

            return (
                True,
                None
            )

        # --------------------------------------------------------
        # Similarity fallback.
        # --------------------------------------------------------

        best_score = 0.0

        for value in provider_values:

            if not value:
                continue

            score = self._text_similarity(
                requested_crypto,
                value
            )

            if score > best_score:
                best_score = score

        if best_score >= 0.85:

            return (
                True,
                None
            )

        return (
            False,
            (
                "The cryptocurrency provider returned a "
                "different asset. "
                f"Requested: '{requested_crypto}'. "
                f"Provider returned: "
                f"'{tool_result.resolved_name}' "
                f"({tool_result.resolved_symbol})."
            )
        )

    # ============================================================
    # TOOL RESULT HELPERS
    # ============================================================

    @staticmethod
    def _serialize_tool_result(
        tool_result
    ):

        """
        Convert Pydantic/object/dict result into a JSON string.
        """

        if tool_result is None:
            return "{}"

        if hasattr(
            tool_result,
            "model_dump"
        ):

            data = tool_result.model_dump()

        elif isinstance(
            tool_result,
            dict
        ):

            data = tool_result

        else:

            try:

                data = vars(
                    tool_result
                )

            except Exception:

                data = {
                    "result": str(
                        tool_result
                    )
                }

        return json.dumps(
            data,
            ensure_ascii=False
        )

    @staticmethod
    def _result_as_dict(
        tool_result
    ):

        """
        Convert tool result into a dictionary.
        """

        if tool_result is None:
            return {}

        if hasattr(
            tool_result,
            "model_dump"
        ):

            try:

                return tool_result.model_dump()

            except Exception:
                pass

        if isinstance(
            tool_result,
            dict
        ):
            return tool_result

        try:

            return vars(
                tool_result
            )

        except Exception:

            return {}

    # ============================================================
    # TOOL RESULT VALIDATION
    # ============================================================

    @staticmethod
    def _validate_tool_result(
        tool_name: str,
        tool_result
    ):

        """
        Validate returned data before using it.

        No cryptocurrency names or stock names are hard-coded.
        """

        data = FinanceAssistant._result_as_dict(
            tool_result
        )

        if not data:

            return (
                False,
                "The tool returned no data."
            )

        if not data.get(
            "success",
            False
        ):

            return (
                False,
                data.get(
                    "message",
                    "The tool reported that the operation failed."
                )
            )

        # ========================================================
        # STOCK
        # ========================================================

        if tool_name == "get_stock_price":

            company = data.get(
                "company"
            )

            price = data.get(
                "price_usd"
            )

            if (
                not isinstance(
                    company,
                    str
                )
                or
                not company.strip()
            ):

                return (
                    False,
                    "The stock tool returned incomplete "
                    "company information."
                )

            if not isinstance(
                price,
                (int, float)
            ):

                return (
                    False,
                    "The stock tool returned "
                    "an invalid price."
                )

            if price <= 0:

                return (
                    False,
                    "The stock tool returned an invalid "
                    "market price."
                )

        # ========================================================
        # CRYPTO
        # ========================================================

        elif tool_name == "get_crypto_price":

            price = data.get(
                "price_usd"
            )

            if not isinstance(
                price,
                (int, float)
            ):

                return (
                    False,
                    "The cryptocurrency tool returned "
                    "an invalid price."
                )

            if price <= 0:

                return (
                    False,
                    "The cryptocurrency tool returned "
                    "an invalid market price."
                )

            # ----------------------------------------------------
            # Canonical CoinGecko identity is required.
            # ----------------------------------------------------

            resolved_coin_id = data.get(
                "resolved_coin_id"
            )

            resolved_symbol = data.get(
                "resolved_symbol"
            )

            resolved_name = data.get(
                "resolved_name"
            )

            if (
                not isinstance(
                    resolved_coin_id,
                    str
                )
                or
                not resolved_coin_id.strip()
            ):

                return (
                    False,
                    "The cryptocurrency tool did not "
                    "return a canonical CoinGecko ID."
                )

            if (
                not isinstance(
                    resolved_name,
                    str
                )
                or
                not resolved_name.strip()
            ):

                return (
                    False,
                    "The cryptocurrency tool did not "
                    "return a canonical cryptocurrency name."
                )

            if (
                resolved_symbol is not None
                and
                not isinstance(
                    resolved_symbol,
                    str
                )
            ):

                return (
                    False,
                    "The cryptocurrency tool returned "
                    "an invalid symbol."
                )

        # ========================================================
        # FOREX
        # ========================================================

        elif tool_name == "convert_currency":

            converted_amount = data.get(
                "converted_amount"
            )

            if not isinstance(
                converted_amount,
                (int, float)
            ):

                return (
                    False,
                    "The currency conversion tool returned "
                    "an invalid result."
                )

        # ========================================================
        # CALCULATOR
        # ========================================================

        elif tool_name == "calculate":

            result = data.get(
                "result"
            )

            if not isinstance(
                result,
                (int, float)
            ):

                return (
                    False,
                    "The calculator returned "
                    "an invalid result."
                )

        # ========================================================
        # NEWS
        # ========================================================

        elif tool_name == "get_finance_news":

            summary = data.get(
                "summary"
            )

            if (
                not isinstance(
                    summary,
                    str
                )
                or
                not summary.strip()
            ):

                return (
                    False,
                    "The finance news tool returned "
                    "no usable news content."
                )

        # ========================================================
        # DATETIME
        # ========================================================

        elif tool_name == "get_current_datetime":

            date = data.get(
                "date"
            )

            if (
                not isinstance(
                    date,
                    str
                )
                or
                not date.strip()
            ):

                return (
                    False,
                    "The datetime tool returned "
                    "incomplete date information."
                )

        return True, None

    # ============================================================
    # RESULT FORMATTING
    # ============================================================

    @staticmethod
    def _format_result(
        tool_name: str,
        tool_result
    ):

        data = FinanceAssistant._result_as_dict(
            tool_result
        )

        # ========================================================
        # STOCK
        # ========================================================

        if tool_name == "get_stock_price":

            company = data.get(
                "company"
            )

            ticker = data.get(
                "ticker"
            )

            price = data.get(
                "price_usd"
            )

            change = data.get(
                "change_percent"
            )

            if isinstance(
                change,
                (int, float)
            ):

                return (
                    f"{company} ({ticker}) is currently "
                    f"${price:,.2f}. "
                    f"The change is {change:.4f}%."
                )

            return (
                f"{company} ({ticker}) is currently "
                f"${price:,.2f}."
            )

        # ========================================================
        # CRYPTO
        # ========================================================

        if tool_name == "get_crypto_price":

            coin = (
                data.get(
                    "resolved_name"
                )
                or
                data.get(
                    "coin"
                )
            )

            price = data.get(
                "price_usd"
            )

            return (
                f"{coin} is currently "
                f"${price:,.2f} USD."
            )

        # ========================================================
        # FOREX
        # ========================================================

        if tool_name == "convert_currency":

            amount = data.get(
                "amount"
            )

            from_currency = data.get(
                "from_currency"
            )

            to_currency = data.get(
                "to_currency"
            )

            converted_amount = data.get(
                "converted_amount"
            )

            return (
                f"{amount:,.2f} "
                f"{from_currency} is equal to "
                f"{converted_amount:,.2f} "
                f"{to_currency}."
            )

        # ========================================================
        # CALCULATOR
        # ========================================================

        if tool_name == "calculate":

            expression = data.get(
                "expression"
            )

            result = data.get(
                "result"
            )

            return (
                f"The result of "
                f"{expression} is {result}."
            )

        # ========================================================
        # NEWS
        # ========================================================

        if tool_name == "get_finance_news":

            title = data.get(
                "title",
                "Finance News"
            )

            summary = data.get(
                "summary",
                ""
            )

            source = data.get(
                "source"
            )

            response = (
                f"{title}\n\n"
                f"{summary}"
            )

            if source:

                response += (
                    f"\n\nSource: {source}"
                )

            return response

        # ========================================================
        # DATETIME
        # ========================================================

        if tool_name == "get_current_datetime":

            date = data.get(
                "date"
            )

            day = data.get(
                "day"
            )

            time = data.get(
                "time"
            )

            if day and time:

                return (
                    f"The current date is "
                    f"{day}, {date}. "
                    f"The current time is {time}."
                )

            return (
                f"The current date is "
                f"{day}, {date}."
            )

        return data.get(
            "message",
            "The tool completed successfully."
        )

    # ============================================================
    # RETRY MESSAGE
    # ============================================================

    @staticmethod
    def _build_retry_message(
        user_message: str,
        reason: str,
        requested_crypto=None
    ):

        """
        Build a retry instruction.

        The CURRENT user request is repeated so the small model
        does not accidentally switch to a previous conversation
        request.

        When cryptocurrency resolution is involved, the original
        requested cryptocurrency is explicitly preserved.
        """

        message = (
            "The previous tool attempt was invalid.\n\n"
            f"Reason: {reason}\n\n"
        )

        if requested_crypto:

            message += (
                "IMPORTANT CRYPTOCURRENCY RULE:\n"
                f"The original requested cryptocurrency is "
                f"'{requested_crypto}'.\n"
                "You MUST keep this exact cryptocurrency.\n"
                "Do NOT replace it with another cryptocurrency.\n"
                "You may select a more appropriate tool, but "
                "the asset itself must remain unchanged.\n\n"
            )

        message += (
            "IMPORTANT CURRENT REQUEST RULE:\n"
            "The following is the CURRENT USER REQUEST.\n"
            "It has higher priority than every previous message.\n"
            "Do not reuse values from previous requests.\n"
            "Do not reuse previous tool arguments.\n"
            "Do not use an earlier stock, cryptocurrency, amount, "
            "currency, ticker, expression, or topic.\n\n"

            "You must handle the CURRENT USER REQUEST below.\n"
            "Do not output a function schema.\n"
            "Do not answer from memory.\n"
            "Make exactly the appropriate native tool call "
            "with concrete argument values.\n\n"

            "CURRENT USER REQUEST:\n"
            f"{user_message}"
        )

        return message

    # ============================================================
    # ASSISTANT TOOL MESSAGE
    # ============================================================

    @staticmethod
    def _build_assistant_tool_message(
        content: str,
        tool_calls: list
    ) -> dict:

        """
        Build an assistant message containing the native tool
        calls returned by Ollama.

        This is important because the next tool-result message
        should correspond to the assistant's tool call.
        """

        message = {
            "role": "assistant",
            "content": content or "",
            "tool_calls": tool_calls,
        }

        return message

    # ============================================================
    # TOOL ERROR RETRY
    # ============================================================

    def _append_retry(
        self,
        messages,
        user_message,
        reason,
        requested_crypto=None,
        tool_name=None
    ):

        """
        Add a tool error and a fresh current-request instruction.

        The retry always repeats the CURRENT USER REQUEST.
        """

        if tool_name:

            messages.append(
                {
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": reason,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": (
                    self._build_retry_message(
                        user_message,
                        reason,
                        requested_crypto,
                    )
                ),
            }
        )

    # ============================================================
    # CHAT
    # ============================================================

    def chat(
        self,
        user_message: str
    ) -> str:

        if (
            not user_message
            or
            not user_message.strip()
        ):

            return "Please enter a message."

        user_message = user_message.strip()

        # ========================================================
        # SAFETY
        # ========================================================

        if is_flagged(
            user_message
        ):

            return (
                "I can't help with that request. "
                "Please ask a legitimate finance or "
                "productivity question."
            )

        # ========================================================
        # INITIAL MESSAGES
        # ========================================================

        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt(),
            }
        ]

        # ========================================================
        # IMPORTANT:
        #
        # Do NOT add:
        #
        # self.memory.get_messages()
        #
        # here.
        #
        # Previous financial conversations were causing the
        # small Ollama model to reuse old entities/arguments.
        #
        # The CURRENT USER REQUEST must control tool selection.
        # ========================================================

        messages.append(
            {
                "role": "user",
                "content": (
                    "CURRENT USER REQUEST:\n"
                    + user_message
                ),
            }
        )

        final_answer = None

        tool_was_required = False

        # ========================================================
        # CRYPTO REQUEST TRACKING
        # ========================================================

        requested_crypto = None

        # ========================================================
        # TOOL LOOP
        # ========================================================

        for round_number in range(
            1,
            self.MAX_TOOL_ROUNDS + 1
        ):

            print()
            print(
                "🤖 OLLAMA ROUND",
                round_number
            )

            try:

                response = self.client.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=TOOLS,
                )

            except Exception as exc:

                print()
                print(
                    "❌ OLLAMA ERROR"
                )

                print(
                    str(exc)
                )

                final_answer = (
                    "I couldn't complete the request because "
                    "the AI model could not be reached."
                )

                break

            # ====================================================
            # OLLAMA RESPONSE
            # ====================================================

            assistant_message = getattr(
                response,
                "message",
                None
            )

            message_data = (
                self._message_to_dict(
                    assistant_message
                )
            )

            content = (
                message_data.get(
                    "content",
                    ""
                )
                or
                ""
            )

            # ====================================================
            # NATIVE TOOL CALLS
            # ====================================================

            raw_tool_calls = []

            if assistant_message is not None:

                raw_tool_calls = (
                    getattr(
                        assistant_message,
                        "tool_calls",
                        None
                    )
                    or
                    []
                )

            tool_calls = [
                self._tool_call_to_dict(
                    call
                )
                for call in raw_tool_calls
            ]

            tool_calls = [
                call
                for call in tool_calls
                if isinstance(
                    call,
                    dict
                )
            ]

            # ====================================================
            # PRINT MODEL CONTENT
            # ====================================================

            if content.strip():

                print()
                print(
                    "🧠 LLM CONTENT"
                )

                print(
                    content
                )

            # ====================================================
            # FUNCTION SCHEMA LEAK
            # ====================================================

            if (
                not tool_calls
                and
                self._is_tool_schema_content(
                    content
                )
            ):

                schema_tool_name = (
                    self._extract_schema_tool_name(
                        content
                    )
                )

                if schema_tool_name:

                    tool_was_required = True

                    print()
                    print(
                        "⚠️ TOOL SCHEMA DETECTED "
                        "IN LLM CONTENT"
                    )

                    print(
                        f"Detected tool: "
                        f"{schema_tool_name}"
                    )

                    print(
                        "🔄 REQUESTING CONCRETE "
                        "TOOL ARGUMENTS..."
                    )

                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                self._build_retry_message(
                                    user_message,
                                    (
                                        "The model output a "
                                        "tool schema instead of "
                                        "making a native tool call."
                                    ),
                                    requested_crypto,
                                )
                            ),
                        }
                    )

                    continue

            # ====================================================
            # NO TOOL CALL
            # ====================================================

            if not tool_calls:

                print()
                print(
                    "✅ NO TOOL CALL"
                )

                if tool_was_required:

                    print()
                    print(
                        "⚠️ TOOL REQUIRED BUT "
                        "NO VALID TOOL CALL"
                    )

                    if (
                        round_number
                        <
                        self.MAX_TOOL_ROUNDS
                    ):

                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    self._build_retry_message(
                                        user_message,
                                        (
                                            "The response did not "
                                            "contain a valid native "
                                            "tool call."
                                        ),
                                        requested_crypto,
                                    )
                                ),
                            }
                        )

                        continue

                    final_answer = (
                        "I couldn't obtain a verified result "
                        "from the required finance tool. "
                        "I will not invent an answer."
                    )

                    break

                final_answer = (
                    content.strip()
                )

                if not final_answer:

                    final_answer = (
                        "I couldn't determine a valid "
                        "tool action for that request."
                    )

                break

            # ====================================================
            # TOOL CALLS FOUND
            # ====================================================

            tool_was_required = True

            print()
            print(
                f"🔧 TOOL CALLS FOUND: "
                f"{len(tool_calls)}"
            )

            # ====================================================
            # PROCESS TOOL CALLS
            # ====================================================

            completed = False

            for tool_call in tool_calls:

                tool_name = (
                    self._get_tool_name(
                        tool_call
                    )
                )

                arguments = (
                    self._get_tool_arguments(
                        tool_call
                    )
                )

                # ------------------------------------------------
                # Remove arguments belonging to another tool.
                # ------------------------------------------------

                arguments = (
                    self._filter_tool_arguments(
                        tool_name,
                        arguments
                    )
                )

                print()
                print(
                    f"🔧 LLM TOOL CALL | "
                    f"Round {round_number}"
                )

                print(
                    f"Tool      : "
                    f"{tool_name}"
                )

                print(
                    "Arguments : "
                    + json.dumps(
                        arguments,
                        indent=2
                    )
                )

                # =================================================
                # TOOL NAME VALIDATION
                # =================================================

                if not tool_name:

                    reason = (
                        "The model did not provide "
                        "a tool name."
                    )

                    print()
                    print(
                        "❌ INVALID TOOL CALL"
                    )

                    print(
                        f"Reason: {reason}"
                    )

                    self._append_retry(
                        messages,
                        user_message,
                        reason,
                        requested_crypto,
                    )

                    continue

                if (
                    tool_name
                    not in
                    self.AVAILABLE_TOOL_NAMES
                ):

                    reason = (
                        f"Unknown tool: {tool_name}"
                    )

                    print()
                    print(
                        "❌ INVALID TOOL CALL"
                    )

                    print(
                        f"Reason: {reason}"
                    )

                    self._append_retry(
                        messages,
                        user_message,
                        reason,
                        requested_crypto,
                        tool_name,
                    )

                    continue

                # =================================================
                # ARGUMENT VALIDATION
                # =================================================

                valid_arguments, reason = (
                    self._validate_arguments(
                        tool_name,
                        arguments,
                    )
                )

                if not valid_arguments:

                    print()
                    print(
                        "❌ INVALID TOOL ARGUMENTS"
                    )

                    print(
                        f"Reason: {reason}"
                    )

                    self._append_retry(
                        messages,
                        user_message,
                        reason,
                        requested_crypto,
                        tool_name,
                    )

                    continue

                # =================================================
                # RECORD ORIGINAL CRYPTO REQUEST
                # =================================================

                current_crypto = (
                    self._extract_requested_crypto(
                        tool_name,
                        arguments
                    )
                )

                if (
                    requested_crypto is None
                    and
                    current_crypto is not None
                ):

                    requested_crypto = (
                        current_crypto
                    )

                    print()
                    print(
                        "🎯 ORIGINAL CRYPTO REQUEST:"
                    )

                    print(
                        requested_crypto
                    )

                # =================================================
                # PREVENT CRYPTO SUBSTITUTION
                # =================================================

                if (
                    requested_crypto
                    and
                    tool_name
                    == "get_crypto_price"
                ):

                    current_normalized = (
                        self._normalize_text(
                            current_crypto
                        )
                    )

                    requested_normalized = (
                        self._normalize_text(
                            requested_crypto
                        )
                    )

                    if (
                        current_normalized
                        !=
                        requested_normalized
                    ):

                        reason = (
                            "The cryptocurrency tool call "
                            "changed the requested asset. "
                            f"Original requested cryptocurrency: "
                            f"'{requested_crypto}'. "
                            f"Attempted cryptocurrency: "
                            f"'{current_crypto}'. "
                            "The original cryptocurrency must "
                            "remain unchanged."
                        )

                        print()
                        print(
                            "❌ CRYPTOCURRENCY "
                            "CONSISTENCY FAILED"
                        )

                        print(
                            f"Reason: {reason}"
                        )

                        self._append_retry(
                            messages,
                            user_message,
                            reason,
                            requested_crypto,
                            tool_name,
                        )

                        continue

                # =================================================
                # EXECUTE TOOL
                # =================================================

                print()
                print(
                    f"⚙️ EXECUTING: "
                    f"{tool_name}"
                )

                try:

                    tool_result = (
                        self.tool_manager.execute_tool(
                            tool_name,
                            arguments,
                        )
                    )

                except Exception as exc:

                    print()
                    print(
                        "❌ TOOL EXECUTION ERROR"
                    )

                    print(
                        str(exc)
                    )

                    error_message = (
                        f"Tool execution failed: {exc}"
                    )

                    self._append_retry(
                        messages,
                        user_message,
                        error_message,
                        requested_crypto,
                        tool_name,
                    )

                    continue

                # =================================================
                # PRINT TOOL RESULT
                # =================================================

                serialized_result = (
                    self._serialize_tool_result(
                        tool_result
                    )
                )

                print()
                print(
                    "📦 TOOL RESULT"
                )

                print(
                    f"Tool      : "
                    f"{tool_name}"
                )

                print(
                    f"Result    : "
                    f"{serialized_result}"
                )

                # =================================================
                # GENERAL RESULT VALIDATION
                # =================================================

                valid_result, reason = (
                    self._validate_tool_result(
                        tool_name,
                        tool_result,
                    )
                )

                if not valid_result:

                    print()
                    print(
                        "❌ INVALID TOOL RESULT"
                    )

                    print(
                        f"Reason: {reason}"
                    )

                    # ---------------------------------------------
                    # IMPORTANT:
                    #
                    # Tell Ollama exactly which assistant tool call
                    # produced this tool result.
                    # ---------------------------------------------

                    messages.append(
                        self._build_assistant_tool_message(
                            content,
                            [tool_call],
                        )
                    )

                    self._append_retry(
                        messages,
                        user_message,
                        (
                            "The selected tool returned "
                            "an invalid or incomplete result. "
                            + reason
                        ),
                        requested_crypto,
                        tool_name,
                    )

                    continue

                # =================================================
                # CRYPTO RESULT CONSISTENCY
                # =================================================

                if (
                    tool_name
                    == "get_crypto_price"
                    and
                    requested_crypto
                ):

                    matches, reason = (
                        self._crypto_result_matches_request(
                            requested_crypto,
                            tool_result,
                        )
                    )

                    if not matches:

                        print()
                        print(
                            "❌ CRYPTO RESULT "
                            "ENTITY MISMATCH"
                        )

                        print(
                            f"Reason: {reason}"
                        )

                        messages.append(
                            self._build_assistant_tool_message(
                                content,
                                [tool_call],
                            )
                        )

                        self._append_retry(
                            messages,
                            user_message,
                            (
                                "The cryptocurrency "
                                "result does not match "
                                "the original requested "
                                "asset. "
                                + reason
                            ),
                            requested_crypto,
                            tool_name,
                        )

                        continue

                    print()
                    print(
                        "✅ CRYPTO ENTITY VERIFIED"
                    )

                    print(
                        f"Requested : "
                        f"{requested_crypto}"
                    )

                    print(
                        f"Resolved  : "
                        f"{tool_result.resolved_name}"
                    )

                    print(
                        f"Symbol    : "
                        f"{tool_result.resolved_symbol}"
                    )

                    print(
                        f"Coin ID   : "
                        f"{tool_result.resolved_coin_id}"
                    )

                # =================================================
                # VERIFIED RESULT
                # =================================================

                print()
                print(
                    "✅ VERIFIED TOOL RESULT"
                )

                final_answer = (
                    self._format_result(
                        tool_name,
                        tool_result,
                    )
                )

                completed = True

                break

            if completed:
                break

        # ========================================================
        # MAX ROUND FALLBACK
        # ========================================================

        if (
            final_answer is None
            and
            tool_was_required
        ):

            if requested_crypto:

                final_answer = (
                    "I couldn't obtain a verified result for "
                    f"'{requested_crypto}' after several attempts. "
                    "I will not substitute another cryptocurrency "
                    "or invent a price."
                )

            else:

                final_answer = (
                    "I couldn't obtain a verified result from "
                    "the required finance tool after several "
                    "attempts. I will not invent an answer."
                )

        # ========================================================
        # MEMORY
        # ========================================================

        if final_answer:

            self.memory.add_message(
                "user",
                user_message,
            )

            self.memory.add_message(
                "assistant",
                final_answer,
            )

        # ========================================================
        # FINAL LOG
        # ========================================================

        print()
        print(
            "🏁 REQUEST COMPLETED"
        )

        print()
        print(
            "FINAL RESPONSE:"
        )

        print(
            final_answer
        )

        return final_answer

    # ============================================================
    # CLEAR MEMORY
    # ============================================================

    def clear_memory(self):

        self.memory.clear()