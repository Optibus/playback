# p3ready
from __future__ import absolute_import

import shutil
import unittest
from datetime import datetime, timedelta
from tempfile import mkdtemp

import six

from playback.exceptions import NoSuchRecording
from playback.tape_cassettes.file_based.file_based_tape_cassette import FileBasedTapeCassette


def assert_items_equal(testcase, seq1, seq2, msg=""):
    if six.PY3:
        testcase.assertCountEqual(seq1, seq2, msg)
    else:
        testcase.assertItemsEqual(seq1, seq2, msg)


class TestFileBasedTapeCassette(unittest.TestCase):

    def setUp(self):
        self.directory = mkdtemp()
        # Delete dir so the cassette will create it
        shutil.rmtree(self.directory)
        self.cassette = FileBasedTapeCassette(self.directory)

    def tearDown(self):
        self.cassette.close()
        shutil.rmtree(self.directory)

    def test_create_save_and_fetch_empty_recording(self):
        recording = self.cassette.create_new_recording('test_operation')
        self.cassette.save_recording(recording)
        fetched_recording = self.cassette.get_recording(recording.id)
        self.assertEqual(recording.id, fetched_recording.id)

    def test_get_no_such_recording(self):
        with self.assertRaises(NoSuchRecording):
            self.cassette.get_recording('nonexisting')

    def test_create_save_and_fetch_recording_with_data(self):
        recording = self.cassette.create_new_recording('test_operation')
        recording.set_data('key1', 5)
        recording.set_data('key2', {'obj_key1': 2, 'obj_key2': "bla"})
        self.cassette.save_recording(recording)
        fetched_recording = self.cassette.get_recording(recording.id)
        self.assertEqual(recording.id, fetched_recording.id)

        self.assertEqual(5, recording.get_data('key1'))
        self.assertEqual(5, recording['key1'])
        self.assertEqual(recording.get_data('key1'), fetched_recording.get_data('key1'))

        self.assertEqual({'obj_key1': 2, 'obj_key2': "bla"}, recording.get_data('key2'))
        self.assertEqual(recording.get_data('key2'), fetched_recording.get_data('key2'))

        assert_items_equal(self, ['key1', 'key2'], recording.get_all_keys())
        assert_items_equal(self, recording.get_all_keys(), fetched_recording.get_all_keys())

    def test_create_save_and_fetch_recording_with_metadata(self):
        recording = self.cassette.create_new_recording('test_operation')
        metadata = {'key1': 5, 'key2': {'obj_key1': 2, 'obj_key2': "bla"}}
        recording.add_metadata(metadata)
        self.cassette.save_recording(recording)
        fetched_recording = self.cassette.get_recording(recording.id)
        self.assertEqual(recording.id, fetched_recording.id)

        self.assertEqual(metadata, recording.get_metadata())
        self.assertEqual(recording.get_metadata(), fetched_recording.get_metadata())

    def test_fetch_recording_ids_by_category(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation2')
        self.cassette.save_recording(recording3)

        assert_items_equal(self, [recording1.id, recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1')))
        assert_items_equal(self, [recording3.id],
                           list(self.cassette.iter_recording_ids(category='test_operation2')))

    def test_fetch_recording_ids_by_category_date_and_metadata(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        recording1.add_metadata({'property': True})
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        recording2.add_metadata({'property': False})
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation2')
        self.cassette.save_recording(recording3)

        assert_items_equal(self, [recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 start_date=datetime.utcnow() - timedelta(hours=1),
                                                                 end_date=datetime.utcnow() + timedelta(hours=1),
                                                                 metadata={'property': False})))

    def test_fetch_recordings_metadata_by_category_date_and_metadata(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        recording1.add_metadata({'property': True})
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        recording2.add_metadata({'property': False})
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation2')
        self.cassette.save_recording(recording3)

        assert_items_equal(self, [{'property': False}],
                           list(self.cassette.iter_recordings_metadata(
                               category='test_operation1',
                               start_date=datetime.utcnow() - timedelta(hours=1),
                               end_date=datetime.utcnow() + timedelta(hours=1),
                               metadata={'property': False})))

    def test_fetch_recording_ids_by_category_and_limit(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording3)

        self.assertEqual(2, len(list(self.cassette.iter_recording_ids(category='test_operation1', limit=2))))

    def test_extract_recording_category(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        self.assertEqual('test_operation1', self.cassette.extract_recording_category(recording1.id))
        recording2 = self.cassette.create_new_recording('test_operation2')
        self.assertEqual('test_operation2', self.cassette.extract_recording_category(recording2.id))
