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
