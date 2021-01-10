from playback.recordings.memory.memory_recording import MemoryRecording
from time import sleep

from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette


class DelayedMemoryRecording(MemoryRecording):

    def __init__(self, delay):
        super(DelayedMemoryRecording, self).__init__()
        self.delay = delay

    def _set_data(self, key, value):
        """
        Sets data in the recording
        :param key: data key
        :type key: basestring
        :param value: data value (serializable)
        :type value: Any
        """
        sleep(self.delay)
        return super(DelayedMemoryRecording, self)._set_data(key, value)

    def _add_metadata(self, metadata):
        """
        :param metadata: Metadata to add to the recording
        :type metadata: dict
        """
        sleep(self.delay)
        return super(DelayedMemoryRecording, self)._add_metadata(metadata)


class DelayedInMemoryTapeCassette(InMemoryTapeCassette):
    """
    Add artificial delay of recording to in memory tape cassette, used for testing asynchronous implementations
    """

    def __init__(self, delay, *args, **kwargs):
        """
        :param delay: How much time to artificially delay recording invocations
        :type delay: float
        """
        super(DelayedInMemoryTapeCassette, self).__init__(*args, **kwargs)
        self.delay = delay

    def create_new_recording(self, category):
        """
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        :return: Creates a new recording object
        :rtype: playback.recording.Recording
        """
        return DelayedMemoryRecording(self.delay)

    def _save_recording(self, recording):
        """
        Saves given recording
        :param recording: Recording to save
        :type recording: playback.recording.Recording
        """
        sleep(self.delay)
        super(DelayedInMemoryTapeCassette, self)._save_recording(recording)
