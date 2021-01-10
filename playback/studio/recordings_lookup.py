from random import shuffle


class RecordingLookupProperties(object):
    def __init__(self, start_date, end_date=None, metadata=None, limit=None, random_sample=False):
        """
        :param start_date: Earliest date of recording
        :type start_date: datetime.datetime
        :param end_date: Latest date of recording
        :type end_date: datetime.datetime
        :param metadata: Optional metadata to filter recording by
        :type metadata: dict
        :param limit: Limit the number of recordings to fetch
        :type limit: int
        :param random_sample: True/False collect using random.shuffle (use random.seed to change selection)
        :type random_sample: boolean
        """
        self.start_date = start_date
        self.end_date = end_date
        self.metadata = metadata
        self.limit = limit
        self.random_sample = random_sample


def find_matching_playable_recordings(tape_recorder, playback_function, category, lookup_properties):
    """
    :param tape_recorder: Tape cassette holding the recordings
    :type tape_recorder: playback.tape_recorder.TapeRecorder
    :param playback_function: Function to replay operation based on recording
    :type playback_function: function
    :param category: Recording category
    :type category: basestring
    :param lookup_properties: Recording lookup properties
    :type lookup_properties: RecordingLookupProperties
    :return: Iterator of playable recordings based on lookup parameters
    :rtype: collections.Iterator[PlayableRecording]
    """
    recordings = tape_recorder.tape_cassette.iter_recording_ids(
            category, start_date=lookup_properties.start_date, end_date=lookup_properties.end_date,
            metadata=lookup_properties.metadata,
            limit=(None if lookup_properties.random_sample else lookup_properties.limit))

    if lookup_properties.random_sample:
        recordings = list(recordings)
        shuffle(recordings)
        recordings = iter(recordings[:lookup_properties.limit])

    for recording_id in recordings:

        def play():
            return tape_recorder.play(recording_id, playback_function)

        yield PlayableRecording(recording_id, play)


def by_id_playable_recordings(tape_recorder, playback_function, recording_ids):
    """
    :param tape_recorder: Tape cassette holding the recordings
    :type tape_recorder: playback.tape_recorder.TapeRecorder
    :param playback_function: Function to replay operation based on recording
    :type playback_function: function
    :param recording_ids: Recording ids to play
    :type recording_ids: list of basestring
    :return: Iterator of playable recordings based on given recording ids
    :rtype: collections.Iterator[PlayableRecording]
    """
    for recording_id in recording_ids:

        def play():
            return tape_recorder.play(recording_id, playback_function)

        yield PlayableRecording(recording_id, play)


class PlayableRecording(object):
    def __init__(self, recording_id, play):
        """
        :param recording_id: Recording id
        :type recording_id: basestring
        :param play: Plays the recording
        :type play: func
        """
        self.recording_id = recording_id
        self.play = play
