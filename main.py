# from core.board import Board
# from core.game import Awele
# from core.player import RandomPlayer
# from core.rules import Rules
# from core.interfaces import IBoard

# SEED = None  # set to an int for reproducible random games


# def main() -> None:
#     game = Awele(
#         board=Board(),
#         rules=Rules(),
#         players=[RandomPlayer(0, seed=42), RandomPlayer(1, seed=SEED)],
#     )

#     game.reset()
#     game.render()
#     move = 0
#     result = None

#     while not game.done:
#         # game workflow
#         obs = game.get_observation()
#         current = obs["current_player"]
#         action = game._players[current].choose_action(obs, obs["action_mask"])
#         result = game.step(action)

#         # rendering and logging
#         move += 1
#         absolute = current * IBoard.PITS_PER_SIDE + action
#         print(
#             f"\n--- move {move}: P{current} plays pit {absolute} (local {action}) ---\n\n"
#         )
#         game.render()
#         print(
#             f"  stores: P0={result.state.scores[0]}  P1={result.state.scores[1]}  "
#             f"no-capture streak: {result.state.no_capture_count}"
#         )

#     assert (
#         result is not None
#     )  # type checker doesn't know game.done implies result is set
#     print("\n=== game over ===")
#     if result.state.winner is not None:
#         print(f"winner: P{result.state.winner}")
#     else:
#         print("draw")
#     print(f"final scores — P0: {result.state.scores[0]}  P1: {result.state.scores[1]}")
#     print(f"total moves: {move}")


# if __name__ == "__main__":
#     main()

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Awele")
    parser.add_argument("--mode", choices=["cli", "gui", "web"], default="cli")
    args, remaining = parser.parse_known_args()

    if args.mode == "cli":
        from interfaces.cli.cli_main import cli_main

        cli_main(remaining)

    elif args.mode == "gui":
        from interfaces.gui.controller import gui_main

        gui_main(remaining)

    elif args.mode == "web":
        raise NotImplementedError("Web mode is not implemented yet.")
        from interfaces.web.server import main as web_main

        web_main()


if __name__ == "__main__":
    main()
