import random
import pygame

GRID_SIZE = 8
TILE_SIZE = 60
GEM_COLORS = [
    (220, 50, 50),   # Red
    (50, 200, 50),   # Green
    (50, 100, 240),  # Blue
    (240, 200, 40),  # Yellow
    (180, 50, 220),  # Purple
    (240, 130, 40),  # Orange
]


class Gem:
   
    def __init__(self, color, target_row, col, is_bomb=False, bomb_dir="row"):
        self.color = color
        self.target_row = target_row
        self.col = col
        self.is_bomb = is_bomb
        self.bomb_dir = bomb_dir  # "row" clears row, "col" clears column
        # Start higher up to animate falling down
        self.current_y = (target_row - 2) * TILE_SIZE
        self.target_y = target_row * TILE_SIZE
        self.fall_speed = 12.0

    def update(self):
        if self.current_y < self.target_y:
            self.current_y += self.fall_speed
            if self.current_y > self.target_y:
                self.current_y = self.target_y

    def is_animating(self):
        return self.current_y < self.target_y


class Board:
    """Manages animated gem grid, gravity drops, score, and game limits."""

    def __init__(self, offset_x, offset_y, target_score=500, max_moves=20):
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.target_score = target_score
        self.max_moves = max_moves
        self.grid = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.selected = None
        self.score = 0
        self.moves_remaining = max_moves
        self.last_combo = 0
        self.reset()

    def reset(self):
        """Reset board grid, score, and move limits."""
        self.score = 0
        self.moves_remaining = self.max_moves
        self.selected = None
        self.last_combo = 0
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                color = random.choice(GEM_COLORS)
                gem = Gem(color, r, c)
                gem.current_y = gem.target_y  # Snap instantly on initial start
                self.grid[r][c] = gem

        self.resolve_matches()
        self.last_combo = 0

    def is_animating(self):
        """Returns True if any gem is currently dropping down."""
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if self.grid[r][c] and self.grid[r][c].is_animating():
                    return True
        return False

    def swap_gems(self, pos1, pos2):
        """Swap positions and target render coordinates of two gems."""
        r1, c1 = pos1
        r2, c2 = pos2

        g1, g2 = self.grid[r1][c1], self.grid[r2][c2]
        self.grid[r1][c1], self.grid[r2][c2] = g2, g1

        if self.grid[r1][c1]:
            self.grid[r1][c1].target_row = r1
            self.grid[r1][c1].target_y = r1 * TILE_SIZE
            self.grid[r1][c1].current_y = r1 * TILE_SIZE

        if self.grid[r2][c2]:
            self.grid[r2][c2].target_row = r2
            self.grid[r2][c2].target_y = r2 * TILE_SIZE
            self.grid[r2][c2].current_y = r2 * TILE_SIZE

    def is_adjacent(self, pos1, pos2):
        r1, c1 = pos1
        r2, c2 = pos2
        return abs(r1 - r2) + abs(c1 - c2) == 1

    def find_matches(self):
        """Scan grid for horizontal and vertical 3-in-a-row color matches."""
        matched = set()

        # Horizontal matches
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE - 2):
                if (
                    self.grid[r][c]
                    and self.grid[r][c + 1]
                    and self.grid[r][c + 2]
                    and self.grid[r][c].color == self.grid[r][c + 1].color == self.grid[r][c + 2].color
                ):
                    matched.update([(r, c), (r, c + 1), (r, c + 2)])

        # Vertical matches
        for r in range(GRID_SIZE - 2):
            for c in range(GRID_SIZE):
                if (
                    self.grid[r][c]
                    and self.grid[r + 1][c]
                    and self.grid[r + 2][c]
                    and self.grid[r][c].color == self.grid[r + 1][c].color == self.grid[r + 2][c].color
                ):
                    matched.update([(r, c), (r + 1, c), (r + 2, c)])

        return self._expand_bombs(matched)

    def find_match_groups(self):
        """Return contiguous same-color runs >=3 as [{'cells':[(r,c)..], 'dir':'row'/'col'}]."""
        groups = []
        # Horizontal runs
        for r in range(GRID_SIZE):
            c = 0
            while c < GRID_SIZE:
                if self.grid[r][c] is None:
                    c += 1
                    continue
                color = self.grid[r][c].color
                run = [(r, c)]
                cc = c + 1
                while (
                    cc < GRID_SIZE
                    and self.grid[r][cc] is not None
                    and self.grid[r][cc].color == color
                ):
                    run.append((r, cc))
                    cc += 1
                if len(run) >= 3:
                    groups.append({"cells": run, "dir": "row"})
                c = cc if len(run) > 1 else c + 1
        # Vertical runs
        for c in range(GRID_SIZE):
            r = 0
            while r < GRID_SIZE:
                if self.grid[r][c] is None:
                    r += 1
                    continue
                color = self.grid[r][c].color
                run = [(r, c)]
                rr = r + 1
                while (
                    rr < GRID_SIZE
                    and self.grid[rr][c] is not None
                    and self.grid[rr][c].color == color
                ):
                    run.append((rr, c))
                    rr += 1
                if len(run) >= 3:
                    groups.append({"cells": run, "dir": "col"})
                r = rr if len(run) > 1 else r + 1
        return groups

    def _expand_bombs(self, matched):
        """If a matched cell holds a Bomb Gem, add its full row/column (chain-aware)."""
        matched = set(matched)
        if not matched:
            return matched
        queue = list(matched)
        seen_bombs = set()
        while queue:
            r, c = queue.pop()
            if not (0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE):
                continue
            gem = self.grid[r][c]
            if (
                gem is not None
                and getattr(gem, "is_bomb", False)
                and (r, c) not in seen_bombs
            ):
                seen_bombs.add((r, c))
                if getattr(gem, "bomb_dir", "row") == "col":
                    targets = [(rr, c) for rr in range(GRID_SIZE)]
                else:
                    targets = [(r, cc) for cc in range(GRID_SIZE)]
                for t in targets:
                    if t not in matched:
                        matched.add(t)
                        queue.append(t)
        return matched

    def find_hint(self):
        """Find adjacent pair that would produce a match if swapped.

        Returns ((r1,c1),(r2,c2)) or None. Bomb swaps count as valid
        (fallback) since swapping a bomb always detonates.
        """
        if self.find_matches():
            return None  # board not settled
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if self.grid[r][c] is None:
                    continue
                for dr, dc in [(0, 1), (1, 0)]:
                    r2, c2 = r + dr, c + dc
                    if r2 >= GRID_SIZE or c2 >= GRID_SIZE:
                        continue
                    if self.grid[r2][c2] is None:
                        continue
                    g1, g2 = self.grid[r][c], self.grid[r2][c2]
                    self.grid[r][c], self.grid[r2][c2] = g2, g1
                    matches = self.find_matches()
                    self.grid[r][c], self.grid[r2][c2] = g1, g2
                    if matches:
                        return ((r, c), (r2, c2))
        # Fallback: any adjacent bomb swap detonates
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                gem = self.grid[r][c]
                if gem is not None and getattr(gem, "is_bomb", False):
                    for dr, dc in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        r2, c2 = r + dr, c + dc
                        if 0 <= r2 < GRID_SIZE and 0 <= c2 < GRID_SIZE:
                            if self.grid[r2][c2] is not None:
                                return ((r, c), (r2, c2))
        return None

    def drop_and_refill(self):
        for c in range(GRID_SIZE):
            empty_slots = 0
            for r in range(GRID_SIZE - 1, -1, -1):
                if self.grid[r][c] is None:
                    empty_slots += 1
                elif empty_slots > 0:
                    gem = self.grid[r][c]
                    gem.target_row = r + empty_slots
                    gem.target_y = (r + empty_slots) * TILE_SIZE
                    self.grid[r + empty_slots][c] = gem
                    self.grid[r][c] = None

            for r in range(empty_slots):
                color = random.choice(GEM_COLORS)
                gem = Gem(color, r, c)
                gem.current_y = -((empty_slots - r) * TILE_SIZE)
                self.grid[r][c] = gem

    def resolve_matches(self):
        """Clear matches with cascade combo multiplier.

        1x for initial matches, 2x for secondary drops, 3x for tertiary, etc.
        4-in-a-row runs spawn a glowing Bomb Gem (kept, not cleared).
        Bomb Gems in a match detonate their full row/column.
        Returns total combo points (cleared * 10 * combo per cascade level).
        """
        combo = 0
        total_points = 0
        while True:
            matches = self.find_matches()
            if not matches:
                break
            combo += 1
            total_points += len(matches) * 10 * combo

            # Detect 4+ runs -> spawn one bomb per run (middle cell, keep it)
            spawn = {}
            for g in self.find_match_groups():
                cells = g["cells"]
                if len(cells) >= 4:
                    # Don't spawn if a bomb is already detonating here
                    if any(
                        self.grid[r][c] is not None
                        and getattr(self.grid[r][c], "is_bomb", False)
                        for r, c in cells
                    ):
                        continue
                    sr, sc = cells[len(cells) // 2]
                    if (sr, sc) in matches and (sr, sc) not in spawn:
                        spawn[(sr, sc)] = g["dir"]

            for r, c in matches:
                if (r, c) not in spawn:
                    self.grid[r][c] = None

            for (sr, sc), bdir in spawn.items():
                old = self.grid[sr][sc]
                color = old.color if old is not None else random.choice(GEM_COLORS)
                bomb = Gem(color, sr, sc, is_bomb=True, bomb_dir=bdir)
                bomb.current_y = sr * TILE_SIZE
                bomb.target_y = sr * TILE_SIZE
                bomb.target_row = sr
                self.grid[sr][sc] = bomb

            self.drop_and_refill()
        self.last_combo = combo
        return total_points

    def _collect_bomb_blast(self, positions):
        """Return full blast set for bombs at positions (row or column each, chain-aware)."""
        blast = set(positions)
        queue = list(positions)
        seen = set()
        while queue:
            r, c = queue.pop()
            if (r, c) in seen:
                continue
            seen.add((r, c))
            gem = (
                self.grid[r][c]
                if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE
                else None
            )
            if gem is None or not getattr(gem, "is_bomb", False):
                continue
            if getattr(gem, "bomb_dir", "row") == "col":
                targets = [(rr, c) for rr in range(GRID_SIZE)]
            else:
                targets = [(r, cc) for cc in range(GRID_SIZE)]
            for t in targets:
                if t not in blast:
                    blast.add(t)
                    queue.append(t)
        return blast

    def process_swap(self, pos1, pos2):
        if not self.is_adjacent(pos1, pos2) or self.is_game_over() or self.is_animating():
            return False

        self.swap_gems(pos1, pos2)

        # Bomb detonation: swapping a bomb detonates even without a color match
        bomb_positions = [
            p
            for p in (pos1, pos2)
            if self.grid[p[0]][p[1]] is not None
            and getattr(self.grid[p[0]][p[1]], "is_bomb", False)
        ]
        if bomb_positions:
            self.moves_remaining -= 1
            blast = self._collect_bomb_blast(bomb_positions)
            # combo level 1 for the detonation itself
            points = len(blast) * 10 * 1
            for r, c in blast:
                self.grid[r][c] = None
            self.drop_and_refill()
            # Cascades after blast use combo starting at 2
            combo = 1
            while True:
                matches = self.find_matches()
                if not matches:
                    break
                combo += 1
                points += len(matches) * 10 * combo
                spawn = {}
                for g in self.find_match_groups():
                    cells = g["cells"]
                    if len(cells) >= 4 and not any(
                        self.grid[r][c] is not None
                        and getattr(self.grid[r][c], "is_bomb", False)
                        for r, c in cells
                    ):
                        sr, sc = cells[len(cells) // 2]
                        if (sr, sc) in matches and (sr, sc) not in spawn:
                            spawn[(sr, sc)] = g["dir"]
                for r, c in matches:
                    if (r, c) not in spawn:
                        self.grid[r][c] = None
                for (sr, sc), bdir in spawn.items():
                    old = self.grid[sr][sc]
                    color = old.color if old is not None else random.choice(GEM_COLORS)
                    bomb = Gem(color, sr, sc, is_bomb=True, bomb_dir=bdir)
                    bomb.current_y = sr * TILE_SIZE
                    bomb.target_y = sr * TILE_SIZE
                    bomb.target_row = sr
                    self.grid[sr][sc] = bomb
                self.drop_and_refill()
            self.last_combo = combo
            self.score += points
            return True

        matches = self.find_matches()

        if not matches:
            self.swap_gems(pos1, pos2)  # Revert invalid swap
            return False

        self.moves_remaining -= 1

        points = self.resolve_matches()
        self.score += points
        return True

    def is_game_over(self):
        return self.score >= self.target_score or self.moves_remaining <= 0

    def check_result(self):
        if self.score >= self.target_score:
            return "WIN"
        if self.moves_remaining <= 0:
            return "LOSS"
        return None

    def update(self):
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                if self.grid[r][c]:
                    self.grid[r][c].update()

    def render(self, surface):
        board_rect = pygame.Rect(
            self.offset_x, self.offset_y, GRID_SIZE * TILE_SIZE, GRID_SIZE * TILE_SIZE
        )
        pygame.draw.rect(surface, (20, 22, 28), board_rect, border_radius=8)
        pygame.draw.rect(surface, (60, 65, 75), board_rect, width=3, border_radius=8)

        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                gem = self.grid[r][c]
                if gem:
                    x = self.offset_x + c * TILE_SIZE
                    y = self.offset_y + gem.current_y
                    tile_rect = pygame.Rect(x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4)

                    pygame.draw.rect(surface, gem.color, tile_rect, border_radius=10)
                    if getattr(gem, "is_bomb", False):
                        # Glowing Bomb Gem: pulsing white/yellow outline + core dot
                        import math

                        pulse = (math.sin(pygame.time.get_ticks() * 0.008) + 1) / 2
                        glow_w = 3 + int(pulse * 3)
                        pygame.draw.rect(
                            surface, (255, 255, 180), tile_rect, width=glow_w, border_radius=12
                        )
                        cx, cy = tile_rect.center
                        dot_r = 8 + int(pulse * 3)
                        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), dot_r)
                        pygame.draw.circle(surface, (40, 40, 40), (cx, cy), max(3, dot_r - 4))
                    else:
                        pygame.draw.rect(
                            surface, (255, 255, 255), tile_rect, width=1, border_radius=10
                        )

                if self.selected == (r, c):
                    sel_x = self.offset_x + c * TILE_SIZE
                    sel_y = self.offset_y + r * TILE_SIZE
                    sel_rect = pygame.Rect(sel_x + 2, sel_y + 2, TILE_SIZE - 4, TILE_SIZE - 4)
                    pygame.draw.rect(
                        surface, (255, 255, 255), sel_rect, width=4, border_radius=10
                    )