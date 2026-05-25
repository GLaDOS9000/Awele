from __future__ import annotations

import random
from typing import Any

from core.interfaces import IPlayer


class RandomPlayer(IPlayer):
    """
    Picks a random legal action uniformly.
    Primary use: smoke-testing the game loop, RL baseline opponent.
    """

    def __init__(self, player_id: int, seed: int | None = None) -> None:
        super().__init__(player_id)
        self._rng = random.Random(seed)

    def choose_action(
        self,
        observation: dict[str, Any],
        action_mask: list[bool],
    ) -> int:
        legal = [i for i, legal in enumerate(action_mask) if legal]
        if not legal:
            raise ValueError(f"Player {self.player_id}: no legal actions available.")
        return self._rng.choice(legal)


class HumanPlayer(IPlayer):
    """
    Reads action from stdin.
    Prompt shows local indices (0-5) from the player's own perspective.
    """

    def choose_action(
        self,
        observation: dict[str, Any],
        action_mask: list[bool],
    ) -> int:
        print(observation["board_repr"])  # IGame passes the ASCII board
        legal = [i for i, legal in enumerate(action_mask) if legal]
        while True:
            try:
                raw = input(f"P{self.player_id} — choose pit {legal}: ")
                action = int(raw.strip())
                if action in legal:
                    return action
                print(f"  Illegal move. Legal pits: {legal}")
            except ValueError, EOFError:
                print(f"  Enter a number from {legal}.")
