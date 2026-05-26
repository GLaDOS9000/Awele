from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.interfaces import IPlayer

if TYPE_CHECKING:
    from interfaces.gui.view import PygameView


class PygameHumanPlayer(IPlayer):
    """
    Human player for the Pygame GUI.

    Instead of blocking on stdin, this player uses a non-blocking queue:
    - The controller delivers clicks via receive_action(local_pit)
    - The game loop polls pop_action() each frame
    - choose_action() is never called in blocking mode for GUI players

    This keeps the event loop responsive — the game never hangs waiting
    for input while Pygame events pile up.
    """

    def __init__(self, player_id: int) -> None:
        super().__init__(player_id)
        self._pending_action: int | None = None
        self._view: PygameView | None = None

    def set_view(self, view: PygameView) -> None:
        """Inject view reference (called by controller after view is created)."""
        self._view = view

    def receive_action(self, local_pit: int) -> None:
        """Called by the controller when the player clicks a legal pit."""
        self._pending_action = local_pit

    def pop_action(self) -> int | None:
        """
        Return and clear the pending action, or None if no click yet.
        Called every frame by the controller event loop.
        """
        action = self._pending_action
        self._pending_action = None
        return action

    def choose_action(
        self,
        observation: dict[str, Any],
        action_mask: list[bool],
    ) -> int:
        """
        Not used in GUI mode — the controller uses receive_action / pop_action.
        Raises to catch accidental blocking calls.
        """
        raise RuntimeError(
            "PygameHumanPlayer.choose_action() should not be called directly. "
            "Use receive_action() / pop_action() via the controller."
        )
