"""Resource gathering and unit production logic."""
from ..config.balance import (
    COST_TANK,
    COST_WORKER,
    MAX_PRODUCTION_QUEUE,
    UNIT_BUILD_TIME,
)
from ..config.balance import REPAIR_RATE
from ..config.settings import FPS


def update_worker_task(unit, game):
    if (unit.target_x - unit.x) ** 2 + (unit.target_y - unit.y) ** 2 > 25:
        return

    if unit.state == "gather" and unit.gather_target and unit.gather_target.amount > 0:
        take = min(0.3, unit.gather_target.amount, unit.carry_max - unit.carry)
        unit.gather_target.amount -= take
        unit.carry += take
        if unit.carry >= unit.carry_max or unit.gather_target.amount <= 0:
            unit._go_return(game)
    elif unit.state == "return" and unit.return_base:
        game.resources[unit.team] += unit.carry
        unit.carry = 0
        if unit.gather_target and unit.gather_target.amount > 0:
            unit.set_gather(unit.gather_target, game)
        else:
            unit.state = "idle"
    elif unit.state == "build" and unit.build_target and not unit.build_target.finished:
        unit.build_target.build_progress += 0.55
        if unit.build_target.build_progress >= 100:
            unit.build_target.finish_build()
            game.play_sound("build")
            unit.state = "idle"
            unit.build_target = None
    elif (
        unit.state == "repair"
        and unit.repair_target
        and unit.repair_target in game.buildings
        and unit.repair_target.finished
        and unit.repair_target.hp > 0
    ):
        if unit.repair_target.hp < unit.repair_target.max_hp:
            old_hp = unit.repair_target.hp
            unit.repair_target.hp = min(
                unit.repair_target.max_hp,
                unit.repair_target.hp + REPAIR_RATE,
            )
            if old_hp < unit.repair_target.max_hp <= unit.repair_target.hp:
                game.show_msg("维修完成", 45)
        else:
            unit.state = "idle"
            unit.repair_target = None
    elif unit.state == "move":
        unit.state = "idle"


def queue_unit(building, unit_type, game, count=1):
    if not building.can_produce(unit_type):
        return 0

    cost = COST_WORKER if unit_type == "worker" else COST_TANK
    added = 0
    count = min(max(0, int(count)), MAX_PRODUCTION_QUEUE - building.queued_count())
    while added < count and game.resources[building.team] >= cost:
        game.resources[building.team] -= cost
        building.production_queue.append(unit_type)
        added += 1
    if added:
        game.play_sound("click")
    return added


def update_production(building, game):
    if not building.finished or building.hp <= 0 or building.b_type == "tower":
        return
    if building.production_current is None and building.production_queue:
        building.production_current = building.production_queue.pop(0)
        building.production_progress = 0.0
        game.play_sound("train")

    if building.production_current is None:
        return

    total_frames = max(1, int(UNIT_BUILD_TIME[building.production_current] * FPS))
    building.production_progress += 1.0
    if building.production_progress >= total_frames:
        if game.spawn_produced_unit(building) is not None:
            building.production_current = None
            building.production_progress = 0.0
