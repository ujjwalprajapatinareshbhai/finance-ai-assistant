import requests

from app.config import FINNHUB_API_KEY
from app.models import StockQuote


class StockService:

    BASE_URL = "https://finnhub.io/api/v1"


    def get_stock_price(
        self,
        ticker: str
    ) -> StockQuote:

        try:

            ticker = ticker.upper()

            # ------------------------------------------------
            # GET QUOTE
            # ------------------------------------------------

            quote_response = requests.get(
                f"{self.BASE_URL}/quote",
                params={
                    "symbol": ticker,
                    "token": FINNHUB_API_KEY
                },
                timeout=15
            )

            quote_response.raise_for_status()

            data = quote_response.json()


            # ------------------------------------------------
            # GET COMPANY PROFILE
            # ------------------------------------------------

            profile_response = requests.get(
                f"{self.BASE_URL}/stock/profile2",
                params={
                    "symbol": ticker,
                    "token": FINNHUB_API_KEY
                },
                timeout=15
            )

            profile_response.raise_for_status()

            profile = profile_response.json()


            # ------------------------------------------------
            # RETURN RESULT
            # ------------------------------------------------

            return StockQuote(
                success=True,
                message="Stock fetched successfully.",
                ticker=ticker,
                company=profile.get("name"),
                price_usd=data.get("c"),
                change_percent=data.get("dp")
            )

        except Exception as e:

            return StockQuote(
                success=False,
                message=str(e),
                ticker=ticker.upper(),
                company=None,
                price_usd=None,
                change_percent=None
            )