import numpy as np
import pytest
from core.rules import Rules
from core.interfaces import IBoard


class MinimalBoard(IBoard):
    """Bare-minimum IBoard implementation — no Board internals whatsoever."""

    def __init__(self, holes: list[int], stores: list[int] | None = None) -> None:
        self._holes = list(holes)
        self._stores = list(stores) if stores else [0, 0]

    @property
    def holes(self) -> list[int]:
        return list(self._holes)

    @property
    def stores(self) -> list[int]:
        return list(self._stores)

    def sow(self, pit: int) -> list[int]:
        seeds = self._holes[pit]
        if seeds == 0:
            raise ValueError(f"Pit {pit} is empty.")
        self._holes[pit] = 0
        skip = pit if seeds >= self.TOTAL_PITS else None
        seq, current = [], pit
        for _ in range(seeds):
            current = self.next_pit(current, skip=skip)
            self._holes[current] += 1
            seq.append(current)
        return seq

    def reset(self) -> None:
        self._holes = [self.SEEDS_PER_PIT] * self.TOTAL_PITS
        self._stores = [0, 0]

    def clone(self) -> "MinimalBoard":
        return MinimalBoard(self._holes, self._stores)

    def to_array(self) -> np.ndarray:
        return np.array(self._holes + self._stores, dtype=np.int16)

    def zero_pit(self, pit: int) -> int:
        seeds = self._holes[pit]
        self._holes[pit] = 0
        return seeds

    def add_to_store(self, player_id: int, seeds: int) -> None:
        self._stores[player_id] += seeds

    def render_from(self, pov: int) -> str:
        return f"MinimalBoard(holes={self._holes}, stores={self._stores}, pov={pov})"


class TestRulesOnIBoard:
    def test_would_starve_works_on_non_board_iboard(self, rules: Rules) -> None:
        """Rules.would_starve must work on any IBoard, not just Board."""
        b = MinimalBoard([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        player_id = 0
        assert rules.would_starve(b, 0, player_id) is True

    def test_valid_actions_works_on_non_board_iboard(self, rules: Rules) -> None:
        b = MinimalBoard([4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4])
        player_id = 0
        assert rules.valid_actions(b, player_id) == list(IBoard.side_pits(player_id))

    def test_apply_captures_works_on_non_board_iboard(self, rules: Rules) -> None:
        b = MinimalBoard([4, 4, 4, 4, 4, 4, 2, 4, 4, 4, 4, 4])
        player_id = 0
        captured = rules.apply_captures(b, 6, player_id)
        assert captured == 2
        assert b.holes[6] == 0
        assert b.stores[player_id] == 2

    def test_move_causing_starvation_via_capture_is_blocked(self, rules: Rules) -> None:
        """
        A move is illegal if the resulting capture empties the opponent's side.
        would_starve must simulate sow + capture, not sow alone.
        """
        # P1 has pit6=1, pit7=2, pit8=2.
        # P0 sows pit5=1 → pit6 becomes 2 → rafle captures pit6+pit7+pit8 = 6 seeds.
        # P1 side empty after capture → move must be blocked.
        b = MinimalBoard([4, 4, 4, 4, 4, 1, 1, 2, 2, 0, 0, 0])
        player_id = 0
        assert rules.would_starve(b, 4, player_id) is True
        valid = rules.valid_actions(b, player_id)
        assert 4 not in valid

    def test_starvation_via_capture_allowed_when_no_other_move(
        self, rules: Rules
    ) -> None:
        """
        If every possible move would empty the opponent's side (via sow or capture),
        the no-starve constraint is lifted and all non-empty pits are legal.
        """
        # P0 has only pit5=1. P1 has only pit6=1, pit7=2, pit8=2.
        # P0's only move (pit5) causes a capture that empties P1 entirely.
        # Since there is no alternative, the move must be allowed.
        b = MinimalBoard([0, 0, 0, 0, 0, 2, 1, 1, 0, 0, 0, 0])
        player_id = 0
        assert rules.would_starve(b, 5, player_id) is True
        assert rules.all_starve(b, player_id) is True
        valid = rules.valid_actions(b, player_id)
        assert valid == [5]
