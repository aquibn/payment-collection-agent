"""
Payment Collection AI Agent
Entry point: Agent class with next(user_input: str) -> dict interface
"""

from conversation_manager import ConversationManager


class Agent:
    """
    Production-ready Payment Collection AI Agent.

    Maintains all conversation state internally. Each call to next() represents
    one turn of the conversation.
    """

    def __init__(self):
        self._manager = ConversationManager()

    def next(self, user_input: str) -> dict:
        """
        Process one turn of the conversation.

        Args:
            user_input: The user's message as a plain string.

        Returns:
            {"message": str}  # The agent's response to display to the user
        """
        response = self._manager.process_turn(user_input.strip())
        return {"message": response}
