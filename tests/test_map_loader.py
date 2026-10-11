import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pygame

from tools.map_editor import MapEditor, _remove_at, map_path_from_name, new_map_data
from our_land.game import RTSGame
from our_land.world.map_data import Bridge, Mountain, River
from our_land.world.map_loader import DEFAULT_MAP_PATH, apply_map, list_maps, load_map, save_map


class MapLoaderTests(unittest.TestCase):
    def test_default_map_loads_and_populates_game(self):
        data = load_map()
        game = SimpleNamespace(
            rivers=[], bridges=[], mountains=[], resource_nodes=[], buildings=[], units=[]
        )

        apply_map(game, data)

        self.assertEqual(len(game.rivers), len(data["terrain"]["rivers"]))
        self.assertEqual(len(game.bridges), len(data["terrain"]["bridges"]))
        self.assertEqual(len(game.mountains), len(data["terrain"]["mountains"]))
        self.assertEqual(len(game.buildings), len(data["buildings"]))
        self.assertEqual(len(game.units), len(data["units"]))
        self.assertEqual(len(game.resource_nodes), len(data["resources"]))
        self.assertEqual({building.team for building in game.buildings}, {"player", "enemy"})

    def test_save_and_load_round_trip(self):
        data = load_map(DEFAULT_MAP_PATH)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "round-trip.json"
            save_map(path, data)
            self.assertEqual(load_map(path), data)

    def test_invalid_map_is_rejected_without_overwriting_existing_file(self):
        data = copy.deepcopy(load_map())
        data["buildings"] = [building for building in data["buildings"] if building["team"] != "enemy"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.json"
            path.write_text('{"keep": true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "enemy 基地"):
                save_map(path, data)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"keep": True})

    def test_invalid_json_reports_a_value_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON 格式错误"):
                load_map(path)

    def test_editor_places_and_removes_selected_objects(self):
        editor = MapEditor.__new__(MapEditor)
        editor.data = copy.deepcopy(load_map())
        editor.mode = "soldier"
        editor.team = "enemy"

        editor.place_at(500, 350)

        self.assertEqual(editor.data["units"][-1], {
            "x": 500, "y": 350, "team": "enemy", "type": "soldier"
        })
        self.assertTrue(_remove_at(editor.data, 500, 350))
        self.assertEqual(len(editor.data["units"]), 6)

    def test_editor_restricts_map_paths_to_maps_directory(self):
        self.assertEqual(map_path_from_name("skirmish.json"), DEFAULT_MAP_PATH)
        with self.assertRaisesRegex(ValueError, "maps 文件夹"):
            map_path_from_name("..\\outside.json")
        with self.assertRaisesRegex(ValueError, r"\.json"):
            map_path_from_name("readme.txt")

    def test_map_list_includes_all_json_maps_in_stable_order(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "Zulu.json").touch()
            Path(directory, "alpha.json").touch()
            Path(directory, "notes.txt").touch()

            self.assertEqual([path.name for path in list_maps(directory)], ["alpha.json", "Zulu.json"])

    def test_main_menu_starts_the_selected_map(self):
        game = RTSGame.__new__(RTSGame)
        game.map_paths = [Path("first.json"), Path("second.json")]
        game.selected_map_index = 1
        game.menu_active = True
        game.menu_error = ""
        game.game_over = True
        game.winner = "enemy"
        game.enemy_timer = 99
        game.setup_map = Mock()

        self.assertTrue(game.handle_menu_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)))

        game.setup_map.assert_called_once_with(Path("second.json"))
        self.assertFalse(game.menu_active)
        self.assertFalse(game.game_over)
        self.assertIsNone(game.winner)
        self.assertEqual(game.enemy_timer, 0)

    def test_new_editor_map_starts_with_both_teams_and_can_be_saved_as(self):
        data = new_map_data()
        self.assertEqual((data["width"], data["height"]), (4000, 3000))
        self.assertEqual(
            {building["team"] for building in data["buildings"]},
            {"player", "enemy"},
        )

        with tempfile.TemporaryDirectory() as directory:
            editor = MapEditor.__new__(MapEditor)
            editor.data = data
            editor.map_path = None
            editor.save_as_name = "custom"
            editor.message = ""
            editor.message_timer = 0
            with patch("tools.map_editor.MAPS_DIR", Path(directory)), patch(
                "tools.map_editor.pygame.display.set_caption"
            ):
                editor.finish_save_as()
                self.assertEqual(editor.map_path.name, "custom.json")
                self.assertEqual(load_map(editor.map_path), data)

    def test_freeform_terrain_contains_points_and_checks_bridge_footprints(self):
        river = River(points=[[100, 100], [220, 120], [200, 220], [120, 210]])
        bridge = Bridge(points=[[140, 145], [180, 145], [180, 175], [140, 175]])
        mountain = Mountain(points=[[300, 300], [360, 310], [345, 370], [310, 350]])

        self.assertTrue(river.contains(160, 160))
        self.assertTrue(river.intersects_circle(119, 160, 5))
        self.assertTrue(bridge.contains_circle(160, 160, 10))
        self.assertFalse(bridge.contains_circle(142, 160, 10))
        self.assertTrue(mountain.contains(330, 330))

    def test_legacy_rectangular_terrain_remains_loadable(self):
        data = copy.deepcopy(load_map())
        data["width"] = 1200
        data["height"] = 780
        data["terrain"] = {
            "rivers": [{"x": 500, "y": 0, "w": 40, "h": 780}],
            "bridges": [{"x": 490, "y": 300, "w": 60, "h": 40}],
            "mountains": [{"x": 100, "y": 100, "w": 80, "h": 70}],
        }
        for group in (data["resources"], data["buildings"], data["units"]):
            for item in group:
                item["x"] /= 4
                item["y"] /= 4

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.json"
            save_map(path, data)
            game = SimpleNamespace(
                rivers=[], bridges=[], mountains=[], resource_nodes=[], buildings=[], units=[]
            )
            apply_map(game, load_map(path))

        self.assertEqual(game.rivers[0].points, [(500.0, 0.0), (540.0, 0.0), (540.0, 780.0), (500.0, 780.0)])
        self.assertEqual(game.mountains[0].rect.size, (80, 70))

    def test_editor_finishes_arbitrary_terrain_after_enter(self):
        editor = MapEditor.__new__(MapEditor)
        editor.data = copy.deepcopy(load_map())
        editor.mode = "river"
        editor.polygon_points = [(100, 100), (250, 120), (180, 240)]
        editor.message = ""
        editor.message_timer = 0
        editor.save_as_active = False

        self.assertTrue(editor.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)))

        self.assertEqual(
            editor.data["terrain"]["rivers"][-1]["points"],
            [[100, 100], [250, 120], [180, 240]],
        )
        self.assertFalse(editor.polygon_points)

    def test_editor_can_expand_and_safely_reject_invalid_shrink(self):
        editor = MapEditor.__new__(MapEditor)
        editor.data = copy.deepcopy(load_map())
        editor.camera_x = 0
        editor.camera_y = 0
        editor.message = ""
        editor.message_timer = 0

        editor.resize_map(width_delta=1000, height_delta=1000)
        self.assertEqual((editor.data["width"], editor.data["height"]), (5800, 4120))

        editor.resize_map(width_delta=-3000)
        self.assertEqual(editor.data["width"], 5800)
        self.assertIn("无法缩小地图", editor.message)

    def test_large_map_load_sets_world_bounds(self):
        data = load_map()
        game = SimpleNamespace(
            rivers=[], bridges=[], mountains=[], resource_nodes=[], buildings=[], units=[]
        )

        apply_map(game, data)

        self.assertEqual((game.map_width, game.map_height), (4800, 3120))
        self.assertGreater(len(game.rivers), 0)
        self.assertGreater(len(game.bridges), 0)
        self.assertGreater(len(game.mountains), 0)


if __name__ == "__main__":
    unittest.main()
