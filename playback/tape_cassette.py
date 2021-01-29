from abc import ABCMeta, abstractmethod


class TapeCassette(object):
    """
    An abstract class that acts as a storage driver for TapeRecorder to store and fetch recordings
    """

    __metaclass__ = ABCMeta

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abstractmethod
    def get_recording(self, recording_id):
        """
        Get recording stored with the given id
        :param recording_id: If of recording to fetch
        :type recording_id: basestring
        :return: Recording of the given id
        :rtype: playback.recording.Recording
        :raises: playback.exceptions.NoSuchRecording
        """
        pass

    @abstractmethod
    def create_new_recording(self, category):
        """
        Creates a new recording object
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        :return: Creates a new recording object
        :rtype: playback.recording.Recording
        """
        pass

    def abort_recording(self, recording=None):
        # pylint: disable=no-self-use
        """
        Aborts given recording without saving it
        :param recording: Recording to abort
        :type recording: playback.recording.Recording
        """
        recording.close()

    def save_recording(self, recording):
        """
        Saves given recording
        :param recording: Recording to save
        :type recording: playback.recording.Recording
        """
        self._save_recording(recording)
        recording.close()

    @abstractmethod
    def _save_recording(self, recording):
        """
        Saves given recording
        :param recording: Recording to save
        :type recording: playback.recording.Recording
        """
        pass

    @abstractmethod
    def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None):
        """
        Creates an iterator of recording ids matching the given search parameters
        :param category: Recordings category
        :type category: str
        :param start_date: Optional recording start date (need to be given in utc time)
        :type start_date: datetime.datetime
        :param end_date: Optional recording end date (need to be given in utc time)
        :type end_date: datetime.datetime
        :param metadata: Optional metadata values to filter by
        :type metadata: dict
        :param limit: Optional limit on number of ids to fetch
        :type limit: int
        :return: Iterator of recording ids matching the given parameters
        :rtype: collections.Iterator[str]
        """
        pass

    @abstractmethod
    def extract_recording_category(self, recording_id):
        """
        :param recording_id: Recording id to extract category from
        :type recording_id: str
        :return: Recording's category
        :rtype: str
        """
        pass

    def close(self):
        """
        Close this cassette and release any underlying resources
        """
        pass
