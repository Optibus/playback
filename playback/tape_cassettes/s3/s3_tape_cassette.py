from __future__ import absolute_import
from copy import copy
from random import Random
from zlib import compress, decompress
import logging
import uuid
from fnmatch import fnmatch
import six
from jsonpickle import encode, decode
from parse import compile  # pylint: disable=redefined-builtin


from playback.exceptions import NoSuchRecording
from playback.tape_cassette import TapeCassette
from playback.recordings.memory.memory_recording import MemoryRecording
from playback.tape_cassettes.s3.s3_basic_facade import S3BasicFacade
from playback.utils.timing_utils import Timed

_logger = logging.getLogger(__name__)


class S3TapeCassette(TapeCassette):

    FULL_KEY = 'tape_recorder_recordings/{key_prefix}full/{id}'
    METADATA_KEY = 'tape_recorder_recordings/{key_prefix}metadata/{id}'
    RECORDING_ID = '{category}/{id}'

    def __init__(self, bucket, key_prefix='', region=None, transient=False, read_only=True,
                 infrequent_access_kb_threshold=None, sampling_calculator=None):
        """
        :param bucket: Cassette s3 storage bucket
        :type bucket: str
        :param key_prefix: Optional key prefix for recordings
        :type key_prefix: str
        :param region: Optional aws region
        :type region: str
        :param transient: Is this a transient cassette, all recording under given prefix will be deleted when closed
        (only if not read only)
        :type transient: bool
        :param read_only: If True, this cassette can only be used to fetch recordings and not to create new ones,
        any write operations will raise an assertion.
        :type read_only: bool
        :param infrequent_access_kb_threshold: Threshold in KB that above it object will be saved in STANDARD_IA
        (infrequent access storage class), None means never (default)
        :type infrequent_access_kb_threshold: float
        :param sampling_calculator: Optional sampling ratio calculator function, before saving the recording this
        function will be triggered with (category, recording_size, recording),
        and the function should return a number between 0 and 1 which specify its sampling rate
        :type sampling_calculator: function
        """
        _logger.info(u'Creating S3TapeCassette using bucket {}'.format(bucket))
        self.bucket = bucket
        self.key_prefix = (key_prefix + '/') if key_prefix else ''
        self.transient = transient
        self.read_only = read_only
        self.infrequent_access_threshold = \
            infrequent_access_kb_threshold * 1024 if infrequent_access_kb_threshold else None
        self.sampling_calculator = sampling_calculator
        self._random = Random(110613)
        self._metadata_key_parser = compile(self.METADATA_KEY)
        self._recording_id_parser = compile(self.RECORDING_ID)
        self._s3_facade = S3BasicFacade(self.bucket, region=region)

    def get_recording(self, recording_id):
        """
        Get recording stored with the given id
        :param recording_id: If of recording to fetch
        :type recording_id: basestring
        :return: Recording of the given id
        :rtype: playback.recordings.memory.memory_recording.MemoryRecording
        """
        full_key = self.FULL_KEY.format(key_prefix=self.key_prefix, id=recording_id)
        try:
            _logger.info(u'Fetching compressed recording using key {}'.format(full_key))
            compressed_recording = self._s3_facade.get_string(full_key)
            _logger.info(u'Decompressing recording of key {}'.format(full_key))
            serialized_data = decompress(compressed_recording)
        except Exception as ex:
            if 'NoSuchKey' in type(ex).__name__:
                raise NoSuchRecording(recording_id)
            raise
        _logger.info(u'Decoding recording of key {}'.format(full_key))
        full_data = decode(serialized_data)
        # Extract the meta data also in the full recording
        metadata = full_data.pop('_metadata', {})
        _logger.info(u'Returning recording of key {}'.format(full_key))
        return MemoryRecording(recording_id, recording_data=full_data, recording_metadata=metadata)

    def create_new_recording(self, category):
        """
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        :return: Creates a new recording object
        :rtype: playback.recordings.memory.memory_recording.MemoryRecording
        """
        self._assert_not_read_only()

        _id = self.RECORDING_ID.format(category=category, id=uuid.uuid1().hex)
        logging.info(u'Creating a new recording with id {}'.format(_id))
        return MemoryRecording(_id)

    def _assert_not_read_only(self):
        """
        Asserts that current cassette is not in read only mode
        """
        assert not self.read_only, 'Cassette is in readonly mode'

    def _save_recording(self, recording):
        """
        Saves given recording
        :param recording: Recording to save
        :type recording: playback.recordings.memory.memory_recording.MemoryRecording
        """
        self._assert_not_read_only()

        full_data = copy(recording.recording_data)
        # We put meta data also in the full recording
        full_data['_metadata'] = recording.recording_metadata

        with Timed() as timed:
            encoded_full = encode(full_data, unpicklable=True)
        encoding_duration = timed.duration

        with Timed() as timed:
            if six.PY3 and isinstance(encoded_full, str):
                compressed_full = compress(bytes(encoded_full.encode('utf-8')))
            else:
                compressed_full = compress(encoded_full)
        compression_duration = timed.duration

        recording_size = len(compressed_full)

        if not self._should_sample(recording, recording_size):
            logging.info(u'Recording with id {} is not chosen to be sampled and is being discarded'.format(
                recording.id))
            return

        storage_class = self._calculate_storage_class(recording_size)

        full_key = self.FULL_KEY.format(key_prefix=self.key_prefix, id=recording.id)
        metadata_key = self.METADATA_KEY.format(key_prefix=self.key_prefix, id=recording.id)

        _logger.debug(u"Saving recording full data at bucket {} under key {}".format(self.bucket, full_key))
        self._s3_facade.put_string(full_key, compressed_full, StorageClass=storage_class)
        # We break into two keys so we can do faster and cheap filtering based on metadata not requiring to fetch the
        # entire recording data
        _logger.debug(u"Saving recording metadata at bucket {} under key {}".format(self.bucket, metadata_key))
        self._s3_facade.put_string(metadata_key, encode(recording.recording_metadata, unpicklable=True))
        _logger.info(
            u"Recording saved at bucket {} under key {} "
            u"(recording size: {:.1f}KB -compressed-> {:.1f}KB, storage class: {}, "
            u"encoding/compression durations: {:.2f}/{:.2f})".format(
                self.bucket, full_key,
                len(encoded_full) / 1024.0, len(compressed_full) / 1024.0, storage_class,
                encoding_duration, compression_duration))

    def _calculate_storage_class(self, recording_size):
        """
        :param recording_size: Length of compressed recording full data
        :type recording_size: int
        :return: S3 Storage class to be used based on recording size
        :rtype: str
        """
        storage_class = 'STANDARD'
        if self.infrequent_access_threshold and recording_size >= self.infrequent_access_threshold:
            storage_class = 'STANDARD_IA'
        return storage_class

    def _should_sample(self, recording, recording_size):
        """
        Returns whether the given recording should be part of the sample
        :param recording: Recording to determine sample rate for
        :type recording: MemoryRecording
        :param recording_size: Length of compressed recording full data
        :type recording_size: int
        :return:
        :rtype:
        """
        if self.sampling_calculator is None:
            return True

        category = self.extract_recording_category(recording.id)

        ratio = self.sampling_calculator(category, recording_size, recording)
        if ratio >= 1:
            return True

        return self._random.random() <= ratio

    def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None):
        """
        Creates an iterator of keys matching the given parameters
        :param category: Recordings category
        :type category: basestring
        :param start_date: Optional recording start date (need to be given in utc time)
        :type start_date: datetime.datetime
        :param end_date: Optional recording end date (need to be given in utc time)
        :type end_date: datetime.datetime
        :param metadata: Optional metadata values to filter by
        :type metadata: dict
        :param limit: Optional limit on number of ids to fetch
        :type limit: int
        :return: Iterator of keys matching the given parameters
        :rtype: collections.Iterator[basestring]
        """
        content_filter = None
        if metadata:

            def content_filter_func(recording_str):
                recording_metadata = decode(recording_str)
                for k, v in metadata.items():  # pylint: disable=invalid-name
                    recorded_value = recording_metadata.get(k)
                    if recorded_value is None and v is not None:
                        return False

                    if isinstance(v, str):
                        if not fnmatch(recorded_value, v):
                            return False
                    elif recorded_value != v:
                        return False

                return True
            content_filter = content_filter_func

        for key in self._s3_facade.iter_keys(
                prefix=self.METADATA_KEY.format(key_prefix=self.key_prefix, id='{}/'.format(category)),
                start_date=start_date,
                end_date=end_date,
                content_filter=content_filter,
                limit=limit):
            result = self._metadata_key_parser.parse(key)
            if result is None:
                continue
            recording_id = result.named['id']
            _logger.info(u'Found filtered recording id {}'.format(recording_id))
            yield recording_id

    def extract_recording_category(self, recording_id):
        """
        :param recording_id: Recording id to extract category from
        :type recording_id: str
        :return: Recording's category
        :rtype: str
        """
        result = self._recording_id_parser.parse(recording_id)
        assert result is not None, 'Unrecognized key used'
        return result.named['category']

    def close(self):
        """
        Close this cassette and release any underlying resources, if set to be transient it will delete all recordings
        """
        if self.read_only or not self.transient:
            return

        full_key = self.FULL_KEY.format(key_prefix=self.key_prefix, id='')
        metadata_key = self.METADATA_KEY.format(key_prefix=self.key_prefix, id='')
        _logger.info(u'Deleting all full recordings at bucket {} with prefix {}'.format(self.bucket, full_key))
        self._s3_facade.delete_by_prefix(full_key)
        _logger.info(u'Deleting all metadata recordings at bucket {} with prefix {}'.format(self.bucket, metadata_key))
        self._s3_facade.delete_by_prefix(metadata_key)
