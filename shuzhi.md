from typing import Dict

COST_WORKER: int = 50
COST_TANK: int = 80
COST_BASE: int = 150
COST_ARMOR: int = 140
COST_TOWER: int = 70

BUILD_SIZE: Dict[str, int] = {"base": 54, "armor": 50, "tower": 38}
BUILD_HP: Dict[str, float] = {"base": 700.0, "armor": 520.0, "tower": 380.0}

UNIT_BUILD_TIME: Dict[str, float] = {"worker": 2.5, "soldier": 4.0}
MAX_PRODUCTION_QUEUE: int = 12
REPAIR_RATE: float = 1.2