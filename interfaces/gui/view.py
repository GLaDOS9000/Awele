from __future__ import annotations

import math
from typing import Any

import pygame
import pygame.display
import pygame.draw
import pygame.event
import pygame.font
import pygame.time

from core.interfaces import IBoard

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

BG = (18, 18, 24)
BOARD_BG = (30, 30, 40)
BOARD_LINE = (60, 60, 80)
PIT_EMPTY = (45, 45, 60)
PIT_HOVER = (80, 120, 180)
PIT_LEGAL = (55, 85, 130)
PIT_ILLEGAL = (35, 35, 48)
SEED_COLORS = [
    (220, 180, 80),  # gold
    (180, 120, 60),  # amber
    (200, 160, 70),  # warm gold
    (160, 90, 50),  # dark amber
]
STORE_BG = (38, 38, 52)
TEXT_MAIN = (230, 230, 240)
TEXT_DIM = (120, 120, 140)
TEXT_ACCENT = (100, 180, 255)
HIGHLIGHT = (100, 200, 120)
P0_COLOR = (80, 160, 255)
P1_COLOR = (255, 120, 80)
SEPARATOR = (55, 55, 70)


class PygameView:
    """
    Renders the Awele board using Pygame.

    Layout (landscape):
        ┌─────────────────────────────────────────────┐
        │  [P1 store]  [P1 pits 11→6]  [P1 store gap] │
        │  [P0 store gap] [P0 pits 0→5] [P0 store]    │
        └─────────────────────────────────────────────┘

    Coordinate system:
        Pit circles are indexed 0-11 absolutely.
        P0 pits (0-5) on the bottom row, left to right.
        P1 pits (6-11) on the top row, right to left (11 leftmost).

    The view is purely read-only — it never calls game.step().
    All interaction is handled by the controller.
    """

    W = 900
    H = 520
    PIT_R = 46  # pit circle radius
    SEED_R = 6  # individual seed dot radius
    STORE_W = 90
    STORE_H = 220
    FONT_LARGE = 28
    FONT_MED = 20
    FONT_SMALL = 14
    FPS = 60

    def __init__(self) -> None:
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("Awele")
        self.screen = pygame.display.set_mode((self.W, self.H))
        self.clock = pygame.time.Clock()

        self._font_large = pygame.font.SysFont("monospace", self.FONT_LARGE, bold=True)
        self._font_med = pygame.font.SysFont("monospace", self.FONT_MED)
        self._font_small = pygame.font.SysFont("monospace", self.FONT_SMALL)

        # self._font_large = pygame.font.Font(None, self.FONT_LARGE)
        # self._font_med = pygame.font.Font(None, self.FONT_MED)
        # self._font_small = pygame.font.Font(None, self.FONT_SMALL)

        # Precompute pit center positions
        self._pit_centers: dict[int, tuple[int, int]] = {}
        self._compute_layout()

        # Animation state
        self._drop_sequence: list[int] = []
        self._drop_index: int = 0
        self._drop_timer: int = 0
        self._drop_interval: int = 120  # ms per seed drop
        self._animating: bool = False

        # Hover state
        self._hovered_pit: int | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _compute_layout(self) -> None:
        """Compute pit center (x, y) for all 12 pits and both stores."""
        usable_w = self.W - 2 * self.STORE_W - 40
        pit_spacing = usable_w // IBoard.PITS_PER_SIDE
        x_start = self.STORE_W + 20 + pit_spacing // 2
        y_top = self.H // 2 - self.PIT_R - 30
        y_bot = self.H // 2 + self.PIT_R + 30

        # P0 pits bottom row (0-5 left to right)
        for i in range(IBoard.PITS_PER_SIDE):
            self._pit_centers[i] = (x_start + i * pit_spacing, y_bot)

        # P1 pits top row (6-11 mapped: pit 11 leftmost, pit 6 rightmost)
        for i in range(IBoard.PITS_PER_SIDE):
            absolute = 11 - i  # 11,10,9,8,7,6
            self._pit_centers[absolute] = (x_start + i * pit_spacing, y_top)

        # Store positions
        self._store_p1 = pygame.Rect(
            10, self.H // 2 - self.STORE_H // 2, self.STORE_W - 10, self.STORE_H
        )
        self._store_p0 = pygame.Rect(
            self.W - self.STORE_W + 5,
            self.H // 2 - self.STORE_H // 2,
            self.STORE_W - 10,
            self.STORE_H,
        )

        # Reset button (bottom-right, inside the board area)
        self._reset_btn = pygame.Rect(self.W - self.STORE_W - 118, self.H - 36, 108, 24)
        self._menu_btn = pygame.Rect(self.W - self.STORE_W - 232, self.H - 36, 108, 24)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def reset_button_rect(self) -> pygame.Rect:
        return self._reset_btn

    @property
    def menu_button_rect(self) -> pygame.Rect:
        return self._menu_btn

    def render(
        self,
        holes: list[int],
        stores: list[int],
        action_mask: list[bool],
        current_player: int,
        hovered_pit: int | None,
        done: bool,
        winner: int | None,
        scores: tuple[int, int],
        no_capture_count: int,
        animating_pits: set[int] | None = None,
        reset_hovered: bool = False,
        menu_hovered: bool = False,
    ) -> None:
        """Draw one frame. Called every tick by the controller."""
        self.screen.fill(BG)
        self._draw_board_bg()
        self._draw_stores(stores, current_player)
        self._draw_pits(
            holes, action_mask, current_player, hovered_pit, animating_pits or set()
        )
        self._draw_separator()
        self._draw_hud(current_player, scores, no_capture_count, done, winner)
        self._draw_reset_button(reset_hovered)
        self._draw_menu_button(menu_hovered)
        pygame.display.flip()

    def tick(self) -> None:
        self.clock.tick(self.FPS)

    def pit_at(self, x: int, y: int) -> int | None:
        """Return the absolute pit index under (x, y), or None."""
        for pit, (cx, cy) in self._pit_centers.items():
            if math.hypot(x - cx, y - cy) <= self.PIT_R:
                return pit
        return None

    def quit(self) -> None:
        pygame.quit()

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_board_bg(self) -> None:
        board_rect = pygame.Rect(
            self.STORE_W,
            20,
            self.W - 2 * self.STORE_W,
            self.H - 40,
        )
        pygame.draw.rect(self.screen, BOARD_BG, board_rect, border_radius=16)
        pygame.draw.rect(self.screen, BOARD_LINE, board_rect, width=1, border_radius=16)

    def _draw_separator(self) -> None:
        y = self.H // 2
        pygame.draw.line(
            self.screen,
            SEPARATOR,
            (self.STORE_W + 10, y),
            (self.W - self.STORE_W - 10, y),
            1,
        )

    def _draw_pits(
        self,
        holes: list[int],
        action_mask: list[bool],
        current_player: int,
        hovered_pit: int | None,
        animating_pits: set[int],
    ) -> None:
        for pit, (cx, cy) in self._pit_centers.items():
            seeds = holes[pit]
            owner = IBoard.pit_owner(pit)
            local = pit % IBoard.PITS_PER_SIDE
            is_legal = (owner == current_player) and action_mask[local]
            is_hovered = (pit == hovered_pit) and is_legal
            is_animating = pit in animating_pits

            # Pit background
            if is_hovered:
                color = PIT_HOVER
            elif is_legal:
                color = PIT_LEGAL
            elif is_animating:
                color = (70, 100, 70)
            else:
                color = PIT_EMPTY if owner == current_player else PIT_ILLEGAL

            pygame.draw.circle(self.screen, color, (cx, cy), self.PIT_R)
            pygame.draw.circle(self.screen, BOARD_LINE, (cx, cy), self.PIT_R, 1)

            # Seeds
            self._draw_seeds(seeds, cx, cy)

            # Pit index label
            idx_surf = self._font_small.render(str(pit), True, TEXT_DIM)
            self.screen.blit(
                idx_surf, (cx - idx_surf.get_width() // 2, cy + self.PIT_R + 4)
            )

    def _draw_seeds(self, count: int, cx: int, cy: int) -> None:
        if count == 0:
            return
        if count <= 12:
            # Arrange in a circle within the pit
            for i in range(count):
                angle = 2 * math.pi * i / count - math.pi / 2
                radius = self.PIT_R * 0.55 if count > 1 else 0
                sx = int(cx + radius * math.cos(angle))
                sy = int(cy + radius * math.sin(angle))
                color = SEED_COLORS[i % len(SEED_COLORS)]
                pygame.draw.circle(self.screen, color, (sx, sy), self.SEED_R)
        else:
            # Too many to show individually — display count only
            pass

        # Count label
        color = TEXT_MAIN if count <= 12 else TEXT_ACCENT
        surf = self._font_med.render(str(count), True, color)
        self.screen.blit(
            surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2)
        )

    def _draw_stores(self, stores: list[int], current_player: int) -> None:
        for player_id, rect in enumerate([self._store_p1, self._store_p0]):
            color = STORE_BG
            border = P0_COLOR if player_id == 0 else P1_COLOR
            width = 2 if player_id == current_player else 1
            pygame.draw.rect(self.screen, color, rect, border_radius=12)
            pygame.draw.rect(self.screen, border, rect, width=width, border_radius=12)

            label = self._font_small.render(
                f"P{player_id}", True, P0_COLOR if player_id == 0 else P1_COLOR
            )
            self.screen.blit(
                label, (rect.centerx - label.get_width() // 2, rect.top + 10)
            )

            val = self._font_large.render(str(stores[player_id]), True, TEXT_MAIN)
            self.screen.blit(
                val,
                (
                    rect.centerx - val.get_width() // 2,
                    rect.centery - val.get_height() // 2,
                ),
            )

    def _draw_hud(
        self,
        current_player: int,
        scores: tuple[int, int],
        no_capture_count: int,
        done: bool,
        winner: int | None,
    ) -> None:
        if done:
            if winner is not None:
                msg = f"P{winner} wins!  {scores[0]} – {scores[1]}"
            else:
                msg = f"Draw  {scores[0]} – {scores[1]}"
            surf = self._font_large.render(msg, True, HIGHLIGHT)
            self.screen.blit(surf, (self.W // 2 - surf.get_width() // 2, 8))
        else:
            color = P0_COLOR if current_player == 0 else P1_COLOR
            msg = f"P{current_player}'s turn"
            surf = self._font_med.render(msg, True, color)
            self.screen.blit(surf, (self.W // 2 - surf.get_width() // 2, 8))

            streak = self._font_small.render(
                f"no-capture streak: {no_capture_count}", True, TEXT_DIM
            )
            self.screen.blit(
                streak, (self.W // 2 - streak.get_width() // 2, self.H - 22)
            )

    def _draw_reset_button(self, hovered: bool) -> None:
        btn = self._reset_btn
        bg = (70, 70, 90) if hovered else (50, 50, 68)
        border = (140, 140, 180) if hovered else (90, 90, 120)
        pygame.draw.rect(self.screen, bg, btn, border_radius=6)
        pygame.draw.rect(self.screen, border, btn, width=1, border_radius=6)
        label = self._font_small.render("R  Reset", True, TEXT_MAIN)
        self.screen.blit(
            label,
            (
                btn.centerx - label.get_width() // 2,
                btn.centery - label.get_height() // 2,
            ),
        )

    def render_menu(
        self,
        p0_selected: str,
        p1_selected: str,
        delay_selected: int,
        start_hovered: bool,
        quit_hovered: bool,
    ) -> None:
        self.screen.fill(BG)

        # Title
        title = self._font_large.render("A W A L E", True, TEXT_ACCENT)
        self.screen.blit(title, (self.W // 2 - title.get_width() // 2, 60))

        subtitle = self._font_small.render("an ancient seed game", True, TEXT_DIM)
        self.screen.blit(subtitle, (self.W // 2 - subtitle.get_width() // 2, 100))

        # Player type options
        options = ["human", "random"]
        self._draw_menu_row("Player 0", options, p0_selected, 180, "p0")
        self._draw_menu_row("Player 1", options, p1_selected, 250, "p1")

        # Delay options
        delay_options = [0, 500, 1000, 2000, 3000, 5000]
        self._draw_menu_row(
            "AI delay (ms)",
            [str(d) for d in delay_options],
            str(delay_selected),
            320,
            "delay",
        )

        # Start button
        start_bg = (60, 120, 80) if start_hovered else (40, 90, 60)
        start_rect = pygame.Rect(self.W // 2 - 80, 400, 160, 40)
        pygame.draw.rect(self.screen, start_bg, start_rect, border_radius=8)
        pygame.draw.rect(self.screen, HIGHLIGHT, start_rect, width=1, border_radius=8)
        label = self._font_med.render("Start Game", True, TEXT_MAIN)
        self.screen.blit(
            label,
            (
                start_rect.centerx - label.get_width() // 2,
                start_rect.centery - label.get_height() // 2,
            ),
        )

        # Quit button
        quit_bg = (100, 40, 40) if quit_hovered else (70, 30, 30)
        quit_rect = pygame.Rect(self.W // 2 - 80, 455, 160, 36)
        pygame.draw.rect(self.screen, quit_bg, quit_rect, border_radius=8)
        pygame.draw.rect(
            self.screen, (180, 60, 60), quit_rect, width=1, border_radius=8
        )
        qlabel = self._font_small.render("Quit", True, TEXT_MAIN)
        self.screen.blit(
            qlabel,
            (
                quit_rect.centerx - qlabel.get_width() // 2,
                quit_rect.centery - qlabel.get_height() // 2,
            ),
        )

        # Store rects for hit testing
        self._menu_start_rect = start_rect
        self._menu_quit_rect = quit_rect

        pygame.display.flip()

    def _draw_menu_row(
        self,
        label: str,
        options: list[str],
        selected: str,
        y: int,
        key: str,
    ) -> None:
        lbl = self._font_small.render(label + ":", True, TEXT_DIM)
        self.screen.blit(lbl, (120, y + 6))

        if not hasattr(self, "_menu_option_rects"):
            self._menu_option_rects: dict[tuple[str, str], pygame.Rect] = {}

        # Compute button width to fit all options in available space
        available_w = self.W - 320 - 40  # 320 = label area, 40 = right margin
        btn_w = min(100, (available_w - (len(options) - 1) * 8) // len(options))
        x = 320

        for opt in options:
            rect = pygame.Rect(x, y, btn_w, 30)
            active = opt == selected
            bg = PIT_LEGAL if active else PIT_EMPTY
            border = TEXT_ACCENT if active else BOARD_LINE
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, border, rect, width=1, border_radius=6)
            surf = self._font_small.render(opt, True, TEXT_MAIN if active else TEXT_DIM)
            self.screen.blit(
                surf,
                (
                    rect.centerx - surf.get_width() // 2,
                    rect.centery - surf.get_height() // 2,
                ),
            )
            self._menu_option_rects[(key, opt)] = rect
            x += btn_w + 8

    def _draw_menu_button(self, hovered: bool) -> None:
        btn = self._menu_btn
        bg = (70, 70, 90) if hovered else (50, 50, 68)
        border = (140, 140, 180) if hovered else (90, 90, 120)
        pygame.draw.rect(self.screen, bg, btn, border_radius=6)
        pygame.draw.rect(self.screen, border, btn, width=1, border_radius=6)
        label = self._font_small.render("M  Menu", True, TEXT_MAIN)
        self.screen.blit(
            label,
            (
                btn.centerx - label.get_width() // 2,
                btn.centery - label.get_height() // 2,
            ),
        )

    def menu_hit(self, x: int, y: int) -> tuple[str, str] | str | None:
        """
        Returns:
            ("p0"|"p1"|"delay", value)  if an option button was clicked
            "start"                      if start was clicked
            "quit"                       if quit was clicked
            None                         otherwise
        """
        if hasattr(self, "_menu_start_rect") and self._menu_start_rect.collidepoint(
            x, y
        ):
            return "start"
        if hasattr(self, "_menu_quit_rect") and self._menu_quit_rect.collidepoint(x, y):
            return "quit"
        if hasattr(self, "_menu_option_rects"):
            for (key, val), rect in self._menu_option_rects.items():
                if rect.collidepoint(x, y):
                    return (key, val)
        return None
