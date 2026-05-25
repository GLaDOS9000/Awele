from tkinter import N
from core.board import Board
from core.game import Awele
from core.player import RandomPlayer
from core.rules import Rules
from core.interfaces import IBoard

SEED = None  # set to an int for reproducible random games


def main() -> None:
    game = Awele(
        board=Board(),
        rules=Rules(),
        players=[RandomPlayer(0, seed=42), RandomPlayer(1, seed=SEED)],
    )

    state = game.reset()
    game.render()
    move = 0

    while not state.done:
        current = state.current_player
        obs = game.get_observation()
        action = game._players[current].choose_action(obs, obs["action_mask"])
        absolute = current * IBoard.PITS_PER_SIDE + action
        result = game.step(action)
        state = result.state
        move += 1
        print(
            f"\n--- move {move}: P{current} plays pit {absolute} (local {action}) ---\n\n"
        )
        game.render()
        print(
            f"  stores: P0={state.scores[0]}  P1={state.scores[1]}  "
            f"no-capture streak: {state.no_capture_count}"
        )

    print("\n=== game over ===")
    if state.winner is not None:
        print(f"winner: P{state.winner}")
    else:
        print("draw")
    print(f"final scores — P0: {state.scores[0]}  P1: {state.scores[1]}")
    print(f"total moves: {move}")


if __name__ == "__main__":
    main()
