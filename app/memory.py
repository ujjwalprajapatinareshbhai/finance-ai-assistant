from typing import List

from app.models import ChatMessage


class Memory:

    def __init__(self):

        self.messages: List[ChatMessage] = []


    def add_message(
        self,
        role: str,
        content: str
    ):

        self.messages.append(
            ChatMessage(
                role=role,
                content=content
            )
        )


    def get_messages(self):

        return [
            message.model_dump()
            for message in self.messages
        ]


    def clear(self):

        self.messages.clear()