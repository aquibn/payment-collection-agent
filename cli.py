#!/usr/bin/env python3
"""
Interactive CLI to manually test the Payment Collection Agent.
Run: python cli.py
"""

import sys
import os

# Ensure package root is on path when running from any directory
sys.path.insert(0, os.path.dirname(__file__))

from agent import Agent


def run():
    print("=" * 60)
    print("  Payment Collection Agent — Interactive CLI")
    print("  Type 'quit' or 'exit' to end the session.")
    print("=" * 60)
    print()

    agent = Agent()

    # Kick off the conversation with a synthetic greeting
    response = agent.next("hi")
    print(f"Agent: {response['message']}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession interrupted. Goodbye!")
            break

        if user_input.lower() in ("quit", "exit"):
            print("Session ended by user. Goodbye!")
            break

        if not user_input:
            continue

        response = agent.next(user_input)
        print(f"\nAgent: {response['message']}\n")

        # Detect closed state
        if "session has been closed" in response["message"].lower() \
                or "have a great day" in response["message"].lower():
            print("[Session complete]")
            break


if __name__ == "__main__":
    run()
