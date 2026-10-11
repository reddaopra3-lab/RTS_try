"""??????????????"""
import math
import random

from ..config.settings import FPS

def attack_nearest(attacker, game):
    targets = [unit for unit in game.units if unit.team != attacker.team and unit.hp > 0]
    targets.extend(building for building in game.buildings if building.team != attacker.team and building.hp > 0)
    if not targets:
        attacker.turret = attacker.facing
        return
    nearest = min(targets, key=lambda target: math.hypot(target.x - attacker.x, target.y - attacker.y))
    distance = math.hypot(nearest.x - attacker.x, nearest.y - attacker.y)
    if distance <= attacker.attack_range:
        attacker.turret = math.atan2(nearest.y - attacker.y, nearest.x - attacker.x)
        nearest.hp -= (attacker.attack_power / FPS) * getattr(nearest, "defense_bonus", 1.0)
        if random.random() < 0.08:
            game.play_sound("hit")
    else:
        attacker.turret = attacker.facing

def fire_tower(building, game):
    if building.b_type != "tower" or not building.finished or building.hp <= 0:
        return
    targets = [unit for unit in game.units if unit.team != building.team and unit.hp > 0]
    targets.extend(target for target in game.buildings if target.team != building.team and target.hp > 0)
    if not targets:
        return
    nearest = min(targets, key=lambda target: math.hypot(target.x - building.x, target.y - building.y))
    if math.hypot(nearest.x - building.x, nearest.y - building.y) <= building.attack_range:
        building.aim = math.atan2(nearest.y - building.y, nearest.x - building.x)
        nearest.hp -= (building.attack_power / FPS) * getattr(nearest, "defense_bonus", 1.0)
        if random.random() < 0.05:
            game.play_sound("hit")
