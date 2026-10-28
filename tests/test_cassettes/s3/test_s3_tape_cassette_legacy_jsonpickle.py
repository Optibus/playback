import json
import unittest
from datetime import timedelta
from decimal import Decimal
from zlib import compress

import boto3
import jsonpickle
from moto import mock_s3

from playback.tape_cassettes.s3.s3_tape_cassette import S3TapeCassette
from playback.tape_recorder import TapeRecorder
from tests.utils.legacy_jsonpickle_cases import Color, load_fixtures

TEST_BUCKET = 'test_bucket'
KEY_PREFIX = 'legacy'

LEGACY_TIMEDELTA = {
    'py/object': 'datetime.timedelta',
    '__reduce__': [{'py/type': 'datetime.timedelta'}, {'py/tuple': [0, 30, 0]}],
}


@mock_s3
class TestS3TapeCassetteLegacyJsonpickle(unittest.TestCase):

    def setUp(self):
        self.s3 = boto3.resource('s3', region_name='us-east-1')
        self.s3.create_bucket(Bucket=TEST_BUCKET)
        self.fixtures = load_fixtures()

    def test_decode_legacy_memory_recording(self):
        self._put_legacy_memory_recording('Operation/20260101/legacy')

        recording = self._cassette(True).get_recording('Operation/20260101/legacy')

        self.assertTrue(recording.legacy_jsonpickle)

        value = recording.get_data('input: get args={"py/tuple": []}, kwargs=[]')['value']
        self.assertIs(Color.RED, value[0])
        self.assertEqual([1, 2], value[1])

        stored = recording.get_data('output: store #1')
        self.assertEqual([1, 2], stored['args'][0])
        self.assertEqual(timedelta(hours=1), stored['args'][1]['when'])

        self.assertEqual(Decimal('2.5'), recording.get_data('output: _tape_recorder_operation #1')['args'][1])

    def test_decode_legacy_metadata(self):
        self._put_legacy_memory_recording(
            'Operation/20260101/legacy', metadata={'_recording_type': 'memory', 'timeout': LEGACY_TIMEDELTA}
        )

        cassette = self._cassette(True)

        self.assertEqual(timedelta(seconds=30), cassette.get_recording_metadata('Operation/20260101/legacy')['timeout'])

    def test_recording_with_jsonpickle_version_is_not_legacy(self):
        value = {'when': timedelta(hours=1), 'shared': [[1], [1]]}
        metadata = {'_recording_type': 'memory', TapeRecorder.JSONPICKLE_VERSION: '4.1.4'}
        self._put_recording(
            'Operation/20260101/current', metadata, compress(jsonpickle.encode({'key': value}).encode('utf-8'))
        )

        recording = self._cassette(True).get_recording('Operation/20260101/current')

        self.assertFalse(recording.legacy_jsonpickle)
        self.assertEqual(value, recording.get_data('key'))

    def test_compatibility_is_off_by_default(self):
        encoded = json.dumps({'key': [1, 2]})
        self._put_recording(
            'Operation/20260101/legacy', {'_recording_type': 'memory'}, compress(encoded.encode('utf-8'))
        )

        recording = S3TapeCassette(TEST_BUCKET, key_prefix=KEY_PREFIX).get_recording('Operation/20260101/legacy')

        self.assertFalse(recording.legacy_jsonpickle)
        self.assertEqual([1, 2], recording.get_data('key'))

    def _put_legacy_memory_recording(self, recording_id, metadata=None):
        encoded = self.fixtures['recording like']['encoded']
        self._put_recording(recording_id, metadata or {'_recording_type': 'memory'}, compress(encoded.encode('utf-8')))

    def _put_recording(self, recording_id, metadata, body):
        metadata_key = S3TapeCassette.METADATA_KEY.format(key_prefix=KEY_PREFIX + '/', id=recording_id)
        full_key = S3TapeCassette.FULL_KEY.format(key_prefix=KEY_PREFIX + '/', id=recording_id)
        self.s3.Object(TEST_BUCKET, metadata_key).put(Body=json.dumps(metadata))
        self.s3.Object(TEST_BUCKET, full_key).put(Body=body)

    @staticmethod
    def _cassette(legacy_recordings_compatibility):
        return S3TapeCassette(
            TEST_BUCKET, key_prefix=KEY_PREFIX, legacy_recordings_compatibility=legacy_recordings_compatibility
        )
