from playback.tape_recorder import TapeRecorder


class RecordingLookupProperties(object):
    def __init__(self, start_date, end_date=None, metadata=None, limit=None, random_sample=False, skip_incomplete=True):
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
        :param skip_incomplete: True/False to skip recordings at incomplete state (TapeRecorder.INCOMPLETE_RECORDING)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.metadata = metadata
        self.limit = limit
        self.random_sample = random_sample
        self.skip_incomplete = skip_incomplete


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
    metadata = lookup_properties.metadata
    if lookup_properties.skip_incomplete:
        metadata = metadata or {}
        # We also add None to support recordings that were created before adding the INCOMPLETE_RECORDING metadata
        metadata[TapeRecorder.INCOMPLETE_RECORDING] = [False, None]
    recording_ids = tape_recorder.tape_cassette.iter_recording_ids(
            category, start_date=lookup_properties.start_date, end_date=lookup_properties.end_date,
            metadata=metadata,
            limit=lookup_properties.limit,
            random_results=lookup_properties.random_sample)

    return recording_ids
