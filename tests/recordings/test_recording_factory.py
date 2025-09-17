import unittest

from playback.recordings.factory import get_recording_class
from playback.recordings.memory.memory_recording import MemoryRecording
from playback.recordings.sqlite.sqlite_recording import SqliteRecording


class TestSqliteRecording(unittest.TestCase):
    def test_recording_factory(self):
        self.assertEqual(get_recording_class({'_recording_type': 'sqlite'}), SqliteRecording)
        self.assertEqual(get_recording_class({'_recording_type': 'memory'}), MemoryRecording)
        self.assertEqual(get_recording_class({}), MemoryRecording)
        try:
            get_recording_class({'_recording_type': 'unknown'})
            self.fail("An exception should be raised")
        except Exception as e:
            self.assertEqual(str(e), "Unsupported recording type unknown")
