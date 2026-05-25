import pytest
from core.board import Board
from core.rules import Rules
from core.interfaces import IBoard


@pytest.fixture
def rules() -> Rules:
    return Rules()


@pytest.fixture
def board() -> Board:
    return Board()


def make_board(holes: list[int], stores: list[int] | None = None) -> Board:
    assert len(holes) == IBoard.TOTAL_PITS
    b = Board()
    b._holes = list(holes)
    b._stores = list(stores) if stores else [0, 0]
    return b
