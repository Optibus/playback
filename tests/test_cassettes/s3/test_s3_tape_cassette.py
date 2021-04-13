# p3ready
from __future__ import absolute_import

import unittest
import uuid
from datetime import datetime, timedelta
from mock import patch
import boto3
from mock.mock import Mock
from moto import mock_s3
from playback.exceptions import NoSuchRecording
from playback.recording import Recording
import six
from playback.tape_cassettes.s3.s3_tape_cassette import S3TapeCassette
from six.moves import range
TEST_BUCKET = 'test_bucket'


def assert_items_equal(testcase, seq1, seq2, msg=""):
    if six.PY3:
        testcase.assertCountEqual(seq1, seq2, msg)
    else:
        testcase.assertItemsEqual(seq1, seq2, msg)


@mock_s3
class TestS3TapeCassette(unittest.TestCase):

    def setUp(self):
        conn = boto3.resource('s3', region_name='us-east-1')
        # We need to create the bucket since this is all in Moto's 'virtual' AWS account
        conn.create_bucket(Bucket=TEST_BUCKET)
        self.cassette = S3TapeCassette(TEST_BUCKET, key_prefix='tests_' + uuid.uuid1().hex, transient=True,
                                       read_only=False)

    def tearDown(self):
        self.cassette.close()

    def test_create_save_and_fetch_empty_recording(self):
        recording = self.cassette.create_new_recording('test_operation')
        self.cassette.save_recording(recording)
        fetched_recording = self.cassette.get_recording(recording.id)
        self.assertEqual(recording.id, fetched_recording.id)

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

    def test_get_recording_and_get_recording_metadata_non_existing(self):
        with self.assertRaises(NoSuchRecording):
            self.cassette.get_recording('non existing id')

        with self.assertRaises(NoSuchRecording):
            self.cassette.get_recording_metadata('non existing id')

    def test_get_recording_and_get_recording_metadata_other_exception(self):

        def side_affect(*args, **kwargs):
            raise ValueError('some error')

        with patch('playback.tape_cassettes.s3.s3_basic_facade.S3BasicFacade.get_string',
                   side_affect):
            with self.assertRaises(ValueError) as cm:
                self.cassette.get_recording('some id')
            self.assertEqual('some error', str(cm.exception))

            with self.assertRaises(ValueError) as cm:
                self.cassette.get_recording_metadata('some id')
            self.assertEqual('some error', str(cm.exception))

    def test_create_save_and_fetch_recording_with_metadata(self):
        recording = self.cassette.create_new_recording('test_operation')
        metadata = {'key1': 5, 'key2': {'obj_key1': 2, 'obj_key2': "bla"}}
        recording.add_metadata(metadata)
        self.cassette.save_recording(recording)
        fetched_recording = self.cassette.get_recording(recording.id)
        self.assertEqual(recording.id, fetched_recording.id)

        self.assertEqual(metadata, recording.get_metadata())
        self.assertEqual(recording.get_metadata(), fetched_recording.get_metadata())

        fetched_recording_metadata = self.cassette.get_recording_metadata(recording.id)
        self.assertEqual(metadata, fetched_recording_metadata)

    def test_close_transient_true(self):
        prefix = 'tests_' + uuid.uuid1().hex
        with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=False) as new_cassette:
            recording = new_cassette.create_new_recording('test_operation')
            new_cassette.save_recording(recording)

        with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=False) as new_cassette:
            with self.assertRaises(NoSuchRecording):
                new_cassette.get_recording(recording.id)

    def test_close_transient_false(self):
        prefix = 'tests_' + uuid.uuid1().hex
        with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=False, read_only=False) as new_cassette:
            recording = new_cassette.create_new_recording('test_operation')
            new_cassette.save_recording(recording)

        # Closing this will clean up the garbage
        with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=False) as new_cassette:
            self.assertIsNotNone(new_cassette.get_recording(recording.id))

    def test_read_only_cassette(self):
        prefix = 'tests_' + uuid.uuid1().hex
        try:
            with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=False, read_only=False) as new_cassette:
                recording = new_cassette.create_new_recording('test_operation')
                new_cassette.save_recording(recording)

            new_cassette = S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=True)
            fetched_recording = new_cassette.get_recording(recording.id)
            self.assertIsNotNone(fetched_recording)
            with self.assertRaises(AssertionError):
                new_cassette.create_new_recording("some_category")
            with self.assertRaises(AssertionError):
                new_cassette.save_recording(fetched_recording)
            new_cassette.close()

            # Check the close didn't delete the previous recording
            new_cassette = S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=True)
            self.assertIsNotNone(new_cassette.get_recording(recording.id))
            new_cassette.close()

        finally:
            # Clean up the garbage
            S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=False, read_only=False).close()

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

    def test_fetch_recording_ids_by_category_and_date(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation2')
        self.cassette.save_recording(recording3)

        assert_items_equal(self, [recording1.id, recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 start_date=datetime.utcnow() - timedelta(hours=1))))
        assert_items_equal(self, [],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 start_date=datetime.utcnow() + timedelta(hours=1))))

        assert_items_equal(self, [recording1.id, recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 end_date=datetime.utcnow() + timedelta(hours=1))))
        assert_items_equal(self, [],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 end_date=datetime.utcnow() - timedelta(hours=1))))

        assert_items_equal(self, [recording1.id, recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 start_date=datetime.utcnow() - timedelta(hours=1),
                                                                 end_date=datetime.utcnow() + timedelta(hours=1))))

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

    def test_fetch_recording_ids_with_wildcard_matching_metadata(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        recording1.add_metadata({'property': 'val11'})
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        recording2.add_metadata({'property': 'val21'})
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation2')
        self.cassette.save_recording(recording3)

        assert_items_equal(self, [recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 metadata={'property': 'val2*'})))

        assert_items_equal(self, [recording1.id, recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 metadata={'property': 'val*'})))

    def test_fetch_recordings_metadata_with_wildcard_matching_metadata(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        recording1.add_metadata({'property': 'val11'})
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        recording2.add_metadata({'property': 'val21'})
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation2')
        self.cassette.save_recording(recording3)

        assert_items_equal(self, [{'property': 'val21'}],
                           list(self.cassette.iter_recordings_metadata(category='test_operation1',
                                                                       metadata={'property': 'val2*'})))

        assert_items_equal(self, [{'property': 'val11'}, {'property': 'val21'}],
                           list(self.cassette.iter_recordings_metadata(category='test_operation1',
                                                                       metadata={'property': 'val*'})))

    def test_fetch_recording_ids_with_wildcard_matching_metadata_value_not_set(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        recording1.add_metadata({'property': 'val11'})
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        recording2.add_metadata({'property': 'val21'})
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording3)

        assert_items_equal(self, [recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 metadata={'property': 'val2*'})))

        assert_items_equal(self, [recording1.id, recording2.id],
                           list(self.cassette.iter_recording_ids(category='test_operation1',
                                                                 metadata={'property': 'val*'})))

    def test_fetch_recording_ids_by_category_and_limit(self):
        recording1 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording2)
        recording3 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording3)

        self.assertEqual(2, len(list(self.cassette.iter_recording_ids(category='test_operation1', limit=2))))

    def test_fetch_recording_ids_by_limit_overall(self):
        yesterday = Mock(wraps=datetime.today)
        yesterday.return_value = datetime.today()-timedelta(days=1)
        with patch('datetime.today', yesterday, create=True):
            recording1 = self.cassette.create_new_recording('test_operation1')
            self.cassette.save_recording(recording1)
        recording2 = self.cassette.create_new_recording('test_operation1')
        self.cassette.save_recording(recording2)
        self.assertEqual(1, len(list(self.cassette.iter_recording_ids(
            category='test_operation1', limit=1, start_date=datetime.utcnow() - timedelta(days=7)))))

    def test_big_recording_storage_type(self):
        prefix = 'tests_' + uuid.uuid1().hex
        with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=False,
                            infrequent_access_kb_threshold=1) as new_cassette:
            with patch.object(new_cassette._s3_facade, 'put_string', wraps=new_cassette._s3_facade.put_string) \
                    as patched:
                recording = new_cassette.create_new_recording('test_operation')
                recording.set_data('some_data', list(range(10000)))
                new_cassette.save_recording(recording)
                args, kwargs = patched.call_args_list[0]
                self.assertEqual('STANDARD_IA', kwargs['StorageClass'])

        with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=False,
                            infrequent_access_kb_threshold=1) as new_cassette:
            with patch.object(new_cassette._s3_facade, 'put_string',
                              wraps=new_cassette._s3_facade.put_string) \
                    as patched:
                recording = new_cassette.create_new_recording('test_operation')
                recording.set_data('some_data', list(range(10)))
                new_cassette.save_recording(recording)
                args, kwargs = patched.call_args_list[0]
                self.assertEqual('STANDARD', kwargs['StorageClass'])

    def test_save_with_sampling_ratio(self):
        prefix = 'tests_' + uuid.uuid1().hex

        def sampling_calculator(category, size, r):
            self.assertEqual(category, 'test_operation')
            self.assertIsInstance(r, Recording)
            return 1 if size < 500 else 0

        with S3TapeCassette(TEST_BUCKET, key_prefix=prefix, transient=True, read_only=False,
                            sampling_calculator=sampling_calculator) as new_cassette:
            recording = new_cassette.create_new_recording('test_operation')
            new_cassette.save_recording(recording)
            self.assertIsNotNone(new_cassette.get_recording(recording.id))

            recording = new_cassette.create_new_recording('test_operation')
            recording.set_data('key', list(range(1000)))
            new_cassette.save_recording(recording)
            with self.assertRaises(NoSuchRecording):
                new_cassette.get_recording(recording.id)
