from __future__ import annotations

from core.interfaces import IBoard, IRules


class Rules(IRules):
    """
    Stateless rule engine for Awele.

    Capture logic (rafle):
        After sowing, if the last seed lands on the opponent's side
        and that pit now contains 2 or 3 seeds, those seeds are captured.
        The chain continues backwards: if the preceding pit also contains
        2 or 3 seeds (and is still on the opponent's side), it is captured
        too, and so on.

    No-starve rule (affamer):
        A player may not play a move that leaves the opponent with zero
        seeds, UNLESS every possible move would do so — in that case the
        constraint is lifted and the opponent collects all remaining seeds.
    """

    # ------------------------------------------------------------------
    # IRules — valid actions
    # ------------------------------------------------------------------

    def valid_actions(self, board: IBoard, player_id: int) -> list[int]:
        """
        Returns absolute pit indices the player may legally play.
        Filters empty pits and moves that would starve the opponent,
        unless all moves starve (affamer exception).
        """
        candidate = [pit for pit in IBoard.side_pits(player_id) if board.holes[pit] > 0]
        if not candidate:
            return []

        non_starving = [
            pit for pit in candidate if not self.would_starve(board, pit, player_id)
        ]

        # Affamer exception: if every move starves, all candidates are legal
        return non_starving if non_starving else candidate

    # ------------------------------------------------------------------
    # IRules — starvation checks
    # ------------------------------------------------------------------

    def would_starve(self, board: IBoard, pit: int, player_id: int) -> bool:
        clone = board.clone()
        seq = clone.sow(pit)
        self.apply_captures(clone, seq[-1], player_id)
        opponent = 1 - player_id
        return all(clone.holes[p] == 0 for p in IBoard.side_pits(opponent))

    def all_starve(self, board: IBoard, player_id: int) -> bool:
        return all(
            self.would_starve(board, pit, player_id)
            for pit in IBoard.side_pits(player_id)
            if board.holes[pit] > 0
        )

    # ------------------------------------------------------------------
    # IRules — captures
    # ------------------------------------------------------------------

    def apply_captures(self, board: IBoard, last_pit: int, player_id: int) -> int:
        """
        Walk backwards from last_pit capturing pits with 2 or 3 seeds,
        as long as they remain on the opponent's side (rafle chain).

        Seeds are moved to the acting player's store.
        Returns total seeds captured.
        """
        if IBoard.pit_owner(last_pit) == player_id:
            return 0  # last seed on own side — no capture

        total_captured = 0
        pit = last_pit

        while IBoard.pit_owner(pit) != player_id:
            seeds = board.holes[pit]
            if seeds in (2, 3):
                board.zero_pit(pit)
                board.add_to_store(player_id, seeds)
                total_captured += seeds
                pit = (pit - 1) % IBoard.TOTAL_PITS
            else:
                break

        return total_captured

    # ------------------------------------------------------------------
    # IRules — terminal state
    # ------------------------------------------------------------------

    def is_terminal(self, board: IBoard) -> bool:
        """
        The game ends when either side has no seeds left.
        """
        return all(board.holes[p] == 0 for p in IBoard.side_pits(0)) or all(
            board.holes[p] == 0 for p in IBoard.side_pits(1)
        )

    def final_scores(self, board: IBoard) -> tuple[int, int]:
        """
        Sweep all remaining seeds to the player who still has seeds.
        Operates on a clone — does not mutate the live board.
        Returns (P0_total, P1_total).
        """
        clone = board.clone()

        for player_id in (0, 1):
            side = list(IBoard.side_pits(player_id))
            remaining = sum(clone.holes[p] for p in side)
            if remaining > 0:
                for p in side:
                    clone.zero_pit(p)
                clone.add_to_store(player_id, remaining)

        return (clone.stores[0], clone.stores[1])
