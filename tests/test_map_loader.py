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
        editor.terrain_size = {"river": [50, 180], "bridge": [90, 40], "mountain": [140, 110]}

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


if __name__ == "__main__":
    unittest.main()
