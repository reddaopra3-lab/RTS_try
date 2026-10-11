import heapq
import math
from typing import List, Tuple, Set, Dict

class SpatialPathfinder:
    """独立的空间网格寻路与碰撞检测子系统"""
    def __init__(self, width: int, height: int, cell_size: int = 10):
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.columns = math.ceil(width / cell_size)
        self.rows = math.ceil(height / cell_size)

    def is_blocked(self, x: float, y: float, radius: float, buildings: list, rivers: list, bridges: list) -> bool:
        if x - radius < 0 or y - radius < 0 or x + radius > self.width or y + radius > self.height:
            return True

        for b in buildings:
            half = b.size / 2 + radius + 2
            if abs(b.x - x) < half and abs(b.y - y) < half:
                return True

        for r in rivers:
            if not self._circle_intersects_rect(x, y, radius, r.rect):
                continue
            if r.rect.w <= r.rect.h:
                on_bridge = any(
                    bridge.rect.left <= r.rect.left - radius
                    and bridge.rect.right >= r.rect.right + radius
                    and bridge.rect.top + radius <= y <= bridge.rect.bottom - radius
                    for bridge in bridges
                )
            else:
                on_bridge = any(
                    bridge.rect.top <= r.rect.top - radius
                    and bridge.rect.bottom >= r.rect.bottom + radius
                    and bridge.rect.left + radius <= x <= bridge.rect.right - radius
                    for bridge in bridges
                )
            if not on_bridge:
                return True
        return False

    @staticmethod
    def _circle_intersects_rect(x: float, y: float, radius: float, rect) -> bool:
        nearest_x = min(max(x, rect.left), rect.right)
        nearest_y = min(max(y, rect.top), rect.bottom)
        return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 < radius ** 2

    def find_path(
        self, start_pos: Tuple[float, float], goal_pos: Tuple[float, float], radius: float, buildings: list, rivers: list, bridges: list
    ) -> List[Tuple[float, float]]:
        x1, y1 = start_pos
        x2, y2 = goal_pos
        walkable: Dict[Tuple[int, int], bool] = {}

        def point(cell: Tuple[int, int]) -> Tuple[float, float]:
            return ((cell[0] + 0.5) * self.cell_size, (cell[1] + 0.5) * self.cell_size)

        def is_walkable(cell: Tuple[int, int]) -> bool:
            if cell not in walkable:
                px, py = point(cell)
                walkable[cell] = (
                    0 <= cell[0] < self.columns
                    and 0 <= cell[1] < self.rows
                    and not self.is_blocked(px, py, radius, buildings, rivers, bridges)
                )
            return walkable[cell]

        start_cell = (
            min(self.columns - 1, max(0, int(x1 / self.cell_size))),
            min(self.rows - 1, max(0, int(y1 / self.cell_size))),
        )
        goal_cell = (
            min(self.columns - 1, max(0, int(x2 / self.cell_size))),
            min(self.rows - 1, max(0, int(y2 / self.cell_size))),
        )

        if not is_walkable(start_cell) or not is_walkable(goal_cell):
            return []

        directions = (
            (-1, 0, 10), (1, 0, 10), (0, -1, 10), (0, 1, 10),
            (-1, -1, 14.142), (1, -1, 14.142), (-1, 1, 14.142), (1, 1, 14.142),
        )
        distances: Dict[Tuple[int, int], float] = {start_cell: 0.0}
        previous: Dict[Tuple[int, int], Tuple[int, int]] = {}
        queue = [(math.hypot(point(start_cell)[0] - x2, point(start_cell)[1] - y2), 0.0, start_cell)]
        visited: Set[Tuple[int, int]] = set()

        while queue:
            _, cost, current = heapq.heappop(queue)
            if current in visited:
                continue
            visited.add(current)
            if current == goal_cell:
                break

            for dx, dy, step_cost in directions:
                neighbor = (current[0] + dx, current[1] + dy)
                if not is_walkable(neighbor):
                    continue
                if dx and dy and (not is_walkable((current[0] + dx, current[1])) or not is_walkable((current[0], current[1] + dy))):
                    continue
                next_cost = cost + step_cost
                if next_cost >= distances.get(neighbor, float("inf")):
                    continue
                distances[neighbor] = next_cost
                previous[neighbor] = current
                px, py = point(neighbor)
                estimate = math.hypot(px - x2, py - y2)
                heapq.heappush(queue, (next_cost + estimate, next_cost, neighbor))

        if goal_cell not in previous and start_cell != goal_cell:
            return []

        curr = goal_cell
        cells = []
        while curr != start_cell:
            cells.append(curr)
            curr = previous[curr]
        cells.reverse()
        return [point(c) for c in cells]