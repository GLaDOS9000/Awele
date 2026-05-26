from __future__ import annotations

import random
from typing import Any

from core.interfaces import IPlayer, IBoard


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
        player_id = observation["current_player"]
        legal = [i for i, ok in enumerate(action_mask) if ok]
        mapping = {local: player_id * IBoard.PITS_PER_SIDE + local for local in legal}
        hints = "  ".join(f"pit{ab}→{loc}" for loc, ab in mapping.items())
        if player_id == 1:
            print(f"  hints: {hints}\n")

        while True:
            raw = input(f"  P{player_id} — choose local pit {legal}: ").strip()
            if not raw:
                continue
            try:
                action = int(raw)
                if action in legal:
                    return action
                print(f"  Illegal move. Legal pits: {legal}")
            except ValueError:
                print(f"  Enter a number from {legal}.")
