from __future__ import absolute_import

import random
from copy import copy
from random import Random
from zlib import compress, decompress
import logging
import uuid
from datetime import datetime, timedelta
import json
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
    RECORDING_ID = '{category}/{day}/{id}'
    DAY_FORMAT = '%Y%m%d'

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

    def get_recording_metadata(self, recording_id):
        """
        Get recording's metadata stored with the given id
        :param recording_id: If of recording to fetch
        :type recording_id: basestring
        :return: Recording of the given id
        :rtype: dict
        :raises: playback.exceptions.NoSuchRecording
        """
        metadata_key = self.METADATA_KEY.format(key_prefix=self.key_prefix, id=recording_id)
        try:
            _logger.debug(u'Fetching metadata of recording using key {}'.format(metadata_key))
            serialized_data = self._s3_facade.get_string(metadata_key)
        except Exception as ex:
            if 'NoSuchKey' in type(ex).__name__:
                raise NoSuchRecording(recording_id)
            raise
        _logger.debug(u'Decoding metadata of recording of key {}'.format(metadata_key))
        return decode(serialized_data)

    def create_new_recording(self, category):
        """
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        :return: Creates a new recording object
        :rtype: playback.recordings.memory.memory_recording.MemoryRecording
        """
        self._assert_not_read_only()

        _id = self.RECORDING_ID.format(
            category=category,
            day=datetime.today().strftime(self.DAY_FORMAT),
            id=uuid.uuid1().hex
        )
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

    def create_id_prefix_iterators(self, id_prefixes, start_date=None, end_date=None, content_filter=None, limit=None,
                                   random_results=False):
        """
        Creates a list of iterators for every day in case of using dates or for category otherwise.
        :param id_prefixes: list of prefixes to use
        :type id_prefixes: list of basestring
        :param start_date: Optional recording start date (need to be given in utc time)
        :type start_date: datetime.datetime
        :param end_date: Optional recording end date (need to be given in utc time)
        :type end_date: datetime.datetime
        :param content_filter: Optional limit on number of ids to fetch
        :type content_filter: function
        :param limit: Optional filter function to use
        :type limit: int
        :param random_results: True to return result in random order
        :type random_results: bool
        :return: list of Iterator of keys matching the given parameters
        :rtype: list of collections.Iterator[basestring]
        """
        return [self._s3_facade.iter_keys(
            prefix=self.METADATA_KEY.format(
                key_prefix=self.key_prefix, id=id_prefix
            ),
            start_date=start_date,
            end_date=end_date,
            content_filter=content_filter,
            limit=copy(limit),
            random_results=random_results) for id_prefix in id_prefixes]

    @staticmethod
    def _create_content_filter_func(metadata):
        """
        Create a filter function which filters on the metadata values
        :param metadata: metadata values to filter by
        :type metadata: dict
        :return: the filter function
        :rtype: function
        """
        def content_filter_func(recording_str):
            recording_metadata = json.loads(recording_str)
            return TapeCassette.match_against_recorded_metadata(metadata, recording_metadata)

        return content_filter_func

    def _get_id_prefixes(self, category, start_date=None, end_date=None):
        """
        Get recording IDs prefixes
        :param category: Recordings category
        :type category: basestring
        :param start_date: Optional recording start date (need to be given in utc time)
        :type start_date: datetime.datetime
        :param end_date: Optional recording end date (need to be given in utc time)
        :type end_date: datetime.datetime
        :return: list of id prefixes
        :rtype: list
        """
        # to improve performance when looking for recordings in s3, the date is added to the folder
        # and when a start date is given we can look for specific folders until today (or end_time)
        if start_date:
            end_date = end_date or datetime.utcnow()
            days = [(start_date + timedelta(days=i)) for i in range((end_date - start_date).days + 1)]
            id_prefixes = ['{}/{}/'.format(category, day.strftime(self.DAY_FORMAT)) for day in days]
        else:
            id_prefixes = ['{}/'.format(category)]

        return id_prefixes

    def _get_days_iterators(self, category, start_date=None, end_date=None, metadata=None, limit=None,
                            random_results=False):
        """
        Get days iterators with recording IDs of each day
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
        :param random_results: True to return result in random order
        :type random_results: bool
        :return: List of days iterators
        :rtype: list
        """
        content_filter = self._create_content_filter_func(metadata) if metadata else None

        id_prefixes = self._get_id_prefixes(category, start_date, end_date)

        return self.create_id_prefix_iterators(id_prefixes, start_date, end_date, content_filter, limit, random_results)

    def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None,
                           random_results=False):
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
        :param random_results: True to return result in random order
        :type random_results: bool
        :return: Iterator of keys matching the given parameters
        :rtype: collections.Iterator[basestring]
        """

        days_iterators = self._get_days_iterators(category, start_date, end_date, metadata, limit, random_results)

        count = 0
        iter_index = 0
        while count != limit and days_iterators:
            if random_results:
                random_day_iterator = random.choice(days_iterators)
            else:
                random_day_iterator = days_iterators[iter_index % len(days_iterators)]
                iter_index += 1
            key = next(random_day_iterator, None)
            if key:
                result = self._metadata_key_parser.parse(key)
                recording_id = result.named['id']
                _logger.info(u'Found filtered recording id {}'.format(recording_id))
                yield recording_id
                count += 1
            else:
                days_iterators.remove(random_day_iterator)

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
