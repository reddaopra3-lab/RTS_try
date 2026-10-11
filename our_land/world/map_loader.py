"""Load, validate, and save the game's JSON map format."""
import json
import math
import os
from pathlib import Path
from typing import Any, Dict

from ..config.settings import HEIGHT, WIDTH
from ..models.building import Building
from ..models.unit import Unit
from .map_data import Bridge, Mountain, ResourceNode, River

DEFAULT_MAP_PATH = Path(__file__).resolve().parents[2] / "maps" / "skirmish.json"
MAPS_DIRECTORY = DEFAULT_MAP_PATH.parent
_TEAMS = {"player", "enemy"}
_BUILDINGS = {"base", "armor", "tower"}
_UNITS = {"worker", "soldier"}
_TERRAIN = {
    "rivers": River,
    "bridges": Bridge,
    "mountains": Mountain,
}


def validate_map(data: Any) -> Dict[str, Any]:
    """Validate map data and return it unchanged, raising ValueError on bad input."""
    if not isinstance(data, dict):
        raise ValueError("地图根节点必须是 JSON 对象")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("不支持的地图版本（当前仅支持 version 1）")
    width = data.get("width")
    height = data.get("height")
    if (
        isinstance(width, bool) or not isinstance(width, int)
        or isinstance(height, bool) or not isinstance(height, int)
        or not WIDTH <= width <= 20000
        or not HEIGHT <= height <= 20000
    ):
        raise ValueError(f"地图尺寸必须在 {WIDTH}×{HEIGHT} 至 20000×20000 之间")

    terrain = data.get("terrain")
    if not isinstance(terrain, dict):
        raise ValueError("terrain 必须是对象")

    def number(value, label):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} 必须是数字")
        if not math.isfinite(value):
            raise ValueError(f"{label} 必须是有限数字")
        return value

    def position(item, label):
        if not isinstance(item, dict):
            raise ValueError(f"{label} 必须是对象")
        x = number(item.get("x"), f"{label}.x")
        y = number(item.get("y"), f"{label}.y")
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError(f"{label} 坐标超出地图边界")
        return x, y

    for name in _TERRAIN:
        features = terrain.get(name)
        if not isinstance(features, list):
            raise ValueError(f"terrain.{name} 必须是数组")
        for index, feature in enumerate(features):
            label = f"terrain.{name}[{index}]"
            if not isinstance(feature, dict):
                raise ValueError(f"{label} 必须是对象")
            if "points" in feature:
                points = feature["points"]
                if not isinstance(points, list) or len(points) < 3:
                    raise ValueError(f"{label}.points 至少需要三个顶点")
                for point_index, point in enumerate(points):
                    if not isinstance(point, (list, tuple)) or len(point) != 2:
                        raise ValueError(f"{label}.points[{point_index}] 必须是 [x, y]")
                    px = number(point[0], f"{label}.points[{point_index}].x")
                    py = number(point[1], f"{label}.points[{point_index}].y")
                    if not 0 <= px <= width or not 0 <= py <= height:
                        raise ValueError(f"{label}.points[{point_index}] 超出地图边界")
                area = abs(sum(
                    point[0] * points[(index + 1) % len(points)][1]
                    - points[(index + 1) % len(points)][0] * point[1]
                    for index, point in enumerate(points)
                ))
                if area == 0:
                    raise ValueError(f"{label}.points 不能共线")
            else:
                x, y = position(feature, label)
                feature_width = number(feature.get("w"), f"{label}.w")
                feature_height = number(feature.get("h"), f"{label}.h")
                if feature_width <= 0 or feature_height <= 0:
                    raise ValueError(f"{label} 的宽度和高度必须大于 0")
                if x + feature_width > width or y + feature_height > height:
                    raise ValueError(f"{label} 超出地图边界")

    resources = data.get("resources")
    buildings = data.get("buildings")
    units = data.get("units")
    for name, items in (("resources", resources), ("buildings", buildings), ("units", units)):
        if not isinstance(items, list):
            raise ValueError(f"{name} 必须是数组")
        for index, item in enumerate(items):
            label = f"{name}[{index}]"
            x, y = position(item, label)
            if name == "resources":
                if number(item.get("amount"), f"{label}.amount") <= 0:
                    raise ValueError(f"{label}.amount 必须大于 0")
                continue
            team = item.get("team")
            if not isinstance(team, str) or team not in _TEAMS:
                raise ValueError(f"{label}.team 必须是 player 或 enemy")
            valid_types = _BUILDINGS if name == "buildings" else _UNITS
            type_key = "type"
            item_type = item.get(type_key)
            if not isinstance(item_type, str) or item_type not in valid_types:
                raise ValueError(f"{label}.type 无效")

    for team in _TEAMS:
        if not any(b["team"] == team and b["type"] == "base" for b in buildings):
            raise ValueError(f"地图必须至少包含一个 {team} 基地")

    return data


def load_map(path=DEFAULT_MAP_PATH) -> Dict[str, Any]:
    """Read and validate a map from disk."""
    map_path = Path(path)
    try:
        with map_path.open("r", encoding="utf-8") as map_file:
            data = json.load(map_file)
    except json.JSONDecodeError as error:
        raise ValueError(f"地图 JSON 格式错误: {map_path} ({error})") from error
    return validate_map(data)


def list_maps(directory=MAPS_DIRECTORY):
    """Return available JSON map files in display order."""
    return sorted(Path(directory).glob("*.json"), key=lambda path: path.name.casefold())


def save_map(path, data: Dict[str, Any]) -> None:
    """Validate and atomically write a map as UTF-8 JSON."""
    validate_map(data)
    map_path = Path(path)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = map_path.with_name(map_path.name + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as map_file:
            json.dump(data, map_file, ensure_ascii=False, indent=2)
            map_file.write("\n")
        os.replace(temporary_path, map_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def apply_map(game, data: Dict[str, Any]) -> None:
    """Populate a game instance from previously validated map data."""
    game.map_width = data["width"]
    game.map_height = data["height"]
    for name in ("rivers", "bridges", "mountains", "resource_nodes", "buildings", "units"):
        getattr(game, name).clear()

    for name, model in _TERRAIN.items():
        for feature in data["terrain"][name]:
            if "points" in feature:
                terrain = model(points=feature["points"])
            else:
                terrain = model(feature["x"], feature["y"], feature["w"], feature["h"])
            getattr(game, name).append(terrain)
    for resource in data["resources"]:
        game.resource_nodes.append(ResourceNode(resource["x"], resource["y"], resource["amount"]))
    for building in data["buildings"]:
        game.buildings.append(Building(building["x"], building["y"], building["team"], building["type"]))
    for unit in data["units"]:
        game.units.append(Unit(unit["x"], unit["y"], unit["team"], unit["type"]))


def setup_map(game, map_path=None) -> None:
    data = load_map(map_path or DEFAULT_MAP_PATH)
    apply_map(game, data)
