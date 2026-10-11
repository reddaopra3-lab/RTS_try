from typing import List, Tuple

class UnitModel:
    """单位领域模型，仅维护单位物理状态与业务属性"""
    def __init__(self, x: float, y: float, team: str = "player", unit_type: str = "worker"):
        self.x: float = float(x)
        self.y: float = float(y)
        self.target_x: float = self.x
        self.target_y: float = self.y
        self.team: str = team
        self.unit_type: str = unit_type
        
        self.base_speed: float = 2.6 if unit_type == "worker" else 2.0
        self.speed: float = self.base_speed
        self.hp: float = 50.0 if unit_type == "worker" else 100.0
        self.max_hp: float = self.hp
        self.attack_power: float = 2.0 if unit_type == "worker" else 8.5
        self.attack_range: float = 160.0 if unit_type == "soldier" else 28.0
        self.radius: float = 11.0 if unit_type == "worker" else 13.0
        
        self.selected: bool = False
        self.defense_bonus: float = 1.0
        self.facing: float = 0.0
        self.turret: float = 0.0
        self.state: str = "idle"
        
        self.carry: float = 0.0
        self.carry_max: float = 12.0
        
        self.gather_target = None
        self.return_base = None
        self.build_target = None
        self.repair_target = None
        self.path: List[Tuple[float, float]] = []

    def set_path(self, path: List[Tuple[float, float]]) -> None:
        self.path = path
        if self.path:
            self.target_x, self.target_y = self.path[-1]
        else:
            self.target_x, self.target_y = self.x, self.y
            self.state = "idle"

    def is_alive(self) -> bool:
        return self.hp > 0