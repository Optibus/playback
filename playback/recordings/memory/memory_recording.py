from playback.exceptions import RecordingKeyError
from playback.recording import Recording


class MemoryRecording(Recording):

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
