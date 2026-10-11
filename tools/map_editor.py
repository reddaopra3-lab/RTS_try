"""Keyboard-driven editor for the game's JSON skirmish maps."""
import argparse
import math
from pathlib import Path
import sys

import pygame

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from our_land.config.settings import (
    COLOR_BG,
    HEIGHT,
    WIDTH,
)
from our_land.models.building import Building
from our_land.models.unit import Unit
from our_land.world.map_data import (
    Bridge,
    Mountain,
    ResourceNode,
    River,
    distance_to_segment,
    point_in_polygon,
)
from our_land.world.map_loader import DEFAULT_MAP_PATH, load_map, save_map, validate_map

MAPS_DIR = PROJECT_ROOT / "maps"
PANEL_WIDTH = 300
MODES = {
    pygame.K_1: ("river", "河流"),
    pygame.K_2: ("bridge", "桥"),
    pygame.K_3: ("mountain", "山地"),
    pygame.K_4: ("resource", "矿点"),
    pygame.K_5: ("base", "基地"),
    pygame.K_6: ("worker", "挖掘机"),
    pygame.K_7: ("soldier", "坦克"),
    pygame.K_8: ("armor", "装甲工厂"),
    pygame.K_9: ("tower", "防御塔"),
}
NEW_MAP_WIDTH = 4000
NEW_MAP_HEIGHT = 3000
EDITOR_MINIMAP_SIZE = 180
EDITOR_MINIMAP_MARGIN = 15


def map_path_from_name(name):
    path = (MAPS_DIR / name).resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("地图文件必须使用 .json 扩展名")
    if not path.is_relative_to(MAPS_DIR.resolve()):
        raise ValueError("地图只能保存在 maps 文件夹中")
    return path


def _map_entities(data):
    terrain = data["terrain"]
    return {
        "river": terrain["rivers"],
        "bridge": terrain["bridges"],
        "mountain": terrain["mountains"],
        "resource": data["resources"],
        "building": data["buildings"],
        "unit": data["units"],
    }


def new_map_data(width=NEW_MAP_WIDTH, height=NEW_MAP_HEIGHT):
    return {
        "version": 1,
        "width": width,
        "height": height,
        "terrain": {"rivers": [], "bridges": [], "mountains": []},
        "resources": [],
        "buildings": [
            {"x": 200, "y": height / 2, "team": "player", "type": "base"},
            {"x": width - 200, "y": height / 2, "team": "enemy", "type": "base"},
        ],
        "units": [
            {"x": 270, "y": height / 2 - 40, "team": "player", "type": "worker"},
            {"x": width - 270, "y": height / 2 - 40, "team": "enemy", "type": "worker"},
        ],
    }


def _terrain_points(feature):
    if "points" in feature:
        return feature["points"]
    x, y, width, height = feature["x"], feature["y"], feature["w"], feature["h"]
    return [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]


def _remove_at(data, x, y):
    for unit in reversed(data["units"]):
        if math.hypot(unit["x"] - x, unit["y"] - y) <= 20:
            data["units"].remove(unit)
            return True

    for building in reversed(data["buildings"]):
        if (
            abs(building["x"] - x) <= 30
            and abs(building["y"] - y) <= 30
        ):
            data["buildings"].remove(building)
            return True

    for resource in reversed(data["resources"]):
        if math.hypot(resource["x"] - x, resource["y"] - y) <= 26:
            data["resources"].remove(resource)
            return True

    terrain = data["terrain"]
    for key in ("bridges", "rivers", "mountains"):
        for feature in reversed(terrain[key]):
            points = _terrain_points(feature)
            if point_in_polygon(x, y, points) or any(
                distance_to_segment(x, y, points[index - 1], point) <= 5
                for index, point in enumerate(points)
            ):
                terrain[key].remove(feature)
                return True
    return False


class MapEditor:
    def __init__(self, map_path):
        self.map_path = map_path
        self.data = load_map(map_path)
        self.mode = "river"
        self.team = "player"
        self.polygon_points = []
        self.message = ""
        self.message_timer = 0
        self.save_as_active = False
        self.save_as_name = ""

        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH + PANEL_WIDTH, HEIGHT))
        pygame.display.set_caption("钢河前线 - 地图编辑器")
        self.font = pygame.font.SysFont("microsoftyahei,simhei,arial", 18)
        self.small_font = pygame.font.SysFont("microsoftyahei,simhei,arial", 15)
        self.clock = pygame.time.Clock()
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.camera_drag = None
        player_base = next(
            (building for building in self.data["buildings"] if building["team"] == "player" and building["type"] == "base"),
            None,
        )
        if player_base:
            self.center_camera(player_base["x"], player_base["y"])

    def clamp_camera(self):
        self.camera_x = max(0, min(self.camera_x, self.data["width"] - WIDTH))
        self.camera_y = max(0, min(self.camera_y, self.data["height"] - HEIGHT))

    def center_camera(self, world_x, world_y):
        self.camera_x = world_x - WIDTH / 2
        self.camera_y = world_y - HEIGHT / 2
        self.clamp_camera()

    def screen_to_world(self, screen_x, screen_y):
        return screen_x + self.camera_x, screen_y + self.camera_y

    def editor_minimap_rect(self):
        return pygame.Rect(
            WIDTH - EDITOR_MINIMAP_SIZE - EDITOR_MINIMAP_MARGIN,
            HEIGHT - EDITOR_MINIMAP_SIZE - EDITOR_MINIMAP_MARGIN,
            EDITOR_MINIMAP_SIZE,
            EDITOR_MINIMAP_SIZE,
        )

    def resize_map(self, width_delta=0, height_delta=0):
        old_width, old_height = self.data["width"], self.data["height"]
        self.data["width"] = max(WIDTH, min(20000, old_width + width_delta))
        self.data["height"] = max(HEIGHT, min(20000, old_height + height_delta))
        try:
            validate_map(self.data)
        except ValueError as error:
            self.data["width"], self.data["height"] = old_width, old_height
            self.show_message(f"无法缩小地图: {error}")
            return
        self.clamp_camera()
        self.show_message(f"地图尺寸: {self.data['width']} × {self.data['height']}")

    def show_message(self, text):
        self.message = text
        self.message_timer = 180

    def place_at(self, x, y):
        entities = _map_entities(self.data)
        if self.mode in {"river", "bridge", "mountain"}:
            self.polygon_points.append((round(x), round(y)))
        elif self.mode == "resource":
            entities["resource"].append({"x": x, "y": y, "amount": 1000})
        elif self.mode in {"base", "armor", "tower"}:
            entities["building"].append({"x": x, "y": y, "team": self.team, "type": self.mode})
        else:
            unit_type = "worker" if self.mode == "worker" else "soldier"
            entities["unit"].append({"x": x, "y": y, "team": self.team, "type": unit_type})

    def save(self):
        if self.map_path is None:
            self.begin_save_as()
            return
        save_map(self.map_path, self.data)
        self.show_message(f"已保存: {self.map_path.name}")

    def begin_save_as(self):
        self.save_as_active = True
        self.save_as_name = ""
        pygame.key.start_text_input()
        self.show_message("输入新地图文件名，然后按 Enter 保存")

    def finish_save_as(self):
        name = self.save_as_name.strip()
        if not name:
            self.show_message("文件名不能为空")
            return
        if not name.lower().endswith(".json"):
            name += ".json"
        path = map_path_from_name(name)
        if path.exists() and path != self.map_path:
            raise FileExistsError(f"{path.name} 已存在；请换一个文件名")
        save_map(path, self.data)
        self.map_path = path
        pygame.display.set_caption(f"钢河前线 - 地图编辑器 - {path.name}")
        self.show_message(f"已另存为: {path.name}")

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if self.save_as_active:
            if event.type == pygame.TEXTINPUT:
                self.save_as_name = (self.save_as_name + event.text)[:64]
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.save_as_active = False
                    pygame.key.stop_text_input()
                    self.show_message("已取消另存为")
                elif event.key == pygame.K_BACKSPACE:
                    self.save_as_name = self.save_as_name[:-1]
                elif event.key == pygame.K_RETURN:
                    try:
                        self.finish_save_as()
                    except (OSError, ValueError) as error:
                        self.show_message(f"另存失败: {error}")
                    else:
                        self.save_as_active = False
                        pygame.key.stop_text_input()
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.polygon_points:
                    self.polygon_points.clear()
                    self.show_message("已取消当前多边形")
                else:
                    return False
            if event.key in MODES:
                self.mode = MODES[event.key][0]
            elif event.key == pygame.K_TAB:
                self.team = "enemy" if self.team == "player" else "player"
            elif event.key == pygame.K_RETURN and self.mode in {"river", "bridge", "mountain"}:
                if len(self.polygon_points) >= 3:
                    key = {"river": "rivers", "bridge": "bridges", "mountain": "mountains"}[self.mode]
                    self.data["terrain"][key].append({
                        "points": [[x, y] for x, y in self.polygon_points]
                    })
                    self.polygon_points.clear()
                    self.show_message("多边形地形已放置")
                else:
                    self.show_message("多边形至少需要三个顶点；左键继续添加")
            elif event.key == pygame.K_BACKSPACE and self.polygon_points:
                self.polygon_points.pop()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                if getattr(event, "mod", pygame.key.get_mods()) & pygame.KMOD_CTRL:
                    if event.key == pygame.K_LEFT:
                        self.resize_map(width_delta=-1000)
                    elif event.key == pygame.K_RIGHT:
                        self.resize_map(width_delta=1000)
                    elif event.key == pygame.K_UP:
                        self.resize_map(height_delta=-1000)
                    else:
                        self.resize_map(height_delta=1000)
                else:
                    if event.key == pygame.K_LEFT:
                        self.camera_x -= 80
                    elif event.key == pygame.K_RIGHT:
                        self.camera_x += 80
                    elif event.key == pygame.K_UP:
                        self.camera_y -= 80
                    else:
                        self.camera_y += 80
                    self.clamp_camera()
            elif event.key == pygame.K_n and pygame.key.get_mods() & pygame.KMOD_CTRL:
                self.data = new_map_data()
                self.map_path = None
                self.polygon_points.clear()
                self.camera_x = 0
                self.camera_y = (self.data["height"] - HEIGHT) / 2
                pygame.display.set_caption("钢河前线 - 地图编辑器 - 未命名地图")
                self.show_message("已新建空白地图；使用 F2 或 Ctrl+Shift+S 另存为")
            elif event.key == pygame.K_F2 or (
                event.key == pygame.K_s
                and pygame.key.get_mods() & pygame.KMOD_CTRL
                and pygame.key.get_mods() & pygame.KMOD_SHIFT
            ):
                self.begin_save_as()
            elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                try:
                    self.save()
                except (OSError, ValueError) as error:
                    self.show_message(f"保存失败: {error}")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self.camera_drag = (event.pos, self.camera_x, self.camera_y)
        elif event.type == pygame.MOUSEMOTION and self.camera_drag:
            start_pos, start_x, start_y = self.camera_drag
            self.camera_x = start_x - (event.pos[0] - start_pos[0])
            self.camera_y = start_y - (event.pos[1] - start_pos[1])
            self.clamp_camera()
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.camera_drag = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.pos[0] < WIDTH and event.pos[1] < HEIGHT:
            if self.editor_minimap_rect().collidepoint(event.pos):
                minimap = self.editor_minimap_rect()
                self.center_camera(
                    (event.pos[0] - minimap.x) / EDITOR_MINIMAP_SIZE * self.data["width"],
                    (event.pos[1] - minimap.y) / EDITOR_MINIMAP_SIZE * self.data["height"],
                )
                return True
            x, y = self.screen_to_world(*event.pos)
            if event.button == 1:
                self.place_at(x, y)
            elif event.button == 3:
                self.show_message("已删除对象" if _remove_at(self.data, x, y) else "此处没有可删除对象")
        return True

    def draw(self):
        self.screen.fill(COLOR_BG)
        camera = (self.camera_x, self.camera_y)
        for feature in self.data["terrain"]["mountains"]:
            Mountain(points=_terrain_points(feature)).draw(self.screen, camera)
        for feature in self.data["terrain"]["rivers"]:
            River(points=_terrain_points(feature)).draw(self.screen, camera)
        for feature in self.data["terrain"]["bridges"]:
            Bridge(points=_terrain_points(feature)).draw(self.screen, camera)
        for resource in self.data["resources"]:
            ResourceNode(resource["x"], resource["y"], resource["amount"]).draw(self.screen, camera)
        for building in self.data["buildings"]:
            Building(building["x"], building["y"], building["team"], building["type"]).draw(self.screen, camera)
        for unit in self.data["units"]:
            Unit(unit["x"], unit["y"], unit["team"], unit["type"]).draw(self.screen, camera)

        if self.polygon_points:
            points = [(x - self.camera_x, y - self.camera_y) for x, y in self.polygon_points]
            mouse_x, mouse_y = pygame.mouse.get_pos()
            if mouse_x < WIDTH and mouse_y < HEIGHT:
                points.append((mouse_x, mouse_y))
            if len(points) > 1:
                pygame.draw.lines(self.screen, (255, 235, 120), False, points, 2)
            for point in points[:-1]:
                pygame.draw.circle(self.screen, (255, 235, 120), (round(point[0]), round(point[1])), 4)

        panel = pygame.Rect(WIDTH, 0, PANEL_WIDTH, HEIGHT)
        pygame.draw.rect(self.screen, (20, 24, 31), panel)
        lines = [
            "地图编辑器",
            self.map_path.name if self.map_path else "未命名地图",
            "",
            f"当前工具: {dict((value[0], value[1]) for value in MODES.values())[self.mode]}",
            f"当前阵营: {'玩家' if self.team == 'player' else '敌方'} (Tab切换)",
            "",
            "1 河流      2 桥梁",
            "3 山地      4 矿点",
            "5 基地      6 挖掘机",
            "7 坦克      8 装甲工厂",
            "9 防御塔",
            "",
            "地形: 左键添加顶点",
            "Enter: 完成多边形",
            "Backspace: 撤销顶点",
            "右键: 删除对象",
            "中键拖动/方向键: 移动视野",
            "Ctrl+方向键: 调整地图大小",
            "点击小地图: 跳转",
            "Ctrl+S: 保存地图",
            "F2 / Ctrl+Shift+S: 另存为",
            "Ctrl+N: 新建地图",
            "Esc: 退出",
            "",
            f"地图: {self.data['width']} × {self.data['height']}",
            f"视野: ({int(self.camera_x)}, {int(self.camera_y)})",
            f"地形: {sum(len(self.data['terrain'][key]) for key in ('rivers', 'bridges', 'mountains'))}",
            f"矿点: {len(self.data['resources'])}",
            f"建筑: {len(self.data['buildings'])}",
            f"单位: {len(self.data['units'])}",
        ]
        for index, line in enumerate(lines):
            color = (230, 230, 230) if index < 2 else (175, 185, 200)
            surface = (self.font if index == 0 else self.small_font).render(line, True, color)
            self.screen.blit(surface, (WIDTH + 16, 16 + index * 29))
        self.draw_minimap()
        if self.save_as_active:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            self.screen.blit(overlay, (0, 0))
            prompt = self.font.render("另存为地图 (maps 文件夹)", True, (255, 255, 255))
            self.screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 24)))
            name = self.save_as_name + ("|" if pygame.time.get_ticks() // 500 % 2 == 0 else "")
            entry = self.font.render(name, True, (255, 220, 100))
            self.screen.blit(entry, entry.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 18)))
        if self.message_timer:
            text = self.small_font.render(self.message, True, (255, 220, 100))
            self.screen.blit(text, (WIDTH + 16, HEIGHT - 38))
            self.message_timer -= 1
        pygame.display.flip()

    def draw_minimap(self):
        rect = self.editor_minimap_rect()
        pygame.draw.rect(self.screen, (20, 24, 30), rect)
        scale_x = EDITOR_MINIMAP_SIZE / self.data["width"]
        scale_y = EDITOR_MINIMAP_SIZE / self.data["height"]
        self.screen.set_clip(rect)
        for key, color in (
            ("mountains", (100, 80, 60)),
            ("rivers", (40, 100, 180)),
            ("bridges", (145, 110, 70)),
        ):
            for feature in self.data["terrain"][key]:
                points = [
                    (
                        rect.x + round(point[0] * scale_x),
                        rect.y + round(point[1] * scale_y),
                    )
                    for point in _terrain_points(feature)
                ]
                pygame.draw.polygon(self.screen, color, points)
        for building in self.data["buildings"]:
            color = (65, 145, 245) if building["team"] == "player" else (230, 75, 75)
            point = (
                rect.x + round(building["x"] * scale_x),
                rect.y + round(building["y"] * scale_y),
            )
            pygame.draw.circle(self.screen, color, point, 3)
        for unit in self.data["units"]:
            color = (65, 145, 245) if unit["team"] == "player" else (230, 75, 75)
            point = (
                rect.x + round(unit["x"] * scale_x),
                rect.y + round(unit["y"] * scale_y),
            )
            pygame.draw.circle(self.screen, color, point, 2)
        viewport = pygame.Rect(
            rect.x + round(self.camera_x * scale_x),
            rect.y + round(self.camera_y * scale_y),
            max(2, round(WIDTH * scale_x)),
            max(2, round(HEIGHT * scale_y)),
        )
        pygame.draw.rect(self.screen, (235, 235, 235), viewport, 1)
        self.screen.set_clip(None)
        pygame.draw.rect(self.screen, (160, 170, 185), rect, 1)

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                running = self.handle_event(event) and running
            self.draw()
            self.clock.tick(60)
        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="创建并编辑钢河前线的 JSON 地图")
    parser.add_argument("--map", default=DEFAULT_MAP_PATH.name, help="maps 文件夹中的地图文件名")
    args = parser.parse_args()
    MapEditor(map_path_from_name(args.map)).run()


if __name__ == "__main__":
    main()
