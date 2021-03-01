import uuid
from collections import OrderedDict
from jsonpickle import encode, decode

from playback.recordings.memory.memory_recording import MemoryRecording
from playback.tape_cassette import TapeCassette


class InMemoryTapeCassette(TapeCassette):
    """
    Implementation of TapeCassette that saves everything in memory, mainly for playing around and testing
    and not meant for production use
    """
    def __init__(self):
        self._recordings = OrderedDict()
        self._last_id = None

    def create_new_recording(self, category):
        """
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        :return: Creates a new recording object
        :rtype: playback.recording.Recording
        """
        return MemoryRecording(u'{}/{}'.format(category, uuid.uuid1().hex))

    def _save_recording(self, recording):
        """
        Saves given recording
        :param recording: Recording to save
        :type recording: playback.recording.Recording
        """
        # We use pickle serialization to find common serialization pitfalls when real cassettes will be used
        self._recordings[recording.id] = encode(recording, unpicklable=True)
        self._last_id = recording.id

    def get_recording(self, recording_id):
        """
        Get recording stored in the given id
        :param recording_id: Id to look for the recording
        :type recording_id: basestring
        :return: Recording in the given id
        :rtype: playback.recording.Recording
        """
        serialized_recording = self._recordings.get(recording_id)
        if serialized_recording is None:
            return None
        deserialized_form = decode(serialized_recording)
        return MemoryRecording(_id=deserialized_form.id, recording_data=deserialized_form.recording_data,
                               recording_metadata=deserialized_form.recording_metadata)

    def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None):
        result = []
        for serialized_recording in self._recordings.values():
            recording = decode(serialized_recording)
            if self.extract_recording_category(recording.id) != category:
                continue

            if metadata:
                # Filter based on metadata if provided
                if not all(metadata[key] == recording.get_metadata()[key] for key in metadata.keys()):
                    continue

            result.append(recording.id)

        if limit:
            result = result[:limit]

        return iter(result)

    def extract_recording_category(self, recording_id):
        """
        :param recording_id: Recording id to extract category from
        :type recording_id: str
        :return: Recording's category
        :rtype: str
        """
        return recording_id.split('/')[0]

    def get_last_recording_id(self):
        """
        :return: Last recording id
        :rtype: str
        """
        return self._last_id

    def get_all_recording_ids(self):
        """
        :return: All recording ids
        :rtype: list of str
        """
        return sorted(self._recordings.keys())
