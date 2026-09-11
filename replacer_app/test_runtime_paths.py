import os
import unittest
from unittest.mock import patch

import runtime_paths


class RuntimePathTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch('runtime_paths._saved_paths', return_value={})
    @patch('pathlib.Path.is_file', return_value=False)
    def test_missing_game_has_a_safe_default(self, _is_file, _saved):
        path = runtime_paths.find_game()
        self.assertTrue(str(path).endswith(
            r'SteamLibrary\steamapps\common\RESIDENT EVIL 4  BIOHAZARD RE4'))

    @patch.dict(os.environ, {}, clear=True)
    @patch('runtime_paths._saved_paths', return_value={'game': r'Q:\Games\RE4'})
    @patch('pathlib.Path.is_file', return_value=False)
    def test_saved_game_path_is_used_as_fallback(self, _is_file, _saved):
        self.assertEqual(str(runtime_paths.find_game()), r'Q:\Games\RE4')


if __name__ == '__main__':
    unittest.main()
