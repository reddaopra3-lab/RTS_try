"""A* pathfinding that accounts for terrain and building collisions."""
import heapq
import math

from ..config.settings import HEIGHT, WIDTH

def segment_is_clear(game, x1, y1, x2, y2, radius):
    distance = math.hypot(x2 - x1, y2 - y1)
    steps = max(1, math.ceil(distance / 5))
    return all(
        not game.is_blocked(
            x1 + (x2 - x1) * i / steps,
            y1 + (y2 - y1) * i / steps,
            radius,
        )
        for i in range(1, steps + 1)
    )


def find_path(game, x1, y1, x2, y2, radius):
    cell_size = 10
    columns = math.ceil(WIDTH / cell_size)
    rows = math.ceil(HEIGHT / cell_size)
    walkable = {}

    def point(cell):
        return ((cell[0] + 0.5) * cell_size, (cell[1] + 0.5) * cell_size)

    def is_walkable(cell):
        if cell not in walkable:
            px, py = point(cell)
            walkable[cell] = (
                0 <= cell[0] < columns
                and 0 <= cell[1] < rows
                and not game.is_blocked(px, py, radius)
            )
        return walkable[cell]

    def nearby_cells(x, y, max_distance):
        center = (
            min(columns - 1, max(0, int(x / cell_size))),
            min(rows - 1, max(0, int(y / cell_size))),
        )
        cell_radius = math.ceil(max_distance / cell_size)
        candidates = []
        for cx in range(max(0, center[0] - cell_radius), min(columns, center[0] + cell_radius + 1)):
            for cy in range(max(0, center[1] - cell_radius), min(rows, center[1] + cell_radius + 1)):
                cell = (cx, cy)
                px, py = point(cell)
                distance = math.hypot(px - x, py - y)
                if distance <= max_distance and is_walkable(cell):
                    candidates.append((distance, cell))
        candidates.sort()
        return candidates

    starts = [
        cell for _, cell in nearby_cells(x1, y1, 30)
        if game._segment_is_clear(x1, y1, *point(cell), radius)
    ]
    if not starts:
        return []

    nearest_goal_cell = (
        min(columns - 1, max(0, int(x2 / cell_size))),
        min(rows - 1, max(0, int(y2 / cell_size))),
    )
    if is_walkable(nearest_goal_cell):
        goals = {nearest_goal_cell}
    else:
        goals = {
            cell for _, cell in nearby_cells(x2, y2, 50)
        }
    if not goals:
        return []

    start = starts[0]
    directions = (
        (-1, 0, 10), (1, 0, 10), (0, -1, 10), (0, 1, 10),
        (-1, -1, 14.142), (1, -1, 14.142),
        (-1, 1, 14.142), (1, 1, 14.142),
    )
    distances = {start: 0}
    previous = {}
    queue = [(math.hypot(point(start)[0] - x2, point(start)[1] - y2), 0, start)]
    visited = set()
    goal = None

    while queue:
        _, cost, current = heapq.heappop(queue)
        if current in visited:
            continue
        visited.add(current)
        if current in goals:
            goal = current
            break

        for dx, dy, step_cost in directions:
            neighbor = (current[0] + dx, current[1] + dy)
            if not is_walkable(neighbor):
                continue
            if dx and dy and (
                not is_walkable((current[0] + dx, current[1]))
                or not is_walkable((current[0], current[1] + dy))
            ):
                continue
            next_cost = cost + step_cost
            if next_cost >= distances.get(neighbor, float("inf")):
                continue
            distances[neighbor] = next_cost
            previous[neighbor] = current
            px, py = point(neighbor)
            estimate = math.hypot(px - x2, py - y2)
            heapq.heappush(queue, (next_cost + estimate, next_cost, neighbor))

    if goal is None:
        return []

    cells = []
    while goal != start:
        cells.append(goal)
        goal = previous[goal]
    cells.reverse()
    path = [point(cell) for cell in cells]
    if path and not game.is_blocked(x2, y2, radius):
        if game._segment_is_clear(*path[-1], x2, y2, radius):
            path.append((x2, y2))
    elif not path and not game.is_blocked(x2, y2, radius):
        if game._segment_is_clear(x1, y1, x2, y2, radius):
            path.append((x2, y2))
    return path


def find_path_to_building(game, x, y, building, radius):
    distance = building.size / 2 + radius + 5
    diagonal = distance * math.sqrt(2)
    approaches = (
        (building.x - distance, building.y),
        (building.x + distance, building.y),
        (building.x, building.y - distance),
        (building.x, building.y + distance),
        (building.x - diagonal, building.y - diagonal),
        (building.x + diagonal, building.y - diagonal),
        (building.x - diagonal, building.y + diagonal),
        (building.x + diagonal, building.y + diagonal),
    )
    paths = [
        path for tx, ty in approaches
        if not game.is_blocked(tx, ty, radius)
        and (path := game.find_path(x, y, tx, ty, radius))
    ]
    return min(
        paths,
        key=lambda path: sum(
            math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
            for i in range(1, len(path))
        ) + math.hypot(path[0][0] - x, path[0][1] - y),
        default=[],
    )
