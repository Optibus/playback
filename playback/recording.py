import uuid
from abc import ABCMeta, abstractmethod


class Recording(object):
    """
    Holds a recording of an operation that was recorded using the TapeRecorder
    """

    __metaclass__ = ABCMeta

    def __init__(self, _id=None):
        self.id = _id or uuid.uuid1().hex
        self._closed = False

    @staticmethod
    @abstractmethod
    def new(_id=None):
        """
        Creates a new recording instance.

        :param _id: Optional ID for the recording. If not provided, a new UUID will be generated.
        :type _id: str
        :return: A new Recording instance.
        :rtype: Recording
        """

    @staticmethod
    @abstractmethod
    def from_buffered_reader(recording_id, buffered_reader, recording_metadata):
        """
        Fetches, decompresses, decodes, and prepares a recording from a buffered reader.

        :param recording_id: The ID of the recording to fetch.
        :type recording_id: str
        :param buffered_reader: A buffered reader instance to read the compressed recording data.
        :type buffered_reader: BufferedReader
        :param recording_metadata: Metadata that could optionally override or append to the extracted
            metadata from the recording.
        :type recording_metadata: dict
        :return: A new MemoryRecording instance containing the fetched recording and its metadata.
        :rtype: MemoryRecording
        """
        pass

    @abstractmethod
    def as_buffered_reader(self):
        """
        Gives access to the recording data as a BufferedReader.

        :returns: A buffered reader instance for reading the recording data.
        :rtype: BufferedReader
        """
        pass

    @abstractmethod
    def _set_data(self, key, value):
        """
        Sets data in the recording
        :param key: data key
        :type key: basestring
        :param value: data value (serializable)
        :type value: Any
        """
        pass

    def set_data(self, key, value):
        """
        Sets data in the recording
        :param key: data key
        :type key: basestring
        :param value: data value (serializable)
        :type value: Any
        """
        assert not self._closed
        self._set_data(key, value)

    @abstractmethod
    def get_data(self, key):
        """
        Should always return a fresh copy of the data event when called multiple times with the same key,
        to prevent modifications of the recording by the calling code. These modifications can lead to differences in
        outputs that are not expected and will yield false positives.
        :param key: Data key
        :type key: basestring
        :return: Recorded data under given key
        :rtype: Any
        :raise: playback.exceptions.RecordingKeyError
        """
        pass

    @abstractmethod
    def get_data_direct(self, key):
        """
        Get the data directly from the recording with necessarily copying it, this should be used with care for
        performance reasons, mainly to be accessed during the recording stage as it can return the underlying saved
        data and not a copy
        :param key: Data key
        :type key: basestring
        :return: Recorded data under given key
        :rtype: Any
        :raise: playback.exceptions.RecordingKeyError
        """
        pass

    @abstractmethod
    def get_all_keys(self):
        """
        :return: All recorded keys
        :rtype: list of basestring
        """
        pass

    def add_metadata(self, metadata):
        """
        :param metadata: Metadata to add to the recording
        :type metadata: dict
        """
        assert not self._closed
        self._add_metadata(metadata)

    @abstractmethod
    def _add_metadata(self, metadata):
        """
        :param metadata: Metadata to add to the recording
        :type metadata: dict
        """
        pass

    def close(self):
        """
        Close the recording and release any underlying resources
        """
        self._closed = True

    def __setitem__(self, key, value):
        self._set_data(key, value)

    def __getitem__(self, item):
        return self.get_data(item)

    @abstractmethod
    def get_metadata(self):
        """
        :return: Recorded metadata
        :rtype: dict
        """
        pass
