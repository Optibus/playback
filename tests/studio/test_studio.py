import unittest

from playback.studio.equalizer import ComparatorResult, EqualityStatus
from playback.studio.studio import PlaybackStudio, RecordingLookupProperties
from playback.studio.equalizer_tuning import EqualizerTuning, EqualizerTuner
from playback.tape_recorder import TapeRecorder
from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette


class TestPlaybackStudio(unittest.TestCase):

    def setUp(self):
        self.tape_cassette = InMemoryTapeCassette()
        self.tape_recorder = TapeRecorder(self.tape_cassette)
        self.tape_recorder.enable_recording()

    def tearDown(self):
        self.tape_cassette.close()

    def test_run_two_categories(self):
        self._test_run_two_operations(use_recording_ids=False)

    def test_run_specific_recording_ids(self):
        self._test_run_two_operations(use_recording_ids=True)

    def _test_run_two_operations(self, use_recording_ids):
        class A(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 'AAA'

        class B(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 'BBB'

        A().execute()
        A().execute()
        B().execute()

        if not use_recording_ids:
            categories = ['A', 'B']
            recording_ids = None
        else:
            categories = None
            recording_ids = self.tape_cassette.get_all_recording_ids()

        class MockEqualizerTuner(EqualizerTuner):

            def create_category_tuning(self, category):

                def result_extractor(outputs):
                    return next(o.value['args'][0] for o in outputs if TapeRecorder.OPERATION_OUTPUT_ALIAS in o.key)

                def comparator(expected, actual, message):
                    return ComparatorResult(EqualityStatus.Equal if expected == actual else EqualityStatus.Different,
                                            message)

                def comparison_data_extractor(recording):
                    return {'message': category}

                def playback_function(recording):
                    cls_name = recording.get_metadata()[TapeRecorder.OPERATION_CLASS]
                    if 'studio.A' in cls_name.values()[0]:
                        return A().execute()
                    return B().execute()

                return EqualizerTuning(
                    playback_function=playback_function, result_extractor=result_extractor, comparator=comparator,
                    comparison_data_extractor=comparison_data_extractor)

        equalizer_tuner = MockEqualizerTuner()
        start_date = 'a'
        studio = PlaybackStudio(categories, equalizer_tuner, self.tape_recorder,
                                lookup_properties=RecordingLookupProperties(start_date), recording_ids=recording_ids)
        result = studio.play()

        a_results = result['A']
        b_results = result['B']

        self.assertEquals(2, len(a_results))
        self.assertTrue(all('AAA' == result.actual for result in a_results))
        self.assertTrue(all('AAA' == result.expected for result in a_results))
        self.assertTrue(all(EqualityStatus.Equal == result.comparator_status.equality_status for result in a_results))
        self.assertTrue(all('A' == result.comparator_status.message for result in a_results))

        self.assertEquals(1, len(b_results))
        self.assertTrue(all('BBB' == result.actual for result in b_results))
        self.assertTrue(all('BBB' == result.expected for result in b_results))
        self.assertTrue(all(EqualityStatus.Equal == result.comparator_status.equality_status for result in b_results))
        self.assertTrue(all('B' == result.comparator_status.message for result in b_results))
