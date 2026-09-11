import requests

from app.config import EXCHANGERATE_API_KEY
from app.models import ForexRate


class ForexService:

    BASE_URL = "https://v6.exchangerate-api.com/v6"


    def convert_currency(
        self,
        amount: float,
        from_currency: str,
        to_currency: str
    ) -> ForexRate:

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        try:

            url = (
                f"{self.BASE_URL}/"
                f"{EXCHANGERATE_API_KEY}/"
                f"pair/"
                f"{from_currency}/"
                f"{to_currency}/"
                f"{amount}"
            )

            response = requests.get(
                url,
                timeout=15
            )

            response.raise_for_status()

            data = response.json()


            if data.get("result") != "success":

                return ForexRate(
                    success=False,
                    message="Conversion failed.",
                    amount=amount,
                    from_currency=from_currency,
                    to_currency=to_currency,
                    converted_amount=None
                )


            return ForexRate(
                success=True,
                message="Conversion successful.",
                amount=amount,
                from_currency=from_currency,
                to_currency=to_currency,
                converted_amount=data.get(
                    "conversion_result"
                )
            )


        except Exception as e:

            return ForexRate(
                success=False,
                message=str(e),
                amount=amount,
                from_currency=from_currency,
                to_currency=to_currency,
                converted_amount=None
            )