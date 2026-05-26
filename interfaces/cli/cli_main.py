from __future__ import annotations

import argparse

from core.board import Board
from core.game import Awele
from core.interfaces import IBoard, IPlayer
from core.player import HumanPlayer, RandomPlayer
from core.rules import Rules


def make_game(p0_type: str, p1_type: str, seed: int | None) -> Awele:
    def make_player(player_type: str, player_id: int) -> IPlayer:
        if player_type == "human":
            return HumanPlayer(player_id)
        if player_type == "random":
            return RandomPlayer(player_id, seed=seed)
        raise ValueError(f"Unknown player type: {player_type}")

    return Awele(
        board=Board(),
        rules=Rules(),
        players=[make_player(p0_type, 0), make_player(p1_type, 1)],
    )


def run(
    p0_type: str = "human", p1_type: str = "random", seed: int | None = None
) -> None:
    game = make_game(p0_type, p1_type, seed)
    # PoV rendering only makes sense when both players are human
    pov_rendering = p0_type == "human" and p1_type == "human"

    game.reset()
    move = 0
    result = None

    while not game.done:
        obs = game.get_observation()
        current = obs["current_player"]
        pov = current if pov_rendering else 0
        game.render(pov=pov)
        action = game._players[current].choose_action(obs, obs["action_mask"])
        absolute = current * IBoard.PITS_PER_SIDE + action
        result = game.step(action)
        move += 1

        # rendering and logging
        print(
            f"\n--- move {move}: P{current} played pit {absolute} (local {action}) ---\n\n"
        )

        print(
            f"  stores: P0={result.state.scores[0]}  P1={result.state.scores[1]}  "
            f"no-capture streak: {result.state.no_capture_count}"
        )

    assert result is not None
    print("\n=== game over ===")
    if result.state.winner is not None:
        print(f"winner: P{result.state.winner}")
    else:
        print("draw")
    print(f"final scores — P0: {result.state.scores[0]}  P1: {result.state.scores[1]}")
    print(f"total moves: {move}")


def cli_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Awele CLI")
    parser.add_argument("--p0", choices=["human", "random"], default="human")
    parser.add_argument("--p1", choices=["human", "random"], default="random")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)
    run(p0_type=args.p0, p1_type=args.p1, seed=args.seed)


if __name__ == "__main__":
    cli_main()
