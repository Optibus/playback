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


def find_matching_recording_ids(tape_recorder, category, lookup_properties):
    """
    :param tape_recorder: Tape cassette holding the recordings
    :type tape_recorder: playback.tape_recorder.TapeRecorder
    :param category: Recording category
    :type category: basestring
    :param lookup_properties: Recording lookup properties
    :type lookup_properties: RecordingLookupProperties
    :return: Iterator of recording ids based on lookup parameters
    :rtype: collections.Iterator[str]
    """
    recording_ids = tape_recorder.tape_cassette.iter_recording_ids(
            category, start_date=lookup_properties.start_date, end_date=lookup_properties.end_date,
            metadata=lookup_properties.metadata,
            limit=(None if lookup_properties.random_sample else lookup_properties.limit))

    if lookup_properties.random_sample:
        recording_ids = list(recording_ids)
        shuffle(recording_ids)
        recording_ids = iter(recording_ids[:lookup_properties.limit])

    return recording_ids
