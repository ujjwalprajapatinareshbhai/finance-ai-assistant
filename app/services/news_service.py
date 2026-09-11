from tavily import TavilyClient

from app.config import TAVILY_API_KEY
from app.models import NewsResult


class NewsService:

    def __init__(self):

        self.tavily = TavilyClient(
            api_key=TAVILY_API_KEY
        )


    def get_finance_news(
        self,
        topic: str
    ) -> NewsResult:

        try:

            response = self.tavily.search(
                query=f"{topic} finance news",
                max_results=5,
                include_answer=True
            )

            return NewsResult(
                success=True,
                message="News fetched successfully.",
                title=topic.title(),
                summary=response.get(
                    "answer",
                    ""
                ),
                source="Tavily"
            )


        except Exception as e:

            return NewsResult(
                success=False,
                message=str(e),
                title=topic.title(),
                summary="",
                source=None
            )