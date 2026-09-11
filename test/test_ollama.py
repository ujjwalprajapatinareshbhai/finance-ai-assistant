import ollama


client = ollama.Client(
    host="http://localhost:11434"
)


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "Get the latest stock price "
                "for a stock ticker."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string"
                    }
                },
                "required": ["ticker"]
            }
        }
    }
]


response = client.chat(

    model="llama3.2:1b",

    messages=[
        {
            "role": "user",
            "content": (
                "What is the current stock price "
                "of Apple? Use the stock tool."
            )
        }
    ],

    tools=tools
)


print(response)