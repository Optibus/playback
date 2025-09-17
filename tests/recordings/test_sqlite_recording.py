from __future__ import absolute_import

import unittest

from playback.recordings.sqlite.sqlite_recording import SqliteRecording
from playback.exceptions import RecordingKeyError


class TestSqliteRecording(unittest.TestCase):

    def test_set_and_get_data_roundtrip(self):
        rec = SqliteRecording.new()

        payloads = {
            'int': 42,
            'float': 3.14,
            'str': 'hello',
            'list': [1, 2, 3],
            'dict': {'a': 1, 'b': [2, 3]},
        }

        for k, v in payloads.items():
            rec.set_data(k, v)

        for k, v in payloads.items():
            self.assertEqual(rec.get_data(k), v)

    def test_get_returns_fresh_copy_each_time(self):
        rec = SqliteRecording.new()
        rec.set_data('obj', {'counter': 0})

        first = rec.get_data('obj')
        second = rec.get_data('obj')

        self.assertEqual(first, {'counter': 0})
        self.assertEqual(second, {'counter': 0})

        # Mutate first and ensure second remains unaffected (fresh decode on each call)
        first['counter'] = 99
        self.assertEqual(second, {'counter': 0})
        # Re-fetch should still be original
        self.assertEqual(rec.get_data('obj'), {'counter': 0})

    def test_missing_key_raises_recording_key_error(self):
        rec = SqliteRecording.new()
        with self.assertRaises(RecordingKeyError):
            rec.get_data('does_not_exist')

    def test_get_all_keys_returns_all(self):
        rec = SqliteRecording.new()
        rec.set_data('k1', 1)
        rec.set_data('k2', 2)
        rec.set_data('k3', 3)

        keys = rec.get_all_keys()
        self.assertTrue(set(keys) == {'k1', 'k2', 'k3'})

    def test_metadata_add_and_get(self):
        rec = SqliteRecording.new()
        rec.add_metadata({'a': 1})
        rec.add_metadata({'b': 2})

        # Metadata also contains an internal _recording_type field, so we are checking inclusion of the expected keys
        self.assertLessEqual({'a': 1, 'b': 2}.items(), rec.get_metadata().items())

    def test_new_with_id_preserved(self):
        rec = SqliteRecording.new('my-id-123')
        self.assertEqual(rec.id, 'my-id-123')

    def test_from_buffered_reader_loads_from_bytes(self):
        # Create a recording and persist some data
        rec1 = SqliteRecording.new()
        rec1.set_data('foo', {'x': 1})

        # Use the public buffered reader API to clone the DB into a new recording
        with rec1.as_buffered_reader() as (f, size):
            self.assertGreater(size, 0)
            rec2 = SqliteRecording.from_buffered_reader(rec1.id, f, recording_metadata={'meta': True})

        # Validate data and metadata are accessible
        self.assertEqual(rec2.get_data('foo'), {'x': 1})
        self.assertEqual(rec2.get_all_keys(), ['foo'])
        self.assertLessEqual({'meta': True}.items(), rec2.get_metadata().items())

    def test_indirect_setitem_getitem(self):
        rec = SqliteRecording.new()
        rec['answer'] = 42
        self.assertEqual(rec['answer'], 42)
