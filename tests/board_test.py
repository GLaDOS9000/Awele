# tests/test_board.py
import numpy as np
import pytest

from core.board import Board
from core.interfaces import IBoard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def board() -> Board:
    return Board()


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_holes_count(self, board: Board) -> None:
        assert len(board.holes) == IBoard.TOTAL_PITS

    def test_seeds_per_pit(self, board: Board) -> None:
        assert all(s == IBoard.SEEDS_PER_PIT for s in board.holes)

    def test_stores_empty(self, board: Board) -> None:
        assert board.stores == [0, 0]

    def test_total_seeds(self, board: Board) -> None:
        total = sum(board.holes) + sum(board.stores)
        assert total == IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT


# ---------------------------------------------------------------------------
# Static geometry
# ---------------------------------------------------------------------------


class TestGeometry:
    def test_pit_owner_p0(self) -> None:
        for pit in range(6):
            assert IBoard.pit_owner(pit) == 0

    def test_pit_owner_p1(self) -> None:
        for pit in range(6, 12):
            assert IBoard.pit_owner(pit) == 1

    def test_side_pits_p0(self) -> None:
        assert list(IBoard.side_pits(0)) == list(range(6))

    def test_side_pits_p1(self) -> None:
        assert list(IBoard.side_pits(1)) == list(range(6, 12))

    def test_opposite_pit(self) -> None:
        assert IBoard.opposite_pit(0) == 11
        assert IBoard.opposite_pit(5) == 6
        assert IBoard.opposite_pit(6) == 5
        assert IBoard.opposite_pit(11) == 0

    def test_opposite_pit_is_symmetric(self) -> None:
        for pit in range(12):
            assert IBoard.opposite_pit(IBoard.opposite_pit(pit)) == pit

    def test_next_pit_wraps(self) -> None:
        assert IBoard.next_pit(11) == 0

    def test_next_pit_skip(self) -> None:
        # skip=2: next after 1 should be 3, not 2
        assert IBoard.next_pit(1, skip=2) == 3

    def test_next_pit_skip_on_wrap(self) -> None:
        # skip=0: next after 11 should be 1, not 0
        assert IBoard.next_pit(11, skip=0) == 1


# ---------------------------------------------------------------------------
# Normal sow (seeds <= 12)
# ---------------------------------------------------------------------------


class TestSow:
    def test_origin_pit_emptied(self, board: Board) -> None:
        board.sow(0)
        assert board.holes[0] == 0

    def test_seeds_distributed(self, board: Board) -> None:
        # Pit 0 has 4 seeds → pits 1,2,3,4 each gain 1
        board.sow(0)
        for pit in [1, 2, 3, 4]:
            assert board.holes[pit] == IBoard.SEEDS_PER_PIT + 1

    def test_pits_beyond_last_drop_unchanged(self, board: Board) -> None:
        board.sow(0)
        for pit in [5, 6, 7, 8, 9, 10, 11]:
            assert board.holes[pit] == IBoard.SEEDS_PER_PIT

    def test_drop_sequence_length(self, board: Board) -> None:
        seq = board.sow(0)
        assert len(seq) == IBoard.SEEDS_PER_PIT  # 4 seeds → 4 drops

    def test_drop_sequence_order(self, board: Board) -> None:
        seq = board.sow(0)
        assert seq == [1, 2, 3, 4]

    def test_last_pit_in_sequence(self, board: Board) -> None:
        seq = board.sow(0)
        assert seq[-1] == 4

    def test_total_seeds_conserved(self, board: Board) -> None:
        before = sum(board.holes)
        board.sow(3)
        assert sum(board.holes) == before

    def test_sow_wraps_around(self, board: Board) -> None:
        # Pit 10 has 4 seeds: next pits are 11, 0, 1, 2
        seq = board.sow(10)
        assert seq == [11, 0, 1, 2]
        assert board.holes[10] == 0
        for pit in [11, 0, 1, 2]:
            assert board.holes[pit] == IBoard.SEEDS_PER_PIT + 1

    def test_sow_empty_pit_raises(self, board: Board) -> None:
        board.sow(0)  # empty pit 0
        with pytest.raises(ValueError):
            board.sow(0)

    def test_sow_p1_side(self, board: Board) -> None:
        seq = board.sow(6)
        assert seq == [7, 8, 9, 10]
        assert board.holes[6] == 0


# ---------------------------------------------------------------------------
# Loop rule: seeds > TOTAL_PITS (> 12)
# ---------------------------------------------------------------------------


class TestLoopSow:
    def _make_board_with(self, pit: int, seeds: int) -> Board:
        """Set one pit to a specific seed count for loop testing."""
        b = Board()
        b._holes = [0] * IBoard.TOTAL_PITS
        b._holes[pit] = seeds
        return b

    def test_origin_pit_skipped_in_loop(self) -> None:
        # Pit 0 with 13 seeds: visits 1..11 then skips 0, continues to 1
        b = self._make_board_with(0, 13)
        seq = b.sow(0)
        assert 0 not in seq  # origin never receives a seed
        assert len(seq) == 13

    def test_origin_pit_stays_zero_after_loop(self) -> None:
        b = self._make_board_with(0, 13)
        b.sow(0)
        assert b.holes[0] == 0

    def test_each_other_pit_gets_one_seed_with_13(self) -> None:
        # seq: 1,2,3,4,5,6,7,8,9,10,11, (skip 0), 1, 2
        b = self._make_board_with(0, 13)
        b.sow(0)
        assert b.holes[0] == 0
        assert b.holes[1] == 2
        assert b.holes[2] == 2
        for pit in range(3, 12):
            assert b.holes[pit] == 1

    def test_exactly_12_seeds_no_skip(self) -> None:
        # 12 seeds exactly: no loop, origin pit is NOT skippeds
        # Pit 0 with 12 seeds → pits 1..11 get 1 each, pit 0 stays 0
        b = self._make_board_with(0, 12)
        seq = b.sow(0)
        assert len(seq) == 12
        assert 0 not in seq  # origin not revisited (12 ≤ 12, no loop)

    def test_large_loop_seed_conservation(self) -> None:
        b = self._make_board_with(3, 25)
        total_before = sum(b._holes)
        b.sow(3)
        assert sum(b._holes) == total_before


# ---------------------------------------------------------------------------
# reset / clone / to_array
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_restores_holes(self, board: Board) -> None:
        board.sow(0)
        board.reset()
        assert board.holes == [IBoard.SEEDS_PER_PIT] * IBoard.TOTAL_PITS

    def test_reset_clears_stores(self, board: Board) -> None:
        board.add_to_store(0, 10)
        board.reset()
        assert board.stores == [0, 0]


class TestClone:
    def test_clone_equal(self, board: Board) -> None:
        assert board.clone() == board

    def test_clone_is_independent(self, board: Board) -> None:
        clone = board.clone()
        board.sow(0)
        assert clone != board

    def test_clone_stores_independent(self, board: Board) -> None:
        clone = board.clone()
        board.add_to_store(0, 5)
        assert clone.stores[0] == 0

    def test_clone_of_clone(self, board: Board) -> None:
        board.sow(2)
        c1 = board.clone()
        c2 = c1.clone()
        assert c1 == c2


class TestToArray:
    def test_shape(self, board: Board) -> None:
        arr = board.to_array()
        assert arr.shape == (IBoard.TOTAL_PITS + 2,)

    def test_dtype(self, board: Board) -> None:
        assert board.to_array().dtype == np.int16

    def test_initial_values(self, board: Board) -> None:
        arr = board.to_array()
        np.testing.assert_array_equal(arr[:12], [4] * 12)
        np.testing.assert_array_equal(arr[12:], [0, 0])

    def test_reflects_sow(self, board: Board) -> None:
        board.sow(0)
        arr = board.to_array()
        assert arr[0] == 0
        assert arr[1] == IBoard.SEEDS_PER_PIT + 1

    def test_reflects_store(self, board: Board) -> None:
        board.add_to_store(1, 7)
        arr = board.to_array()
        assert arr[13] == 7


# ---------------------------------------------------------------------------
# Convenience methods
# ---------------------------------------------------------------------------


class TestConvenience:
    def test_add_to_store(self, board: Board) -> None:
        board.add_to_store(0, 6)
        assert board.stores[0] == 6
        assert board.stores[1] == 0

    def test_zero_pit_returns_seeds(self, board: Board) -> None:
        seeds = board.zero_pit(3)
        assert seeds == IBoard.SEEDS_PER_PIT
        assert board.holes[3] == 0

    def test_zero_pit_already_empty(self, board: Board) -> None:
        board.zero_pit(0)
        seeds = board.zero_pit(0)
        assert seeds == 0


# ---------------------------------------------------------------------------
# Seed conservation — invariant across any sequence of operations
# ---------------------------------------------------------------------------


class TestSeedConservation:
    def test_conservation_after_multiple_sows(self, board: Board) -> None:
        total = IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT
        board.sow(0)
        board.sow(5)
        board.sow(9)
        assert sum(board.holes) + sum(board.stores) == total

    def test_conservation_after_store_add(self, board: Board) -> None:
        total = IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT
        seeds = board.zero_pit(2)
        board.add_to_store(0, seeds)
        assert sum(board.holes) + sum(board.stores) == total
