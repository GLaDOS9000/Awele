from __future__ import annotations

import numpy as np

from core.interfaces import IBoard


class Board(IBoard):
    """
    Concrete Awale board.

    Pit layout (absolute indices):
        Player 0 side  →  0  1  2  3  4  5   (left to right from P0's view)
        Player 1 side  →  11 10  9  8  7  6   (left to right from P1's view)

    Sowing is anti-clockwise, which maps to incrementing absolute index
    modulo TOTAL_PITS.

    Stores are NOT part of the holes array — they live in _stores[0] and _stores[1].
    Captured seeds go there via apply_captures() in Rules; sow() never touches stores.
    """

    def __init__(self) -> None:
        self._holes: list[int] = [self.SEEDS_PER_PIT] * self.TOTAL_PITS
        self._stores: list[int] = [0, 0]

    # ------------------------------------------------------------------
    # IBoard properties
    # ------------------------------------------------------------------

    @property
    def holes(self) -> list[int]:
        return list(self._holes)  # defensive copy — callers cannot mutate

    @property
    def stores(self) -> list[int]:
        return list(self._stores)  # defensive copy

    # ------------------------------------------------------------------
    # IBoard abstract methods
    # ------------------------------------------------------------------

    def sow(self, pit: int) -> list[int]:
        """
        Pick up all seeds from pit and distribute anti-clockwise.

        Loop rule: if seeds > TOTAL_PITS the origin pit is skipped on
        every pass (a seed is never re-deposited there).

        Returns the ordered sequence of pit indices that received a seed,
        so the GUI can animate each drop individually.
        The last element is the pit where the final seed landed —
        Rules uses it to decide whether to attempt a capture.
        """
        seeds = self._holes[pit]
        if seeds == 0:
            raise ValueError(f"Pit {pit} is empty — illegal sow.")

        self._holes[pit] = 0

        # When seeds >= TOTAL_PITS we loop: origin pit is always skipped.
        skip = pit if seeds >= self.TOTAL_PITS else None

        drop_sequence: list[int] = []
        current = pit

        for _ in range(seeds):
            current = self.next_pit(current, skip=skip)
            self._holes[current] += 1
            drop_sequence.append(current)

        return drop_sequence

    def reset(self) -> None:
        self._holes = [self.SEEDS_PER_PIT] * self.TOTAL_PITS
        self._stores = [0, 0]

    def clone(self) -> "Board":
        b = Board.__new__(Board)
        b._holes = list(self._holes)
        b._stores = list(self._stores)
        return b

    def to_array(self) -> np.ndarray:
        """
        Flat int16 array: [holes[0..11], stores[0], stores[1]] — length 14.
        int16 is sufficient (max seeds per cell < 50 in any realistic game).
        """
        return np.array(self._holes + self._stores, dtype=np.int16)

    # ------------------------------------------------------------------
    # Convenience — used by Rules and Game, not part of IBoard contract
    # ------------------------------------------------------------------

    def add_to_store(self, player_id: int, seeds: int) -> None:
        """Move seeds into a player's store (called by Rules.apply_captures)."""
        self._stores[player_id] += seeds

    def zero_pit(self, pit: int) -> int:
        """Empty a pit and return the seeds that were there."""
        seeds = self._holes[pit]
        self._holes[pit] = 0
        return seeds

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        p1 = self._holes[6:12][::-1]
        p0 = self._holes[0:6]

        store_w = max(2, len(str(max(self._stores))))
        pit_w = max(2, len(str(max(self._holes))))

        def fmt_store(v: int | None) -> str:
            return " " * store_w if v is None else str(v).rjust(store_w)

        def fmt_pit(v: int) -> str:
            return str(v).rjust(pit_w)

        def pit_row(pits: list) -> str:
            return "  ".join(fmt_pit(v) for v in pits)

        pad = 4
        inner_w = len(pit_row(p0))
        W = store_w + pad + inner_w + pad + store_w

        bar = "+" + "-" * W + "+"
        offset = " " * (store_w + pad)
        idx1 = "  ".join(str(i).rjust(pit_w) for i in [11, 10, 9, 8, 7, 6])
        idx0 = "  ".join(str(i).rjust(pit_w) for i in [0, 1, 2, 3, 4, 5])

        def board_row(store_l: int | None, pits: list, store_r: int | None) -> str:
            return f"|{fmt_store(store_l)}{' ' * pad}{pit_row(pits)}{' ' * pad}{fmt_store(store_r)}|"

        lines = [
            "  P1 (pits 6-11)",
            f" {offset}{idx1}",
            bar,
            board_row(self._stores[1], p1, None),
            "|" + "·" * W + "|",
            board_row(None, p0, self._stores[0]),
            bar,
            f"  {offset}{idx0}",
            "  P0 (pits 0-5)",
        ]
        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return NotImplemented
        return self._holes == other._holes and self._stores == other._stores


if __name__ == "__main__":
    b = Board()
    print("=== initial board ===")
    print(b)

    print("\n=== after sowing pit 0 ===")
    b.sow(0)
    print(b)

    print("\n=== after sowing pit 11 (wraps) ===")
    b.sow(11)
    print(b)

    print("\n=== after adding 6 seeds to P0 store ===")
    b.add_to_store(0, 6)
    print(b)
