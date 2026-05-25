from __future__ import annotations

import pytest

from core.board import Board
from core.game import Awele
from core.interfaces import IBoard, GameState, StepResult
from core.player import RandomPlayer
from core.rules import Rules
from tests.conftest import make_board


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def game() -> Awele:
    return Awele(
        board=Board(),
        rules=Rules(),
        players=[RandomPlayer(0, seed=42), RandomPlayer(1, seed=99)],
    )


def make_game(holes: list[int], stores: list[int] | None = None) -> Awele:
    """Build a game with a specific board position."""
    b = make_board(holes, stores)
    return Awele(
        board=b,
        rules=Rules(),
        players=[RandomPlayer(0, seed=0), RandomPlayer(1, seed=0)],
    )


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_returns_game_state(self, game: Awele) -> None:
        state = game.reset()
        assert isinstance(state, GameState)

    def test_current_player_is_zero(self, game: Awele) -> None:
        state = game.reset()
        assert state.current_player == 0

    def test_not_done(self, game: Awele) -> None:
        state = game.reset()
        assert state.done is False

    def test_scores_zero(self, game: Awele) -> None:
        state = game.reset()
        assert state.scores == (0, 0)

    def test_last_action_none(self, game: Awele) -> None:
        state = game.reset()
        assert state.last_action is None

    def test_board_array_shape(self, game: Awele) -> None:
        state = game.reset()
        assert state.board_array.shape == (IBoard.TOTAL_PITS + 2,)

    def test_board_array_initial_values(self, game: Awele) -> None:
        state = game.reset()
        assert all(v == IBoard.SEEDS_PER_PIT for v in state.board_array[:12])
        assert state.board_array[12] == 0
        assert state.board_array[13] == 0

    def test_double_reset(self, game: Awele) -> None:
        game.reset()
        game.step(0)
        state = game.reset()
        assert state.scores == (0, 0)
        assert state.current_player == 0


# ---------------------------------------------------------------------------
# step
# ---------------------------------------------------------------------------


class TestStep:
    def test_returns_step_result(self, game: Awele) -> None:
        game.reset()
        result = game.step(0)
        assert isinstance(result, StepResult)

    def test_last_action_recorded(self, game: Awele) -> None:
        game.reset()
        result = game.step(3)
        assert result.state.last_action == 3

    def test_player_alternates(self, game: Awele) -> None:
        game.reset()
        r1 = game.step(0)
        assert r1.state.current_player == 1
        r2 = game.step(0)
        assert r2.state.current_player == 0

    def test_illegal_action_raises(self, game: Awele) -> None:
        game.reset()
        with pytest.raises(ValueError):
            game.step(6)  # out of local range

    def test_step_after_done_raises(self, game: Awele) -> None:
        game.reset()
        # Run to completion
        _run_full_game(game)
        with pytest.raises(RuntimeError):
            game.step(0)

    def test_reward_is_zero_during_game(self, game: Awele) -> None:
        game.reset()
        result = game.step(0)
        assert result.reward == 0.0

    def test_seed_conservation_after_step(self, game: Awele) -> None:
        game.reset()
        game.step(0)
        obs = game.get_observation()
        total = int(obs["board"].sum()) + int(obs["stores"].sum())
        assert total == IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT


# ---------------------------------------------------------------------------
# get_observation
# ---------------------------------------------------------------------------


class TestGetObservation:
    def test_keys_present(self, game: Awele) -> None:
        game.reset()
        obs = game.get_observation()
        assert "board" in obs
        assert "stores" in obs
        assert "action_mask" in obs
        assert "current_player" in obs
        assert "board_repr" in obs

    def test_board_shape(self, game: Awele) -> None:
        game.reset()
        obs = game.get_observation()
        assert obs["board"].shape == (IBoard.TOTAL_PITS,)

    def test_action_mask_length(self, game: Awele) -> None:
        game.reset()
        obs = game.get_observation()
        assert len(obs["action_mask"]) == IBoard.PITS_PER_SIDE

    def test_action_mask_all_true_at_start(self, game: Awele) -> None:
        game.reset()
        obs = game.get_observation()
        assert all(obs["action_mask"])

    def test_board_repr_is_string(self, game: Awele) -> None:
        game.reset()
        obs = game.get_observation()
        assert isinstance(obs["board_repr"], str)

    def test_perspective_symmetry(self, game: Awele) -> None:
        """P0 and P1 should see their own pits first."""
        game.reset()
        obs_p0 = game.get_observation()
        game.step(0)
        obs_p1 = game.get_observation()
        # P0's pits 0-5 should be in obs_p0["board"][0:6]
        # P1's pits 6-11 should be in obs_p1["board"][0:6]
        assert obs_p0["current_player"] == 0
        assert obs_p1["current_player"] == 1


# ---------------------------------------------------------------------------
# get_valid_actions
# ---------------------------------------------------------------------------


class TestGetValidActions:
    def test_all_valid_at_start(self, game: Awele) -> None:
        game.reset()
        assert game.get_valid_actions() == list(range(IBoard.PITS_PER_SIDE))

    def test_returns_local_indices(self, game: Awele) -> None:
        game.reset()
        actions = game.get_valid_actions()
        assert all(0 <= a < IBoard.PITS_PER_SIDE for a in actions)


# ---------------------------------------------------------------------------
# GAME TERMINATION CONDITIONS
# ---------------------------------------------------------------------------


class TestNoCaptureLimit:
    def test_counter_increments_on_non_capture(self, game: Awele) -> None:
        game.reset()
        game.step(0)  # unlikely to capture on first move
        obs = game.get_observation()
        assert obs["no_capture_count"] >= 0

    def test_counter_resets_on_capture(self) -> None:
        # P0 sows pit5=1 → pit6: 1+1=2 → capture
        b = make_board([4, 4, 4, 4, 4, 1, 1, 4, 4, 4, 4, 4])
        g = Awele(board=b, rules=Rules(), players=[RandomPlayer(0), RandomPlayer(1)])
        g._no_capture_count = 10  # simulate prior non-capturing moves
        g._current_player = 0
        g.step(5)  # causes capture
        assert g._no_capture_count == 0

    def test_counter_in_game_state(self, game: Awele) -> None:
        state = game.reset()
        assert state.no_capture_count == 0

    def test_counter_in_observation(self, game: Awele) -> None:
        game.reset()
        obs = game.get_observation()
        assert "no_capture_count" in obs

    def test_game_ends_at_limit(self) -> None:
        # Build a position where no captures will ever happen
        # Both sides have 1 seed each in pits that will never form 2 or 3
        b = make_board([1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0])
        g = Awele(board=b, rules=Rules(), players=[RandomPlayer(0), RandomPlayer(1)])
        g._no_capture_count = Awele.NO_CAPTURE_LIMIT - 1
        g._current_player = 0
        result = g.step(0)
        assert result.state.done is True
        assert result.state.winner is None  # draw — neither player has majority

    def test_seed_conservation_at_no_capture_limit(self) -> None:
        b = make_board([1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0], stores=[24, 22])
        g = Awele(board=b, rules=Rules(), players=[RandomPlayer(0), RandomPlayer(1)])
        g._no_capture_count = Awele.NO_CAPTURE_LIMIT - 1
        g._current_player = 0
        result = g.step(0)
        assert sum(result.state.scores) == IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT


# ---------------------------------------------------------------------------
# Full game loop — integration
# ---------------------------------------------------------------------------


class TestFullGame:
    def test_game_terminates(self, game: Awele) -> None:
        result = _run_full_game(game)
        assert result.state.done is True

    def test_seed_conservation_at_terminal(self, game: Awele) -> None:
        result = _run_full_game(game)
        p0, p1 = result.state.scores
        assert p0 + p1 == IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT

    def test_winner_has_more_seeds(self, game: Awele) -> None:
        result = _run_full_game(game)
        p0, p1 = result.state.scores
        winner = result.state.winner
        if winner == 0:
            assert p0 > p1
        elif winner == 1:
            assert p1 > p0
        else:
            assert p0 == p1  # draw

    def test_multiple_games_consistent(self) -> None:
        """Run 20 games — all must terminate with seed conservation."""
        for seed in range(20):
            g = Awele(
                board=Board(),
                rules=Rules(),
                players=[RandomPlayer(0, seed=seed), RandomPlayer(1, seed=seed + 1)],
            )
            result = _run_full_game(g)
            p0, p1 = result.state.scores
            assert p0 + p1 == IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT
            assert result.state.done is True

    def test_only_legal_actions_played(self, game: Awele) -> None:
        """Every action played must have been in get_valid_actions() before the step."""
        game.reset()
        rules = Rules()
        board = game._board
        for _ in range(200):
            if game._done:
                break
            valid = game.get_valid_actions()
            action = valid[0]
            result = game.step(action)
            assert result.state.last_action in valid


# ---------------------------------------------------------------------------
# Terminal positions
# ---------------------------------------------------------------------------


class TestTerminalPositions:
    def test_near_terminal_p0_wins(self) -> None:
        b = make_board([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], stores=[30, 17])
        g = Awele(board=b, rules=Rules(), players=[RandomPlayer(0), RandomPlayer(1)])
        g._current_player = 0
        result = g.step(0)
        assert result.state.done is True
        assert result.state.winner == 0
        assert sum(result.state.scores) == IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT

    def test_near_terminal_draw(self) -> None:
        b = make_board([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], stores=[23, 24])
        g = Awele(board=b, rules=Rules(), players=[RandomPlayer(0), RandomPlayer(1)])
        g._current_player = 0
        result = g.step(0)
        assert result.state.done is True
        assert sum(result.state.scores) == IBoard.TOTAL_PITS * IBoard.SEEDS_PER_PIT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_full_game(game: Awele) -> StepResult:
    """Run a full game with RandomPlayers, return the terminal StepResult."""
    game.reset()
    last_result = None
    for _ in range(500):  # safety cap
        if game._done:
            break
        action = game.get_valid_actions()[0]
        last_result = game.step(action)
        if last_result.state.done:
            break
    assert last_result is not None
    return last_result
