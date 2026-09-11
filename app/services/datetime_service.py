from datetime import datetime

from app.models import DateTimeResponse


class DateTimeService:

    def get_current_datetime(
        self
    ) -> DateTimeResponse:

        now = datetime.now()

        return DateTimeResponse(
            success=True,
            message=(
                "Current date and time "
                "fetched successfully."
            ),
            date=now.strftime("%Y-%m-%d"),
            day=now.strftime("%A"),
            time=now.strftime("%I:%M:%S %p")
        )