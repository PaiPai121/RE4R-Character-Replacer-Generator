import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from subprocess import TimeoutExpired
from unittest.mock import patch

import server


class ProfilePreparationTests(unittest.TestCase):
    def write_profile(self, root, character, fingerprint):
        folder = root / 'replacer_app' / 'presets' / ('re4_' + character['id'])
        folder.mkdir(parents=True)
        (folder / 'hidden.mesh.221108797').touch()
        (folder / 'neutral.mdf2.32').touch()
        (folder / 'profile.json').write_text(json.dumps({
            'character': character['id'], 'game_fingerprint': fingerprint,
        }), encoding='utf-8')

    def test_scan_prepares_characters_individually_and_resumes_completed_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            characters = [
                {'id': 'leon', 'label': 'Leon', 'characterIds': ['cha000']},
                {'id': 'ashley', 'label': 'Ashley', 'characterIds': ['cha100']},
            ]
            fingerprint = [['re_chunk_000.pak', 10, 20]]
            data = {'game': 'game', 'fingerprint': fingerprint,
                    'resources': {'natives/stm/_chainsaw/character/ch/cha100/cha100_00.mesh.221108797': {}}}
            self.write_profile(root, characters[0], fingerprint)
            calls = []

            def run_character(command, **kwargs):
                calls.append((command, kwargs))
                character_id = command[command.index('--character') + 1]
                character = next(item for item in characters if item['id'] == character_id)
                self.write_profile(root, character, fingerprint)
                return CompletedProcess(command, 0, stdout=json.dumps({'prepared': [character_id], 'skipped': []}), stderr='')

            server.JOBS['profile-test'] = {'id': 'profile-test', 'status': 'queued'}
            with (patch.object(server, 'PROJECT', root),
                  patch.object(server, 'BLENDER', Path('blender.exe')),
                  patch.object(server.game_resources, 'CHARACTERS', characters),
                  patch.object(server.game_resources, 'scan', return_value=data),
                  patch.object(server.game_resources, 'extract') as extract,
                  patch.object(server, 'scan_replaceable_characters', return_value=[{'id': 'leon'}, {'id': 'ashley'}]),
                  patch.object(server.subprocess, 'run', side_effect=run_character)):
                server.run_scan_job('profile-test', {'gamePath': 'game'})

            job = server.JOBS.pop('profile-test')
            self.assertEqual(job['status'], 'complete')
            extract.assert_called_once()
            self.assertEqual(len(calls), 1)
            self.assertIn('--skip-extract', calls[0][0])
            self.assertEqual(calls[0][1]['timeout'], 180)
            self.assertIn('Leon 已完成，跳过', job['stdout'])
            self.assertIn('Ashley', job['stdout'])

    def test_profile_cache_requires_matching_game_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            character = {'id': 'leon', 'label': 'Leon', 'characterIds': ['cha000']}
            self.write_profile(root, character, [['pak', 1, 2]])
            with patch.object(server, 'PROJECT', root):
                self.assertTrue(server.profile_is_current(character, {'fingerprint': [('pak', 1, 2)]}))
                self.assertFalse(server.profile_is_current(character, {'fingerprint': [['pak', 1, 3]]}))

    def test_stalled_character_fails_with_name_and_keeps_completed_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            characters = [
                {'id': 'leon', 'label': 'Leon', 'characterIds': ['cha000']},
                {'id': 'ashley', 'label': 'Ashley', 'characterIds': ['cha100']},
            ]
            fingerprint = [['re_chunk_000.pak', 10, 20]]
            data = {'game': 'game', 'fingerprint': fingerprint,
                    'resources': {'natives/stm/_chainsaw/character/ch/cha100/cha100_00.mesh.221108797': {}}}
            self.write_profile(root, characters[0], fingerprint)
            server.JOBS['timeout-test'] = {'id': 'timeout-test', 'status': 'queued'}
            with (patch.object(server, 'PROJECT', root),
                  patch.object(server, 'BLENDER', Path('blender.exe')),
                  patch.object(server.game_resources, 'CHARACTERS', characters),
                  patch.object(server.game_resources, 'scan', return_value=data),
                  patch.object(server.game_resources, 'extract'),
                  patch.object(server.subprocess, 'run', side_effect=TimeoutExpired(['blender'], 180))):
                server.run_scan_job('timeout-test', {'gamePath': 'game'})

            job = server.JOBS.pop('timeout-test')
            self.assertEqual(job['status'], 'failed')
            self.assertIn('Ashley', job['error'])
            self.assertIn('180 秒', job['error'])
            self.assertTrue((root / 'replacer_app/presets/re4_leon/profile.json').is_file())

    def test_scan_skips_character_whose_pak_entry_was_invalidated_by_mod_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            characters = [
                {'id': 'leon', 'label': 'Leon', 'characterIds': ['cha000']},
                {'id': 'ashley', 'label': 'Ashley', 'characterIds': ['cha100']},
            ]
            fingerprint = [['re_chunk_000.pak', 10, 20]]
            data = {
                'game': 'game', 'fingerprint': fingerprint,
                'resources': {'natives/stm/_chainsaw/character/ch/cha100/00/cha100_00.mesh.221108797': {}},
                'diagnostics': {'characters': {
                    'leon': {'primaryAvailable': False, 'issue': 'modded-game-archive'},
                    'ashley': {'primaryAvailable': True, 'issue': None},
                }},
            }
            calls = []

            def run_character(command, **kwargs):
                character_id = command[command.index('--character') + 1]
                calls.append(character_id)
                character = next(item for item in characters if item['id'] == character_id)
                self.write_profile(root, character, fingerprint)
                return CompletedProcess(command, 0, stdout=json.dumps({'prepared': [character_id], 'skipped': []}), stderr='')

            server.JOBS['invalidated-primary-test'] = {'id': 'invalidated-primary-test', 'status': 'queued'}
            with (patch.object(server, 'PROJECT', root),
                  patch.object(server, 'BLENDER', Path('blender.exe')),
                  patch.object(server.game_resources, 'CHARACTERS', characters),
                  patch.object(server.game_resources, 'scan', return_value=data),
                  patch.object(server.game_resources, 'extract'),
                  patch.object(server.subprocess, 'run', side_effect=run_character),
                  patch.object(server, 'scan_replaceable_characters', return_value=[{'id': 'leon'}, {'id': 'ashley'}])):
                server.run_scan_job('invalidated-primary-test', {'gamePath': 'game'})

            job = server.JOBS.pop('invalidated-primary-test')
            self.assertEqual(job['status'], 'complete')
            self.assertEqual(calls, ['ashley'])
            self.assertIn('Fluffy Mod Manager', job['stdout'])


if __name__ == '__main__':
    unittest.main()
