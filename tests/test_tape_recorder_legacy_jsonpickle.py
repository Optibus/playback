import unittest

from playback.exceptions import RecordingKeyError
from playback.recordings.memory.memory_recording import MemoryRecording
from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette
from playback.tape_recorder import TapeRecorder
from playback.utils.legacy_jsonpickle import _is_legacy_jsonpickle_installed
from tests.utils.legacy_jsonpickle_cases import KEY_ALIAS, KEY_FIXTURES_PATH, build_key_cases, load_fixtures

RECORDING_ID = 'Operation/legacy'


class SingleRecordingTapeCassette(InMemoryTapeCassette):

    def __init__(self, recording):
        super(SingleRecordingTapeCassette, self).__init__()
        self.recording = recording

    def get_recording(self, recording_id):
        return self.recording


class TestTapeRecorderLegacyJsonpickle(unittest.TestCase):

    def test_play_legacy_recording(self):
        results = self._play_all_cases(legacy_jsonpickle=True)

        for name in build_key_cases():
            if name == 'shared list and dict' and not _is_legacy_jsonpickle_installed():
                self.assertIsInstance(results[name], RecordingKeyError)
            else:
                self.assertEqual(name, results[name])

    @unittest.skipIf(_is_legacy_jsonpickle_installed(), 'jsonpickle 0.9.x makes the same keys as the recording')
    def test_recording_that_is_not_legacy_needs_exact_keys(self):
        results = self._play_all_cases(legacy_jsonpickle=False)

        self.assertIsInstance(results['dict'], RecordingKeyError)
        self.assertIsInstance(results['enum'], RecordingKeyError)
        self.assertEqual('shared list', results['shared list'])

    def _play_all_cases(self, legacy_jsonpickle):
        """
        Plays back a recording whose input keys were made by jsonpickle 0.9.4, and returns the value or the
        exception of each case
        """
        fixtures = load_fixtures(KEY_FIXTURES_PATH)
        recording_data = {fixture['key']: {'value': name} for name, fixture in fixtures.items()}
        recording = MemoryRecording(
            RECORDING_ID,
            recording_data=recording_data,
            recording_metadata={TapeRecorder.DURATION: 1},
            legacy_jsonpickle=legacy_jsonpickle,
        )
        tape_recorder = TapeRecorder(SingleRecordingTapeCassette(recording))
        results = {}

        class Operation(object):

            @tape_recorder.operation()
            def execute(self):
                for name, (args, kwargs) in build_key_cases().items():
                    try:
                        results[name] = self.get(*args, **kwargs)
                    except RecordingKeyError as ex:
                        results[name] = ex

            @tape_recorder.intercept_input(KEY_ALIAS)
            def get(self, *args, **kwargs):
                raise AssertionError('Playback must not run the intercepted method')

        tape_recorder.play(RECORDING_ID, playback_function=lambda recording: Operation().execute())
        return results
