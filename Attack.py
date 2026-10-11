"""Compatibility launcher for the modular RTS game."""
import argparse

from our_land.audio.synthesizer import make_sound
from our_land.config.balance import (
    BUILD_HP,
    BUILD_SIZE,
    COST_ARMOR,
    COST_BASE,
    COST_TANK,
    COST_TOWER,
    COST_WORKER,
    MAX_PRODUCTION_QUEUE,
    REPAIR_RATE,
    UNIT_BUILD_TIME,
)
from our_land.config.settings import *
from our_land.game import RTSGame
from our_land.models.building import Building
from our_land.models.unit import Unit
from our_land.rendering.procedural_renderer import (
    _rot,
    draw_armor_factory,
    draw_excavator,
    draw_hq,
    draw_tank,
    draw_tower,
)
from our_land.world.map_data import Bridge, Mountain, ResourceNode, River

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="钢河前线 RTS")
    parser.add_argument("--map", dest="map_path", help="要加载的 JSON 地图路径")
    args = parser.parse_args()
    RTSGame(map_path=args.map_path).run()
