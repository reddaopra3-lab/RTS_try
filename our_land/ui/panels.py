"""HUD panels and minimap rendering."""
import pygame

from ..config.balance import COST_TANK, COST_WORKER, MAX_PRODUCTION_QUEUE, UNIT_BUILD_TIME
from ..config.settings import (
    COLOR_ARMOR, COLOR_BUILD, COLOR_ENEMY, COLOR_PLAYER, COLOR_PROGRESS,
    COLOR_RESOURCE, COLOR_RIVER, COLOR_TEXT, COLOR_TOWER, HEIGHT, FPS,
    MINIMAP_MARGIN, MINIMAP_SIZE, WIDTH,
)

def render_production_panel(game):
    building = game.selected_building()
    if not building:
        return

    x, y, w, h = game.production_panel_rect()
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((15, 18, 24, 225))
    pygame.draw.rect(panel, (150, 160, 175), (0, 0, w, h), 2)
    game.screen.blit(panel, (x, y))

    names = {"base": "基地 / 拖拉机厂", "armor": "装甲工厂", "tower": "防御塔"}
    title = game.font.render(names.get(building.b_type, building.b_type), True, COLOR_TEXT)
    game.screen.blit(title, (x + 12, y + 10))

    if building.b_type == "tower":
        text = game.font.render("该建筑没有生产项目", True, (190, 190, 190))
        game.screen.blit(text, (x + 12, y + 46))
        return

    unit_type = "worker" if building.b_type == "base" else "soldier"
    unit_name = "挖掘机" if unit_type == "worker" else "坦克"
    cost = COST_WORKER if unit_type == "worker" else COST_TANK
    time_sec = UNIT_BUILD_TIME[unit_type]
    queued = building.queued_count()

    # 当前生产状态
    if building.production_current:
        current_name = "挖掘机" if building.production_current == "worker" else "坦克"
        total = max(1, UNIT_BUILD_TIME[building.production_current] * FPS)
        remain = max(0.0, (total - building.production_progress) / FPS)
        status = f"正在生产：{current_name}  {remain:.1f}s"
        status_color = COLOR_PROGRESS
    elif building.production_queue:
        status = "等待生产..."
        status_color = COLOR_PROGRESS
    else:
        status = "生产队列空闲"
        status_color = (180, 180, 180)
    game.screen.blit(game.font.render(status, True, status_color), (x + 12, y + 38))

    info = game.font.render(
        f"{unit_name}  |  钢铁 {cost}  |  生产时间 {time_sec:g}s  |  队列 {queued}/{MAX_PRODUCTION_QUEUE}",
        True, (210, 215, 220),
    )
    game.screen.blit(info, (x + 12, y + 64))

    for amount, rect in game.production_button_rects(building):
        can_afford = game.resources[building.team] >= cost and building.queued_count() < MAX_PRODUCTION_QUEUE
        fill = (55, 70, 90) if can_afford else (45, 45, 48)
        border = COLOR_BUILD if can_afford else (90, 90, 90)
        pygame.draw.rect(game.screen, fill, rect, border_radius=4)
        pygame.draw.rect(game.screen, border, rect, 1, border_radius=4)
        label = game.font.render(f"生产 ×{amount}", True, COLOR_TEXT if can_afford else (130, 130, 130))
        game.screen.blit(label, label.get_rect(center=rect.center))

    hint = game.font.render(
        "快捷键：W 生产挖掘机 / S 生产坦克（点击建筑自动打开）",
        True, (155, 165, 180),
    )
    game.screen.blit(hint, (x + 12, y + 159))


def render_minimap(game):
    mm_x = WIDTH - MINIMAP_SIZE - MINIMAP_MARGIN
    mm_y = HEIGHT - MINIMAP_SIZE - MINIMAP_MARGIN
    pygame.draw.rect(game.screen, (20, 24, 30), (mm_x, mm_y, MINIMAP_SIZE, MINIMAP_SIZE))
    pygame.draw.rect(game.screen, (80, 90, 100), (mm_x, mm_y, MINIMAP_SIZE, MINIMAP_SIZE), 2)

    scale_x = MINIMAP_SIZE / WIDTH
    scale_y = MINIMAP_SIZE / HEIGHT

    # 河流
    for r in game.rivers:
        pygame.draw.rect(game.screen, COLOR_RIVER,
                         (mm_x + int(r.rect.x * scale_x), mm_y + int(r.rect.y * scale_y),
                          max(2, int(r.rect.w * scale_x)), max(2, int(r.rect.h * scale_y))))

    for node in game.resource_nodes:
        px = mm_x + int(node.x * scale_x)
        py = mm_y + int(node.y * scale_y)
        pygame.draw.circle(game.screen, COLOR_RESOURCE, (px, py), 2)

    for b in game.buildings:
        px = mm_x + int(b.x * scale_x)
        py = mm_y + int(b.y * scale_y)
        color = COLOR_PLAYER if b.team == "player" else COLOR_ENEMY
        size = 5 if b.b_type == "base" else 4
        pygame.draw.rect(game.screen, color, (px - size // 2, py - size // 2, size, size))

    for u in game.units:
        px = mm_x + int(u.x * scale_x)
        py = mm_y + int(u.y * scale_y)
        color = COLOR_PLAYER if u.team == "player" else COLOR_ENEMY
        pygame.draw.circle(game.screen, color, (px, py), 2)
