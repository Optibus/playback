import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import timedelta

from playback.recordings.sqlite.sqlite_recording import SqliteRecording
from tests.utils.legacy_jsonpickle_cases import Color, load_fixtures


class TestSqliteRecordingLegacyJsonpickle(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.db_path = os.path.join(self.directory, 'recording.db')
        fixtures = load_fixtures()
        connection = sqlite3.connect(self.db_path)
        connection.execute('CREATE TABLE data (key TEXT PRIMARY KEY, value TEXT)')
        connection.executemany(
            'INSERT INTO data VALUES (?, ?)',
            [(name, fixtures[name]['encoded']) for name in ('timedelta', 'enum', 'shared list in dict')],
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        shutil.rmtree(self.directory)

    def test_decode_legacy_values(self):
        with open(self.db_path, 'rb') as db_file:
            recording = SqliteRecording.from_buffered_reader('legacy', db_file, legacy_jsonpickle=True)

        self.assertTrue(recording.legacy_jsonpickle)
        self.assertEqual(timedelta(days=1, seconds=2), recording.get_data('timedelta'))
        self.assertIs(Color.RED, recording.get_data('enum'))

        shared = recording.get_data('shared list in dict')
        self.assertEqual({'a': [1, 2], 'b': [1, 2]}, shared)
        self.assertIs(shared['a'], shared['b'])
