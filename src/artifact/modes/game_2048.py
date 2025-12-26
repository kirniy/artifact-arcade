"""2048 - Adapted from Mini-Games-with-Pygame 2048."""

import random
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text


class Game2048Mode(BaseMode):
    name = "game_2048"
    display_name = "2048"
    description = "Slide tiles and reach 2048"
    icon = "2048"
    style = "arcade"

    GRID = 4
    CELL = 24
    GAP = 4
    BOARD_SIZE = GRID * CELL + (GRID + 1) * GAP
    OFFSET_X = (128 - BOARD_SIZE) // 2
    OFFSET_Y = 10

    COLORS = {
        0: (30, 26, 22),
        2: (238, 228, 218),
        4: (237, 224, 200),
        8: (242, 177, 121),
        16: (245, 149, 99),
        32: (246, 124, 95),
        64: (246, 94, 59),
        128: (237, 207, 114),
        256: (237, 204, 97),
        512: (237, 200, 80),
        1024: (237, 197, 63),
        2048: (237, 194, 46),
    }

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._board: List[List[int]] = []
        self._score = 0
        self._game_over = False

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._board = [[0 for _ in range(self.GRID)] for _ in range(self.GRID)]
        self._score = 0
        self._game_over = False
        self._spawn_tile()
        self._spawn_tile()

    def _spawn_tile(self) -> None:
        empties = [(r, c) for r in range(self.GRID) for c in range(self.GRID) if self._board[r][c] == 0]
        if not empties:
            return
        r, c = random.choice(empties)
        self._board[r][c] = 4 if random.random() < 0.1 else 2

    def _compress_row(self, row: List[int]) -> Tuple[List[int], int]:
        values = [v for v in row if v != 0]
        merged: List[int] = []
        score_add = 0
        i = 0
        while i < len(values):
            if i + 1 < len(values) and values[i] == values[i + 1]:
                new_val = values[i] * 2
                merged.append(new_val)
                score_add += new_val
                i += 2
            else:
                merged.append(values[i])
                i += 1
        while len(merged) < self.GRID:
            merged.append(0)
        return merged, score_add

    def _move_left(self) -> bool:
        changed = False
        for r in range(self.GRID):
            new_row, score_add = self._compress_row(self._board[r])
            if new_row != self._board[r]:
                changed = True
            self._board[r] = new_row
            self._score += score_add
        return changed

    def _move_right(self) -> bool:
        changed = False
        for r in range(self.GRID):
            rev = list(reversed(self._board[r]))
            new_row, score_add = self._compress_row(rev)
            new_row = list(reversed(new_row))
            if new_row != self._board[r]:
                changed = True
            self._board[r] = new_row
            self._score += score_add
        return changed

    def _move_up(self) -> bool:
        changed = False
        cols = list(zip(*self._board))
        new_cols = []
        for col in cols:
            new_col, score_add = self._compress_row(list(col))
            if list(col) != new_col:
                changed = True
            new_cols.append(new_col)
            self._score += score_add
        self._board = [list(row) for row in zip(*new_cols)]
        return changed

    def _move_down(self) -> bool:
        changed = False
        cols = list(zip(*self._board))
        new_cols = []
        for col in cols:
            rev = list(reversed(list(col)))
            new_col, score_add = self._compress_row(rev)
            new_col = list(reversed(new_col))
            if list(col) != new_col:
                changed = True
            new_cols.append(new_col)
            self._score += score_add
        self._board = [list(row) for row in zip(*new_cols)]
        return changed

    def _has_moves(self) -> bool:
        for r in range(self.GRID):
            for c in range(self.GRID):
                if self._board[r][c] == 0:
                    return True
                if c + 1 < self.GRID and self._board[r][c] == self._board[r][c + 1]:
                    return True
                if r + 1 < self.GRID and self._board[r][c] == self._board[r + 1][c]:
                    return True
        return False

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS and self._game_over:
            self._reset()
            return True

        moved = False
        if event.type == EventType.ARCADE_LEFT:
            moved = self._move_left()
        elif event.type == EventType.ARCADE_RIGHT:
            moved = self._move_right()
        elif event.type == EventType.ARCADE_UP:
            moved = self._move_up()
        elif event.type == EventType.ARCADE_DOWN:
            moved = self._move_down()
        elif event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "4":
                moved = self._move_left()
            elif key == "6":
                moved = self._move_right()
            elif key == "8":
                moved = self._move_up()
            elif key == "2":
                moved = self._move_down()

        if moved:
            self._spawn_tile()
            if not self._has_moves():
                self._game_over = True
            return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return
        if self._game_over:
            return

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (15, 12, 10))

        draw_centered_text(buffer, f"SCORE {self._score}", 1, (230, 230, 230), scale=1)

        # Board background
        draw_rect(
            buffer,
            self.OFFSET_X,
            self.OFFSET_Y,
            self.BOARD_SIZE,
            self.BOARD_SIZE,
            (25, 20, 16),
            filled=True,
        )

        for r in range(self.GRID):
            for c in range(self.GRID):
                value = self._board[r][c]
                color = self.COLORS.get(value, (200, 190, 170))
                x = self.OFFSET_X + self.GAP + c * (self.CELL + self.GAP)
                y = self.OFFSET_Y + self.GAP + r * (self.CELL + self.GAP)
                draw_rect(buffer, x, y, self.CELL, self.CELL, color, filled=True)
                if value:
                    digits = len(str(value))
                    scale = 2 if digits <= 2 else 1
                    draw_centered_text(buffer, str(value), y + 6, (40, 30, 20), scale=scale)

        if self._game_over:
            draw_centered_text(buffer, "GAME OVER", 54, (255, 80, 80), scale=1)
            draw_centered_text(buffer, "PRESS", 66, (220, 220, 220), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"2048 {self._score}", 1, (237, 194, 46), scale=1)

    def get_lcd_text(self) -> str:
        return f"2048 {self._score}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=False,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="2048",
        )
        self.complete(result)
