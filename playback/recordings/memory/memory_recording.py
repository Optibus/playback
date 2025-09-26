import io
import logging
from contextlib import contextmanager
from copy import copy
from io import BufferedReader
from zlib import decompress, compress

import six
from jsonpickle import decode, encode

from playback.exceptions import RecordingKeyError
from playback.recording import Recording
from playback.utils.pickle_copy import pickle_copy

from playback.utils.timing_utils import Timed

_logger = logging.getLogger(__name__)


class MemoryRecording(Recording):
    @staticmethod
    def new(_id=None):
        return MemoryRecording(_id=_id)

    @staticmethod
    def from_buffered_reader(recording_id, buffered_reader, recording_metadata):
        _logger.info(u'Fetching compressed recording using key {}'.format(recording_id))
        compressed_recording = buffered_reader.read()

        _logger.info(u'Decompressing recording of key {}'.format(recording_id))
        serialized_data = decompress(compressed_recording)

        _logger.info(u'Decoding recording of key {}'.format(recording_id))
        full_data = decode(serialized_data)

        # remove metadata from the main recording
        full_data.pop('_metadata', {})

        _logger.info(u'Returning recording of key {}'.format(recording_id))
        return MemoryRecording(recording_id, recording_data=full_data, recording_metadata=recording_metadata)

    @contextmanager
    def as_buffered_reader(self):
        full_data = copy(self.recording_data)

        # We put meta data also in the full recording
        full_data['_metadata'] = self.recording_metadata

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

        _logger.info(u'Encoding recording of key {} took {} seconds'.format(self.id, encoding_duration))
        _logger.info(u'Compressing recording of key {} took {} seconds'.format(self.id, compression_duration))

        yield BufferedReader(io.BytesIO(compressed_full)), recording_size

    def __init__(self, _id=None, recording_data=None, recording_metadata=None):
        """
        :param _id: Id of the recording
        :type _id: str
        :param recording_data: On fetched recording this should contain the recorded data
        :type recording_data: dict
        :param recording_metadata: On fetched recording this should contain the recorded metadata
        :type recording_metadata: dict
        """
        super(MemoryRecording, self).__init__(_id=_id)
        self.recording_data = recording_data or {}
        self.recording_metadata = recording_metadata or {}
        self.recording_metadata['_recording_type'] = 'memory'

    def _set_data(self, key, value):
        """
        Sets data in the recording
        :param key: data key
        :type key: basestring
        :param value: data value (serializable)
        :type value: Any
        """
        self.recording_data[key] = value

    def get_data(self, key):
        """
        :param key: Data key
        :type key: basestring
        :return: Recorded data under given key
        :rtype: Any
        """
        # The contract of the recording requires the implementation to always return a fresh copy of the data.
        # It prevents in place modifications that may be done by the calling code to influence the outcome
        # of the recording playback. That's why we copy here.
        return pickle_copy(self.get_data_direct(key))

    def get_data_direct(self, key):
        """
        :param key: Data key
        :type key: basestring
        :return: Recorded data under given key
        :rtype: Any
        """
        if key not in self.recording_data:
            raise RecordingKeyError(u'Key \'{}\' not found in recording'.format(key).encode("utf-8"))

        return self.recording_data.get(key)

    def get_all_keys(self):
        """
        :return: All recorded keys
        :rtype: list of basestring
        """
        return self.recording_data.keys()

    def _add_metadata(self, metadata):
        """
        :param metadata: Metadata to add to the recording
        :type metadata: dict
        """
        self.recording_metadata.update(metadata)

    def get_metadata(self):
        """
        :return: Recorded metadata
        :rtype: dict
        """
        return self.recording_metadata
