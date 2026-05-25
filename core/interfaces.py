# core/interfaces.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import numpy as np


# ---------------------------------------------------------------------------
# Value objects (not ABCs — shared data contracts)
# ---------------------------------------------------------------------------


@dataclass
class GameState:
    board_array: np.ndarray
    current_player: int  # 0 or 1
    done: bool
    winner: int | None
    scores: tuple[int, int]  # (P0_seeds, P1_seeds)
    last_action: int | None  # pit index played, None on reset
    no_capture_count: int = 0  # counts consecutive non-capture moves for draw condition


@dataclass
class StepResult:
    state: GameState
    reward: float = 0.0  # reward from the perspective of the player action
    info: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# IBoard — geometry + state, no player logic
# ---------------------------------------------------------------------------


class IBoard(ABC):
    PITS_PER_SIDE: int = 6
    TOTAL_PITS: int = 12
    SEEDS_PER_PIT: int = 4  # initial seed count

    # ------------------------------------------------------------------
    # Static geometry — topology of the board, no state, no players
    # ------------------------------------------------------------------

    @staticmethod
    def pit_owner(pit: int) -> int:
        """Player who owns pit (0 = pits 0-5, 1 = pits 6-11)."""
        return 0 if pit < IBoard.PITS_PER_SIDE else 1

    @staticmethod
    def side_pits(player_id: int) -> range:
        """Absolute pit indices for player's side."""
        start = player_id * IBoard.PITS_PER_SIDE
        return range(start, start + IBoard.PITS_PER_SIDE)

    @staticmethod
    def opposite_pit(pit: int) -> int:
        """Mirror pit on the opponent's side (used in capture logic)."""
        return IBoard.TOTAL_PITS - 1 - pit

    @staticmethod
    def next_pit(pit: int, skip: int | None = None) -> int:
        """Next pit in anti-clockwise sowing order, optionally skipping one index."""
        nxt = (pit + 1) % IBoard.TOTAL_PITS
        if nxt == skip:
            nxt = (nxt + 1) % IBoard.TOTAL_PITS
        return nxt

    # ------------------------------------------------------------------
    # Abstract state — implemented by Board
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def holes(self) -> list[int]:
        """Seed counts for all 12 pits. Read-only view; mutate via sow()."""
        ...

    @property
    @abstractmethod
    def stores(self) -> list[int]:
        """Captured seed counts: [P0_store, P1_store]."""
        ...

    @abstractmethod
    def sow(self, pit: int) -> list[int]:
        """
        Empty pit and distribute seeds anti-clockwise.
        Returns ordered list of pit indices that were modified,
        so the GUI can animate each drop in sequence.
        Skips the origin pit when seed count > TOTAL_PITS (loop rule).
        Does NOT apply captures — that is IRules' job.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Restore initial position (SEEDS_PER_PIT in every hole)."""
        ...

    @abstractmethod
    def clone(self) -> "IBoard":
        """Deep copy — essential for MCTS / minimax without side effects."""
        ...

    @abstractmethod
    def to_array(self) -> np.ndarray:
        """
        Flat int array of length TOTAL_PITS + 2.
        Layout: [holes[0..11], stores[0], stores[1]]
        Used directly as the RL observation vector.
        """
        ...

    @abstractmethod
    def zero_pit(self, pit: int) -> int:
        """
        Empty pit and return the seeds that were there.
        Called by IRules.apply_captures — board primitive, not a rule.
        """
        ...

    @abstractmethod
    def add_to_store(self, player_id: int, seeds: int) -> None:
        """
        Move seeds into a player's store.
        Called by IRules.apply_captures and final_scores.
        """
        ...


# ---------------------------------------------------------------------------
# IRules — stateless validator and capture engine
# ---------------------------------------------------------------------------


class IRules(ABC):
    """
    Pure functions over board snapshots.
    Never holds mutable state. Never stores a board reference.
    All methods receive a board and return a result or a mutated clone.
    """

    @abstractmethod
    def valid_actions(self, board: IBoard, player_id: int) -> list[int]:
        """
        Legal pit indices for player_id.
        Filters out: empty pits, moves that would starve the opponent (affamer rule).
        Returns absolute pit indices.
        """
        ...

    @abstractmethod
    def would_starve(self, board: IBoard, pit: int, player_id: int) -> bool:
        """
        True if playing pit leaves the opponent with zero seeds on their side.
        Used by valid_actions; also exposed for rule explanations / GUI hints.
        Exception: if ALL moves starve, the player may play anyway
        (opponent then collects remaining seeds).
        """
        ...

    @abstractmethod
    def apply_captures(self, board: IBoard, last_pit: int, player_id: int) -> int:
        """
        Execute chain capture (rafle) starting from last_pit backwards.
        Captures if last_pit is on opponent's side and contains 2 or 3 seeds.
        Continues backwards as long as consecutive pits hold 2 or 3 seeds.
        Seeds move to the acting player's store; pits are zeroed.
        Returns total seeds captured this move.
        """
        ...

    @abstractmethod
    def is_terminal(self, board: IBoard) -> bool:
        """
        True when one side has no seeds (current player cannot move).
        Does NOT sweep remaining seeds — call final_scores() for that.
        """
        ...

    @abstractmethod
    def final_scores(self, board: IBoard) -> tuple[int, int]:
        """
        Called once is_terminal() is True.
        Sweeps all remaining seeds to the player who still has seeds,
        then returns (P0_total, P1_total).
        Does not mutate board — returns scores on a clone.
        """
        ...

    @abstractmethod
    def all_starve(self, board: IBoard, player_id: int) -> bool:
        """
        True if every legal pit for player_id would starve the opponent.
        When True, the no-starve constraint is lifted for this turn.
        """
        ...


# ---------------------------------------------------------------------------
# IPlayer — identity + policy only
# ---------------------------------------------------------------------------


class IPlayer(ABC):
    """
    Action-choosing agent. Knows its ID; knows nothing about board geometry.
    Receives a pre-built observation and action mask from IGame.
    """

    def __init__(self, player_id: int) -> None:
        assert player_id in (0, 1), "player_id must be 0 or 1"
        self.player_id = player_id

    @abstractmethod
    def choose_action(
        self,
        observation: dict[str, Any],
        action_mask: list[bool],  # True = legal; length always PITS_PER_SIDE
    ) -> int:
        """
        Return a pit index in [0, PITS_PER_SIDE).
        Index is LOCAL to the player's side (0 = leftmost pit from their view).
        IGame translates to absolute index before passing to IBoard.
        """
        ...

    def on_game_start(self, opponent_id: int) -> None:
        """Called once before the first move. Override for stateful agents."""
        pass

    def on_game_end(self, result: GameState) -> None:
        """Called once after terminal state. Override to update models / logs."""
        pass


# ---------------------------------------------------------------------------
# IGame — orchestrator; the only class that holds all three above
# ---------------------------------------------------------------------------


class IGame(ABC):
    """
    Coordinates IBoard, IRules, and IPlayer[].
    Single source of truth for turn order, action translation,
    reward calculation, and observation construction.
    """

    NO_CAPTURE_LIMIT: int = 50

    @abstractmethod
    def reset(self) -> GameState:
        """Start a new game. Returns the initial GameState."""
        ...

    @abstractmethod
    def step(self, action: int) -> StepResult:
        """
        Apply action (LOCAL pit index, 0-5) for the current player.
        Internally: translates to absolute index → sow → capture → check terminal.
        Reward is from the perspective of the player who just acted.
        Advances current_player on non-terminal states.
        """
        ...

    @abstractmethod
    def get_observation(self) -> dict[str, Any]:
        """
        Current player's view of the board. Always from their perspective:
          board[0:6]  = their own pits (local order)
          board[6:12] = opponent's pits
          stores      = [my_store, opponent_store]
          action_mask = bool array of length PITS_PER_SIDE
        This symmetry means an RL agent never needs to know its player_id.
        """
        ...

    @abstractmethod
    def get_valid_actions(self) -> list[int]:
        """Local pit indices (0-5) legal for the current player."""
        ...

    @abstractmethod
    def render(self, mode: str = "human") -> str | None:
        """
        mode='human'     → ASCII board string for CLI
        mode='rgb_array' → np.ndarray (H, W, 3) for video recording
        mode='silent'    → None (used during RL training)
        """
        ...

    # ------------------------------------------------------------------
    # Concrete helpers — same for all implementations
    # ------------------------------------------------------------------

    def local_to_absolute(self, local_pit: int, player_id: int) -> int:
        """Translate player-local index (0-5) to absolute board index."""
        return player_id * IBoard.PITS_PER_SIDE + local_pit

    def absolute_to_local(self, absolute_pit: int) -> int:
        """Strip side offset — always 0-5."""
        return absolute_pit % IBoard.PITS_PER_SIDE
