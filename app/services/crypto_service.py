import difflib
import re
from typing import Any, Optional

import requests

from app.models import CryptoPrice


class CryptoService:

    BASE_URL = "https://api.coingecko.com/api/v3"

    SEARCH_TIMEOUT = 15
    PRICE_TIMEOUT = 15

    # ============================================================
    # NORMALIZE TEXT
    # ============================================================

    @staticmethod
    def _normalize(value: Any) -> str:
        """
        Normalize text for generic cryptocurrency matching.

        No hard-coded cryptocurrency names, symbols, or aliases
        are used.
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
    # STRING SIMILARITY
    # ============================================================

    @classmethod
    def _similarity(
        cls,
        first: str,
        second: str
    ) -> float:

        first = cls._normalize(first)
        second = cls._normalize(second)

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
    # SEARCH COINGECKO
    # ============================================================

    def _search_coin(
        self,
        coin: str
    ) -> Optional[dict]:
        """
        Dynamically resolve a cryptocurrency using CoinGecko.

        The search can match against:
        - CoinGecko ID
        - symbol
        - name

        No cryptocurrency list is hard-coded.
        """

        try:

            response = requests.get(
                f"{self.BASE_URL}/search",
                params={
                    "query": coin.strip()
                },
                timeout=self.SEARCH_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            coins = data.get("coins", [])

            if not isinstance(coins, list):
                return None

            if not coins:
                return None

            requested = self._normalize(coin)

            # ====================================================
            # 1. EXACT MATCH
            # ====================================================

            exact_matches = []

            for item in coins:

                coin_id = item.get("id", "")
                symbol = item.get("symbol", "")
                name = item.get("name", "")

                candidates = [
                    coin_id,
                    symbol,
                    name
                ]

                for candidate in candidates:

                    if (
                        self._normalize(candidate)
                        == requested
                    ):
                        exact_matches.append(item)
                        break

            if exact_matches:

                return exact_matches[0]

            # ====================================================
            # 2. GENERIC SIMILARITY MATCH
            # ====================================================

            scored_results = []

            for item in coins:

                coin_id = item.get("id", "")
                symbol = item.get("symbol", "")
                name = item.get("name", "")

                id_score = self._similarity(
                    coin,
                    coin_id
                )

                symbol_score = self._similarity(
                    coin,
                    symbol
                )

                name_score = self._similarity(
                    coin,
                    name
                )

                best_score = max(
                    id_score,
                    symbol_score,
                    name_score
                )

                scored_results.append(
                    (
                        best_score,
                        item
                    )
                )

            scored_results.sort(
                key=lambda item: item[0],
                reverse=True
            )

            if not scored_results:
                return None

            best_score, best_item = (
                scored_results[0]
            )

            # Avoid accepting an unrelated cryptocurrency.
            if best_score < 0.65:
                return None

            return best_item

        except requests.RequestException:
            return None

        except Exception:
            return None

    # ============================================================
    # GET CRYPTO PRICE
    # ============================================================

    def get_crypto_price(
        self,
        coin: str
    ) -> CryptoPrice:

        original_coin = str(
            coin
        ).strip()

        # ========================================================
        # EMPTY INPUT
        # ========================================================

        if not original_coin:

            return CryptoPrice(
                success=False,
                message=(
                    "A cryptocurrency name or symbol "
                    "is required."
                ),
                coin="",
                price_usd=None,
                resolved_coin_id=None,
                resolved_symbol=None,
                resolved_name=None
            )

        try:

            # ====================================================
            # RESOLVE CRYPTOCURRENCY
            # ====================================================

            resolved = self._search_coin(
                original_coin
            )

            if not resolved:

                return CryptoPrice(
                    success=False,
                    message=(
                        f"Could not resolve cryptocurrency "
                        f"'{original_coin}'."
                    ),
                    coin=original_coin,
                    price_usd=None,
                    resolved_coin_id=None,
                    resolved_symbol=None,
                    resolved_name=None
                )

            # ====================================================
            # CANONICAL COINGECKO DATA
            # ====================================================

            coin_id = resolved.get("id")
            symbol = resolved.get("symbol")
            name = resolved.get("name")

            if not coin_id or not name:

                return CryptoPrice(
                    success=False,
                    message=(
                        "CoinGecko returned an incomplete "
                        "cryptocurrency result."
                    ),
                    coin=original_coin,
                    price_usd=None,
                    resolved_coin_id=coin_id,
                    resolved_symbol=symbol,
                    resolved_name=name
                )

            # ====================================================
            # GET CURRENT PRICE
            # ====================================================

            response = requests.get(
                f"{self.BASE_URL}/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd"
                },
                timeout=self.PRICE_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            coin_data = data.get(
                coin_id
            )

            if not isinstance(
                coin_data,
                dict
            ):

                return CryptoPrice(
                    success=False,
                    message=(
                        f"No current price was returned "
                        f"for '{name}'."
                    ),
                    coin=original_coin,
                    price_usd=None,
                    resolved_coin_id=coin_id,
                    resolved_symbol=symbol,
                    resolved_name=name
                )

            price = coin_data.get(
                "usd"
            )

            # ====================================================
            # VALIDATE PRICE
            # ====================================================

            if not isinstance(
                price,
                (int, float)
            ):

                return CryptoPrice(
                    success=False,
                    message=(
                        f"Invalid price returned for "
                        f"'{name}'."
                    ),
                    coin=original_coin,
                    price_usd=None,
                    resolved_coin_id=coin_id,
                    resolved_symbol=symbol,
                    resolved_name=name
                )

            if price <= 0:

                return CryptoPrice(
                    success=False,
                    message=(
                        f"Invalid non-positive price "
                        f"returned for '{name}'."
                    ),
                    coin=original_coin,
                    price_usd=None,
                    resolved_coin_id=coin_id,
                    resolved_symbol=symbol,
                    resolved_name=name
                )

            # ====================================================
            # SUCCESS
            # ====================================================

            return CryptoPrice(
                success=True,
                message=(
                    "Crypto price fetched successfully."
                ),
                coin=original_coin,
                price_usd=float(price),
                resolved_coin_id=coin_id,
                resolved_symbol=symbol,
                resolved_name=name
            )

        except requests.RequestException as e:

            return CryptoPrice(
                success=False,
                message=(
                    f"Crypto provider request failed: {e}"
                ),
                coin=original_coin,
                price_usd=None,
                resolved_coin_id=None,
                resolved_symbol=None,
                resolved_name=None
            )

        except Exception as e:

            return CryptoPrice(
                success=False,
                message=str(e),
                coin=original_coin,
                price_usd=None,
                resolved_coin_id=None,
                resolved_symbol=None,
                resolved_name=None
            )