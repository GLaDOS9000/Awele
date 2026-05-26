from __future__ import annotations

from typing import Any

import numpy as np

from core.interfaces import IBoard, IGame, IPlayer, IRules, GameState, StepResult


class Awele(IGame):
    """
    Concrete Awele game orchestrator.

    Responsibilities:
        - Owns the single live IBoard instance
        - Translates local (0-5) ↔ absolute (0-11) pit indices
        - Sequences: sow → capture → terminal check → state snapshot
        - Builds observations always from the current player's perspective
        - Enforces turn order

    Does NOT own rule logic — delegates entirely to IRules.
    """

    NO_CAPTURE_LIMIT: int = 50

    def __init__(self, board: IBoard, rules: IRules, players: list[IPlayer]) -> None:
        assert len(players) == 2, "Awele requires exactly 2 players."
        assert players[0].player_id == 0 and players[1].player_id == 1
        self._board = board
        self._rules = rules
        self._players = players
        self._current_player: int = 0
        self._done: bool = False
        self._last_action: int | None = None
        self._no_capture_count: int = 0

    # ------------------------------------------------------------------
    # IGame — core interface
    # ------------------------------------------------------------------

    def reset(self) -> GameState:
        self._board.reset()
        self._current_player = 0
        self._done = False
        self._last_action = None
        self._no_capture_count = 0
        for i, player in enumerate(self._players):
            player.on_game_start(opponent_id=1 - i)
        return self._make_state()

    def step(self, action: int) -> StepResult:
        """
        action: LOCAL pit index (0-5) from the current player's perspective.
        """
        if self._done:
            raise RuntimeError("Game is over — call reset() before stepping.")

        player_id = self._current_player
        absolute = self._local_to_absolute(action, player_id)

        valid_abs = self._rules.valid_actions(self._board, player_id)
        if absolute not in valid_abs:
            raise ValueError(
                f"Illegal action {action} (absolute {absolute}) "
                f"for player {player_id}. "
                f"Legal: {[self._absolute_to_local(p) for p in valid_abs]}"
            )

        # Sow
        seq = self._board.sow(absolute)
        last_pit = seq[-1]

        # Capture
        captured = self._rules.apply_captures(self._board, last_pit, player_id)

        # No-capture counter
        if captured > 0:
            self._no_capture_count = 0
        else:
            self._no_capture_count += 1

        # Terminal check — evaluated from next player's perspective
        next_player = 1 - player_id
        done = (
            self._rules.is_terminal(self._board, next_player)
            or self._no_capture_count >= self.NO_CAPTURE_LIMIT
        )
        winner = None

        if done:
            self._done = True
            # Sweep remaining seeds — each player keeps their own side
            for pid in (0, 1):
                for p in IBoard.side_pits(pid):
                    seeds = self._board.zero_pit(p)
                    if seeds:
                        self._board.add_to_store(pid, seeds)
            p0, p1 = self._board.stores[0], self._board.stores[1]
            if p0 > p1:
                winner = 0
            elif p1 > p0:
                winner = 1
            terminal_state = self._make_state(winner=winner, done=True)
            for player in self._players:
                player.on_game_end(terminal_state)
        else:
            # Advance turn — but if next player has no seeds and CAN be fed,
            # keep current player to feed them next move
            next_valid = self._rules.valid_actions(self._board, next_player)
            if next_valid:
                self._current_player = next_player
            else:
                # next player has no seeds but can be fed — current player plays again
                self._current_player = player_id

        self._last_action = action
        return StepResult(state=self._make_state(winner=winner, done=done))

    def get_observation(self) -> dict[str, Any]:
        player_id = self._current_player
        opponent_id = 1 - player_id

        my_pits = [self._board.holes[p] for p in IBoard.side_pits(player_id)]
        opp_pits = [self._board.holes[p] for p in IBoard.side_pits(opponent_id)]

        valid_abs = self._rules.valid_actions(self._board, player_id)
        action_mask = [
            self._local_to_absolute(i, player_id) in valid_abs
            for i in range(IBoard.PITS_PER_SIDE)
        ]

        return {
            "board": np.array(my_pits + opp_pits, dtype=np.int16),
            "stores": np.array(
                [self._board.stores[player_id], self._board.stores[opponent_id]],
                dtype=np.int16,
            ),
            "action_mask": action_mask,
            "current_player": player_id,
            "board_repr": repr(self._board),
            "no_capture_count": self._no_capture_count,
            "done": self._done,
        }

    def get_valid_actions(self) -> list[int]:
        abs_actions = self._rules.valid_actions(self._board, self._current_player)
        return [self._absolute_to_local(p) for p in abs_actions]

    def preview_action(self, local_action: int) -> np.ndarray | None:
        """
        Clone the board, apply local_action (sow + capture), and return
        the resulting state as a player-relative array — same layout as
        get_observation(): [my_pits(6), opp_pits(6), my_store, opp_store].
        Returns None if local_action is illegal.
        """
        player_id = self._current_player
        absolute = self._local_to_absolute(local_action, player_id)
        if absolute not in self._rules.valid_actions(self._board, player_id):
            return None
        clone = self._board.clone()
        seq = clone.sow(absolute)
        self._rules.apply_captures(clone, seq[-1], player_id)
        opponent = 1 - player_id
        my_pits = [clone.holes[p] for p in IBoard.side_pits(player_id)]
        opp_pits = [clone.holes[p] for p in IBoard.side_pits(opponent)]
        stores = [clone.stores[player_id], clone.stores[opponent]]
        return np.array(my_pits + opp_pits + stores, dtype=np.int16)

    def render(self, pov: int | None = None, mode: str = "human") -> str | None:
        player_view = pov if pov is not None else self._current_player
        board_str = self._board.render_from(player_view)
        if mode == "human":
            print(board_str)
            return None
        if mode == "silent":
            return None
        if mode == "rgb_array":
            raise NotImplementedError("rgb_array rendering not yet implemented.")
        return board_str

    @property
    def done(self) -> bool:
        return self._done

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _local_to_absolute(self, local_pit: int, player_id: int) -> int:
        return player_id * IBoard.PITS_PER_SIDE + local_pit

    def _absolute_to_local(self, absolute_pit: int) -> int:
        return absolute_pit % IBoard.PITS_PER_SIDE

    def _make_state(
        self,
        winner: int | None = None,
        done: bool | None = None,
    ) -> GameState:
        return GameState(
            board_array=self._board.to_array(),
            current_player=self._current_player,
            done=done if done is not None else self._done,
            winner=winner,
            scores=(self._board.stores[0], self._board.stores[1]),
            last_action=self._last_action,
            no_capture_count=self._no_capture_count,
        )
