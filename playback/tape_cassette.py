from abc import ABCMeta, abstractmethod
from fnmatch import fnmatch


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

    def get_recording_metadata(self, recording_id):
        """
        Get recording's metadata stored with the given id
        :param recording_id: If of recording to fetch
        :type recording_id: basestring
        :return: Recording of the given id
        :rtype: dict
        :raises: playback.exceptions.NoSuchRecording
        """
        return self.get_recording(recording_id).get_metadata()

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
    def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None,
                           random_results=False):
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
        :param random_results: True to return result in random order
        :type random_results: bool
        :return: Iterator of recording ids matching the given parameters
        :rtype: collections.Iterator[str]
        """
        pass

    def iter_recordings_metadata(self, category, start_date=None, end_date=None, metadata=None, limit=None):
        """
        Creates an iterator of recordings metadata matching the given search parameters
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
        :rtype: collections.Iterator[dict]
        """
        for recording_id in self.iter_recording_ids(
                category, start_date, end_date, metadata, limit):
            yield self.get_recording_metadata(recording_id)

    @staticmethod
    def match_against_recorded_metadata(filter_by_metadata, recording_metadata):
        """
        :param filter_by_metadata: Metadata to match against
        :type filter_by_metadata: dict
        :param recording_metadata: Metadata of a recording
        :type recording_metadata: dict
        :return: Whether the recorded metadata matches the filter metadata
        :rtype: bool
        """
        for k, v in filter_by_metadata.items():  # pylint: disable=invalid-name
            recorded_value = recording_metadata.get(k)
            if not TapeCassette._match_metadata_value(v, recorded_value):
                return False

        return True

    @staticmethod
    def _match_metadata_value(match_value, recorded_value):
        """
        :param match_value: metadata value to match against
        :param recorded_value: metadata value in the recording
        :return: If the recorded value matches the match value
        :rtype: bool
        """
        if isinstance(match_value, list):
            return any(TapeCassette._match_metadata_value(value, recorded_value) for value in match_value)

        if isinstance(match_value, dict) and 'operator' in match_value and 'value' in match_value:
            return TapeCassette._operator_filter(recorded_value, match_value)

        if recorded_value is None and match_value is not None:
            return False

        if isinstance(match_value, str):
            return fnmatch(recorded_value, match_value)

        return recorded_value == match_value

    @staticmethod
    def _operator_filter(recorded_value, metadata_value):
        """
        Check if this is an operator metadata filter and its value is in range
        """
        result = False
        if metadata_value['operator'] == '=':
            result = recorded_value == metadata_value['value']
        if metadata_value['operator'] == '<':
            result = recorded_value < metadata_value['value']
        if metadata_value['operator'] == '<=':
            result = recorded_value <= metadata_value['value']
        if metadata_value['operator'] == '>':
            result = recorded_value > metadata_value['value']
        if metadata_value['operator'] == '>=':
            result = recorded_value >= metadata_value['value']

        return result

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
