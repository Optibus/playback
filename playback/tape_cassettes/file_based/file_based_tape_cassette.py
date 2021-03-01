import os
import uuid
import io

import six
from jsonpickle import encode, decode

from playback.exceptions import NoSuchRecording
from playback.recordings.memory.memory_recording import MemoryRecording
from playback.tape_cassette import TapeCassette


class FileBasedTapeCassette(TapeCassette):
    """
    Implementation of TapeCassette that saves each recording in a file, mainly for playing around and testing,
    this is not production grade implementation.
    """
    def __init__(self, directory):
        if not os.path.isdir(directory):
            os.mkdir(directory)
        self.directory = directory

    def get_recording(self, recording_id):
        """
        Get recording stored in the given id
        :param recording_id: Id to look for the recording
        :type recording_id: basestring
        :return: Recording in the given id
        :rtype: playback.recording.Recording
        """
        file_path = self._get_recording_file_path(recording_id)
        if not os.path.isfile(file_path):
            raise NoSuchRecording(recording_id)

        with io.open(file_path, "r", encoding="utf-8") as f:
            encoded = f.read()
        deserialized_form = decode(encoded)
        return MemoryRecording(_id=deserialized_form.id, recording_data=deserialized_form.recording_data,
                               recording_metadata=deserialized_form.recording_metadata)

    def create_new_recording(self, category):
        """
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        :return: Creates a new recording object
        :rtype: playback.recording.Recording
        """
        return MemoryRecording(u'{}/{}'.format(category, uuid.uuid1().hex))

    def extract_recording_category(self, recording_id):
        """
        :param recording_id: Recording id to extract category from
        :type recording_id: str
        :return: Recording's category
        :rtype: str
        """
        return recording_id.split('/')[0]

    def _save_recording(self, recording):
        """
        Saves the given recording
        :param recording: Recording to save
        :type recording: playback.recording.Recording
        """
        encoded = six.text_type(encode(recording, unpicklable=True))
        with io.open(self._get_recording_file_path(recording.id), "w", encoding="utf-8") as f:
            f.write(encoded)

    def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None):
        """
        Creates an iterator of recording ids matching the given search parameters
        :param category: Recordings category
        :type category: str
        :param start_date: Not supported and will be ignored
        :type start_date: datetime.datetime
        :param end_date: Not supported and will be ignored
        :type end_date: datetime.datetime
        :param metadata: Optional metadata values to filter by
        :type metadata: dict
        :param limit: Optional limit on number of ids to fetch
        :type limit: int
        :return: Iterator of recording ids matching the given parameters
        :rtype: collections.Iterator[str]
        """
        ids = []
        for file_name in os.listdir(self.directory):
            if not file_name.startswith(category):
                continue

            recording_id = file_name.split('.')[0]
            recording = self.get_recording(recording_id)

            if metadata:
                # Filter based on metadata if provided
                if not all(metadata[key] == recording.get_metadata()[key] for key in metadata.keys()):
                    continue

            ids.append(recording.id)

        if limit:
            ids = ids[:limit]

        return iter(ids)

    def _get_recording_file_path(self, recording_id):
        """
        :param recording_id: Recording id
        :type recording_id: str
        :return: File path for given recording id
        :rtype: str
        """
        return os.path.join(self.directory, recording_id.replace('/', '_')) + '.json'
