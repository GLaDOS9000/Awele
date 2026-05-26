from __future__ import annotations

import argparse

import pygame

from core.board import Board
from core.game import Awele
from core.interfaces import IBoard, IPlayer
from core.player import RandomPlayer
from core.rules import Rules
from interfaces.gui.player import PygameHumanPlayer
from interfaces.gui.view import PygameView


def make_game(
    p0_type: str, p1_type: str, seed: int | None
) -> tuple[Awele, list[IPlayer]]:
    def make_player(player_type: str, player_id: int) -> IPlayer:
        if player_type == "human":
            return PygameHumanPlayer(player_id)
        if player_type == "random":
            return RandomPlayer(player_id, seed=seed)
        raise ValueError(f"Unknown player type: {player_type}")

    players = [make_player(p0_type, 0), make_player(p1_type, 1)]
    game = Awele(board=Board(), rules=Rules(), players=players)
    return game, players


def run_menu(view: PygameView) -> dict | None:
    """
    Landing page — player type and delay selection.
    Returns config dict or None if quit.
    Config: {"p0": str, "p1": str, "delay": int}
    """
    p0 = "human"
    p1 = "random"
    delay = 2000

    while True:
        mx, my = pygame.mouse.get_pos()
        start_h = (
            view._menu_start_rect.collidepoint(mx, my)
            if hasattr(view, "_menu_start_rect")
            else False
        )
        quit_h = (
            view._menu_quit_rect.collidepoint(mx, my)
            if hasattr(view, "_menu_quit_rect")
            else False
        )

        view.render_menu(
            p0_selected=p0,
            p1_selected=p1,
            delay_selected=delay,
            start_hovered=start_h,
            quit_hovered=quit_h,
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = view.menu_hit(event.pos[0], event.pos[1])
                if hit == "start":
                    return {"p0": p0, "p1": p1, "delay": delay}
                if hit == "quit":
                    return None
                if isinstance(hit, tuple):
                    key, val = hit
                    if key == "p0":
                        p0 = val
                    elif key == "p1":
                        p1 = val
                    elif key == "delay":
                        delay = int(val)

        view.tick()


def run_game(
    game: Awele,
    players: list[IPlayer],
    view: PygameView,
    delay_ms: int = 2000,
) -> str:
    """
    Run one game. Returns "menu" or "quit".
    """
    human_ids = {p.player_id for p in players if isinstance(p, PygameHumanPlayer)}
    for p in players:
        if isinstance(p, PygameHumanPlayer):
            p.set_view(view)

    game.reset()
    hovered_pit: int | None = None
    delay_until: int = 0
    winner: int | None = None

    while True:
        obs = game.get_observation()
        current = obs["current_player"]
        action_mask = obs["action_mask"]
        done = obs["done"]

        if current == 0:
            absolute_holes = list(obs["board"][:6]) + list(obs["board"][6:])
            p0_store, p1_store = int(obs["stores"][0]), int(obs["stores"][1])
        else:
            absolute_holes = list(obs["board"][6:]) + list(obs["board"][:6])
            p0_store, p1_store = int(obs["stores"][1]), int(obs["stores"][0])

        mx, my = pygame.mouse.get_pos()

        view.render(
            holes=absolute_holes,
            stores=[p0_store, p1_store],
            action_mask=action_mask,
            current_player=current,
            hovered_pit=hovered_pit,
            done=done,
            winner=winner,
            scores=(p0_store, p1_store),
            no_capture_count=obs["no_capture_count"],
            reset_hovered=view.reset_button_rect.collidepoint(mx, my),
            menu_hovered=view.menu_button_rect.collidepoint(mx, my),
        )

        if done:
            return _handle_events_done(view)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    return "quit"
                if event.key == pygame.K_m:
                    return "menu"
                if event.key == pygame.K_r:
                    game.reset()
                    hovered_pit = None
                    winner = None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                ex, ey = event.pos
                if view.reset_button_rect.collidepoint(ex, ey):
                    game.reset()
                    hovered_pit = None
                    winner = None
                    continue
                if view.menu_button_rect.collidepoint(ex, ey):
                    return "menu"
                pit = view.pit_at(ex, ey)
                if pit is not None and current in human_ids:
                    if IBoard.pit_owner(pit) == current:
                        local = pit % IBoard.PITS_PER_SIDE
                        if action_mask[local]:
                            for p in players:
                                if (
                                    isinstance(p, PygameHumanPlayer)
                                    and p.player_id == current
                                ):
                                    p.receive_action(local)
            if event.type == pygame.MOUSEMOTION:
                ex, ey = event.pos
                pit = view.pit_at(ex, ey)
                if pit is not None and IBoard.pit_owner(pit) == current:
                    local = pit % IBoard.PITS_PER_SIDE
                    hovered_pit = pit if action_mask[local] else None
                else:
                    hovered_pit = None

        if current not in human_ids and not done:
            if pygame.time.get_ticks() >= delay_until:
                action = players[current].choose_action(obs, action_mask)
                result = game.step(action)
                winner = result.state.winner
                hovered_pit = None
        elif current in human_ids:
            for p in players:
                if isinstance(p, PygameHumanPlayer) and p.player_id == current:
                    action = p.pop_action()
                    if action is not None:
                        result = game.step(action)
                        winner = result.state.winner
                        hovered_pit = None
                        if human_ids != {0, 1}:
                            delay_until = pygame.time.get_ticks() + delay_ms

        view.tick()


def _handle_events_done(view: PygameView) -> str:
    """Wait after game ends. Returns 'menu' or 'quit'."""
    while True:
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    return "quit"
                if event.key == pygame.K_m:
                    return "menu"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if view.menu_button_rect.collidepoint(event.pos):
                    return "menu"
        view.tick()


def run(
    p0_type: str = "human",
    p1_type: str = "random",
    seed: int | None = None,
    delay_ms: int = 2000,
) -> None:
    view = PygameView()

    while True:
        config = run_menu(view)
        if config is None:
            break
        game, players = make_game(config["p0"], config["p1"], seed)
        result = run_game(game, players, view, delay_ms=config["delay"])
        if result == "quit":
            break
        # result == "menu" → loop back

    view.quit()


def gui_main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Awele GUI")
    parser.add_argument("--p0", choices=["human", "random"], default="human")
    parser.add_argument("--p1", choices=["human", "random"], default="random")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--delay",
        type=float,
        default=2,
        metavar="SECONDS",
        help="Pause after a human move before the AI plays (default: 2",
    )
    args = parser.parse_args(argv)
    run(
        p0_type=args.p0,
        p1_type=args.p1,
        seed=args.seed,
        delay_ms=int(args.delay * 1000),
    )


if __name__ == "__main__":
    gui_main()
