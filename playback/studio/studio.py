from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
from playback.studio.equalizer import Equalizer
from playback.studio.recordings_lookup import find_matching_playable_recordings, \
    by_id_playable_recordings, RecordingLookupProperties
import logging

_logger = logging.getLogger(__name__)


class PlaybackStudio(object):
    """
    Studio that runs multiple playbacks for multiple category using the equalizer to run comparison
    """
    DEFAULT_LOOKUP_PROPERTIES = RecordingLookupProperties(
        start_date=datetime.utcnow() - timedelta(days=7), limit=20)

    def __init__(self, categories, equalizer_tuner, tape_recorder, lookup_properties=None, recording_ids=None):
        """
        :param categories: Categories to play
        :type categories: list of str
        :param recording_ids: List of specific recording ids to play, when given categories are ignored
        :type recording_ids: list of str
        :param equalizer_tuner: Given a recording return a corresponding tuning
        :type equalizer_tuner: playback.studio.equalizer_tuning.EqualizerTuner
        :param lookup_properties: Lookup properties to use for all recordings
        :type lookup_properties: RecordingLookupProperties
        :param tape_recorder: Tape recorder used to play recordings
        :type tape_recorder: playback.tape_recorder.TapeRecorder
        """
        self.categories = categories
        self.recording_ids = recording_ids
        self.equalizer_tuner = equalizer_tuner
        self.lookup_properties = lookup_properties or self.DEFAULT_LOOKUP_PROPERTIES
        self.tape_recorder = tape_recorder

    def play(self):
        """
        Fetch and play recording of all categories and run comparison on each one
        :return: Comparison per category of all playbacks
        :rtype: dict[basestring, (list of playback.studio.equalizer.Comparison) or Exception]
        """
        if self.recording_ids:
            categories_recordings = self._group_recording_ids_by_categories()
        else:
            categories_recordings = {c: None for c in self.categories}

        result = {}
        for category, recording_ids in categories_recordings.items():
            result[category] = self._play_category(category, recording_ids)
        return result

    def _group_recording_ids_by_categories(self):
        """
        :return: Recording ids groups by categories
        :rtype: dict[str, list of str]
        """
        grouping = defaultdict(list)
        for recording_id in self.recording_ids:
            category = self.tape_recorder.tape_cassette.extract_recording_category(recording_id)
            grouping[category].append(recording_id)
        # We want deterministic order of playback
        return OrderedDict(sorted(grouping.items()))

    def _play_category(self, category, recording_ids):
        """
        Play and compare recordings of a single category
        :param category: Category to play
        :type category: str
        :param recording_ids: List of specific recording ids to play, None means to fetch recordings using the
        lookup parameters
        :type recording_ids: None or list of str
        :return: Comparison of all playback of current category
        :rtype: (list of playback.studio.equalizer.Comparison) or Exception
        """
        _logger.info(u'Playing Category {}'.format(category))
        try:
            tuning = self.equalizer_tuner.create_category_tuning(category)
        except Exception as ex:
            _logger.info(u'Cannot tune equalizer for category {} - {}'.format(category, ex))
            return ex

        if recording_ids:
            playable_recordings = by_id_playable_recordings(
                self.tape_recorder, tuning.playback_function, recording_ids)
        else:
            playable_recordings = find_matching_playable_recordings(
                self.tape_recorder, tuning.playback_function, category, self.lookup_properties)

        equalizer = Equalizer(playable_recordings, tuning.result_extractor, tuning.comparator,
                              comparison_data_extractor=tuning.comparison_data_extractor)
        return equalizer.run_comparison()
