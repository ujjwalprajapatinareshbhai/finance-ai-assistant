import math

from app.models import CalculationResult


class CalculatorService:

    def calculate(
        self,
        expression: str
    ) -> CalculationResult:

        try:

            allowed = {
                "__builtins__": None,
                "abs": abs,
                "round": round,
                "pow": pow,
                "sqrt": math.sqrt
            }

            answer = eval(
                expression,
                allowed,
                {}
            )

            return CalculationResult(
                success=True,
                message="Calculation successful.",
                expression=expression,
                result=float(answer)
            )


        except Exception as e:

            return CalculationResult(
                success=False,
                message=str(e),
                expression=expression,
                result=None
            )