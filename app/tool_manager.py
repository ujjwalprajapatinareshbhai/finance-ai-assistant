from app.services.stock_service import StockService
from app.services.crypto_service import CryptoService
from app.services.forex_service import ForexService
from app.services.calculator_service import CalculatorService
from app.services.news_service import NewsService
from app.services.datetime_service import DateTimeService


class ToolManager:

    def __init__(self):

        self.stock_service = StockService()

        self.crypto_service = CryptoService()

        self.forex_service = ForexService()

        self.calculator_service = CalculatorService()

        self.news_service = NewsService()

        self.datetime_service = DateTimeService()


    def execute_tool(
        self,
        tool_name: str,
        arguments: dict
    ):

        if tool_name == "get_stock_price":

            return self.stock_service.get_stock_price(
                arguments["ticker"]
            )


        elif tool_name == "get_crypto_price":

            return self.crypto_service.get_crypto_price(
                arguments["coin"]
            )


        elif tool_name == "convert_currency":

            return self.forex_service.convert_currency(
                arguments["amount"],
                arguments["from_currency"],
                arguments["to_currency"]
            )


        elif tool_name == "calculate":

            return self.calculator_service.calculate(
                arguments["expression"]
            )


        elif tool_name == "get_finance_news":

            return self.news_service.get_finance_news(
                arguments["topic"]
            )


        elif tool_name == "get_current_datetime":

            return self.datetime_service.get_current_datetime()


        else:

            raise ValueError(
                f"Unknown tool: {tool_name}"
            )