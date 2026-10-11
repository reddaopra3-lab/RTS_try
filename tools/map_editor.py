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
from our_land.world.map_data import Bridge, Mountain, ResourceNode, River
from our_land.world.map_loader import DEFAULT_MAP_PATH, load_map, save_map

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


def new_map_data():
    return {
        "version": 1,
        "width": WIDTH,
        "height": HEIGHT,
        "terrain": {"rivers": [], "bridges": [], "mountains": []},
        "resources": [],
        "buildings": [
            {"x": 140, "y": HEIGHT / 2, "team": "player", "type": "base"},
            {"x": WIDTH - 140, "y": HEIGHT / 2, "team": "enemy", "type": "base"},
        ],
        "units": [
            {"x": 210, "y": HEIGHT / 2 - 40, "team": "player", "type": "worker"},
            {"x": WIDTH - 210, "y": HEIGHT / 2 - 40, "team": "enemy", "type": "worker"},
        ],
    }


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
            if (
                feature["x"] <= x <= feature["x"] + feature["w"]
                and feature["y"] <= y <= feature["y"] + feature["h"]
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
        self.terrain_size = {"river": [50, 180], "bridge": [90, 40], "mountain": [140, 110]}
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

    def show_message(self, text):
        self.message = text
        self.message_timer = 180

    def place_at(self, x, y):
        entities = _map_entities(self.data)
        if self.mode in self.terrain_size:
            width, height = self.terrain_size[self.mode]
            x = min(max(width / 2, x), WIDTH - width / 2)
            y = min(max(height / 2, y), HEIGHT - height / 2)
            key = {"river": "rivers", "bridge": "bridges", "mountain": "mountains"}[self.mode]
            entities[self.mode].append({"x": x - width / 2, "y": y - height / 2, "w": width, "h": height})
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
                return False
            if event.key in MODES:
                self.mode = MODES[event.key][0]
            elif event.key == pygame.K_TAB:
                self.team = "enemy" if self.team == "player" else "player"
            elif event.key == pygame.K_n and pygame.key.get_mods() & pygame.KMOD_CTRL:
                self.data = new_map_data()
                self.map_path = None
                pygame.display.set_caption("钢河前线 - 地图编辑器 - 未命名地图")
                self.show_message("已新建空白地图；使用 F2 或 Ctrl+Shift+S 另存为")
            elif event.key == pygame.K_F2 or (
                event.key == pygame.K_s
                and pygame.key.get_mods() & pygame.KMOD_CTRL
                and pygame.key.get_mods() & pygame.KMOD_SHIFT
            ):
                self.begin_save_as()
            elif event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET) and self.mode in self.terrain_size:
                delta = -10 if event.key == pygame.K_LEFTBRACKET else 10
                size = self.terrain_size[self.mode]
                size[0] = max(20, size[0] + delta)
                size[1] = max(20, size[1] + delta)
            elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                try:
                    self.save()
                except (OSError, ValueError) as error:
                    self.show_message(f"保存失败: {error}")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.pos[0] < WIDTH and event.pos[1] < HEIGHT:
            x, y = event.pos
            if event.button == 1:
                self.place_at(x, y)
            elif event.button == 3:
                self.show_message("已删除对象" if _remove_at(self.data, x, y) else "此处没有可删除对象")
        return True

    def draw(self):
        self.screen.fill(COLOR_BG)
        for feature in self.data["terrain"]["mountains"]:
            Mountain(feature["x"], feature["y"], feature["w"], feature["h"]).draw(self.screen)
        for feature in self.data["terrain"]["rivers"]:
            River(feature["x"], feature["y"], feature["w"], feature["h"]).draw(self.screen)
        for feature in self.data["terrain"]["bridges"]:
            Bridge(feature["x"], feature["y"], feature["w"], feature["h"]).draw(self.screen)
        for resource in self.data["resources"]:
            ResourceNode(resource["x"], resource["y"], resource["amount"]).draw(self.screen)
        for building in self.data["buildings"]:
            Building(building["x"], building["y"], building["team"], building["type"]).draw(self.screen)
        for unit in self.data["units"]:
            Unit(unit["x"], unit["y"], unit["team"], unit["type"]).draw(self.screen)

        panel = pygame.Rect(WIDTH, 0, PANEL_WIDTH, HEIGHT)
        pygame.draw.rect(self.screen, (20, 24, 31), panel)
        lines = [
            "地图编辑器",
            self.map_path.name,
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
            "左键: 放置",
            "右键: 删除",
            "[ / ]: 调整地形尺寸",
            "Ctrl+S: 保存地图",
            "F2 / Ctrl+Shift+S: 另存为",
            "Ctrl+N: 新建地图",
            "Esc: 退出",
            "",
            f"地形: {sum(len(self.data['terrain'][key]) for key in ('rivers', 'bridges', 'mountains'))}",
            f"矿点: {len(self.data['resources'])}",
            f"建筑: {len(self.data['buildings'])}",
            f"单位: {len(self.data['units'])}",
        ]
        for index, line in enumerate(lines):
            color = (230, 230, 230) if index < 2 else (175, 185, 200)
            surface = (self.font if index == 0 else self.small_font).render(line, True, color)
            self.screen.blit(surface, (WIDTH + 16, 16 + index * 29))
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
