import unittest

from contextlib2 import suppress
from datetime import datetime, timedelta
from mock import patch
import random

from playback.studio.recordings_lookup import find_matching_playable_recordings, \
    by_id_playable_recordings, RecordingLookupProperties

from playback.studio.equalizer import Equalizer, EqualityStatus, ComparatorResult
from playback.tape_recorder import TapeRecorder
from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette


def exact_comparator(recorded_result, playback_result):
    if type(recorded_result) != type(playback_result):
        return EqualityStatus.Different
    diff = abs(recorded_result - playback_result)
    if diff == 0:
        return EqualityStatus.Equal
    if diff <= 10:
        return EqualityStatus.Different
    return EqualityStatus.Failed


def exact_comparator_with_message(recorded_result, playback_result):
    result = exact_comparator(recorded_result, playback_result)
    return ComparatorResult(result, result.name)


def return_value_result_extractor(outputs):
    return next(o.value['args'][0] for o in outputs if TapeRecorder.OPERATION_OUTPUT_ALIAS in o.key)


class TestEqualizer(unittest.TestCase):

    def setUp(self):
        self.tape_cassette = InMemoryTapeCassette()
        self.tape_recorder = TapeRecorder(self.tape_cassette)
        self.tape_recorder.enable_recording()

    def tearDown(self):
        self.tape_cassette.close()

    def test_equal_comparison(self):

        class Operation(object):
            def __init__(self, value=None, multiply_input=1):
                self._value = value
                self.multiply_input = multiply_input

            @property
            @self.tape_recorder.intercept_input('input')
            def input(self):
                return self._value

            @self.tape_recorder.operation()
            def execute(self):
                return self.input * self.multiply_input

        Operation(3).execute()
        Operation(4).execute()
        Operation(5).execute()

        playback_counter = [0]

        def playback_function(recording):
            playback_counter[0] += 1
            if playback_counter[0] == 2:
                operation = Operation(multiply_input=2)
            elif playback_counter[0] == 3:
                operation = Operation(multiply_input=100)
            else:
                operation = Operation()
            return operation.execute()

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            end_date = datetime.utcnow() + timedelta(hours=1)
            playable_recordings = find_matching_playable_recordings(
                self.tape_recorder,
                playback_function,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(start_date=start_date, end_date=end_date),
            )
            runner = Equalizer(playable_recordings,
                               result_extractor=return_value_result_extractor,
                               comparator=exact_comparator)

            comparison = runner.run_comparison()

        self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Different, comparison[1].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Failed, comparison[2].comparator_status.equality_status)

        self.assertEqual(3, comparison[0].expected)
        self.assertEqual(4, comparison[1].expected)
        self.assertEqual(5, comparison[2].expected)

        self.assertEqual(3, comparison[0].actual)
        self.assertEqual(8, comparison[1].actual)
        self.assertEqual(500, comparison[2].actual)

        mock.assert_called_with(Operation.__name__, start_date=start_date, end_date=end_date, limit=None, metadata=None)
        self.assertGreaterEqual(comparison[0].playback.playback_duration, 0)
        self.assertGreaterEqual(comparison[0].playback.recorded_duration, 0)

    def test_with_exception_comparison(self):

            class Operation(object):
                def __init__(self, value=None, raise_error=None):
                    self._value = value
                    self.raise_error = raise_error

                @property
                @self.tape_recorder.intercept_input('input')
                def input(self):
                    return self._value

                @self.tape_recorder.operation()
                def execute(self, value=None):
                    if self.raise_error:
                        raise Exception("error")
                    if value is not None:
                        return value
                    return self.input

            Operation(3).execute()
            Operation(4).execute()
            with suppress(Exception):
                Operation(raise_error=True).execute()

            playback_counter = [0]

            def playback_function(recording):
                playback_counter[0] += 1
                if playback_counter[0] == 2:
                    operation = Operation(raise_error=True)
                elif playback_counter[0] == 3:
                    return Operation().execute(5)
                else:
                    operation = Operation()
                return operation.execute()

            with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                              wraps=self.tape_cassette.iter_recording_ids):
                start_date = datetime.utcnow() - timedelta(hours=1)
                playable_recordings = find_matching_playable_recordings(
                    self.tape_recorder,
                    playback_function,
                    category=Operation.__name__,
                    lookup_properties=RecordingLookupProperties(start_date=start_date),
                )
                runner = Equalizer(playable_recordings,
                                   result_extractor=return_value_result_extractor,
                                   comparator=exact_comparator)

                comparison = runner.run_comparison()

            self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)
            self.assertEqual(EqualityStatus.Different, comparison[1].comparator_status.equality_status)
            self.assertEqual(EqualityStatus.Different, comparison[2].comparator_status.equality_status)

            self.assertEqual(3, comparison[0].expected)
            self.assertEqual(4, comparison[1].expected)
            self.assertIsInstance(comparison[2].expected, Exception)
            self.assertTrue(comparison[1].actual_is_exception)
            self.assertFalse(comparison[1].expected_is_exception)

            self.assertEqual(3, comparison[0].actual)
            self.assertIsInstance(comparison[1].actual, Exception)
            self.assertEqual(5, comparison[2].actual)
            self.assertFalse(comparison[2].actual_is_exception)
            self.assertTrue(comparison[2].expected_is_exception)

    def test_comparison_with_meta_and_limit_filtering(self):

        class Operation(object):
            def __init__(self, value=None):
                self._value = value

            @property
            @self.tape_recorder.intercept_input('input')
            def input(self):
                return self._value

            @self.tape_recorder.operation(metadata_extractor=lambda op_self, meta=None: {'meta': meta})
            def execute(self, meta=None):
                return self.input

        Operation(3).execute('a')
        Operation(4).execute('b')
        Operation(5).execute('b')

        def playback_function(recording):
            return Operation().execute()

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            playable_recordings = find_matching_playable_recordings(
                self.tape_recorder,
                playback_function,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    metadata={'meta': 'b'},
                    limit=1),
            )
            runner = Equalizer(playable_recordings,
                               result_extractor=return_value_result_extractor,
                               comparator=exact_comparator)

            comparison = runner.run_comparison()

        self.assertEqual(1, len(comparison))
        self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)

        mock.assert_called_with(Operation.__name__, start_date=start_date, end_date=None,
                                limit=1, metadata={'meta': 'b'})
        self.assertEqual(4, comparison[0].expected)
        self.assertEqual(4, comparison[0].actual)

    def test_equal_comparison_with_message(self):

        class Operation(object):
            def __init__(self, value=None, multiply_input=1):
                self._value = value
                self.multiply_input = multiply_input

            @property
            @self.tape_recorder.intercept_input('input')
            def input(self):
                return self._value

            @self.tape_recorder.operation()
            def execute(self):
                return self.input * self.multiply_input

        Operation(3).execute()
        Operation(4).execute()
        Operation(5).execute()

        playback_counter = [0]

        def playback_function(recording):
            playback_counter[0] += 1
            if playback_counter[0] == 2:
                operation = Operation(multiply_input=2)
            elif playback_counter[0] == 3:
                operation = Operation(multiply_input=100)
            else:
                operation = Operation()
            return operation.execute()

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            end_date = datetime.utcnow() + timedelta(hours=1)
            playable_recordings = find_matching_playable_recordings(
                self.tape_recorder,
                playback_function,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    end_date=end_date)
            )
            runner = Equalizer(playable_recordings,
                               result_extractor=return_value_result_extractor,
                               comparator=exact_comparator_with_message)

            comparison = runner.run_comparison()

        self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Different, comparison[1].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Failed, comparison[2].comparator_status.equality_status)

        self.assertEqual(EqualityStatus.Equal.name, comparison[0].comparator_status.message)
        self.assertEqual(EqualityStatus.Different.name, comparison[1].comparator_status.message)
        self.assertEqual(EqualityStatus.Failed.name, comparison[2].comparator_status.message)

    def test_equal_comparison_comparator_data_extraction(self):

        class Operation(object):
            def __init__(self, value=None, override_input=None):
                self._value = value
                self.override_input = override_input

            @property
            @self.tape_recorder.intercept_input('input')
            def input(self):
                return self._value

            @self.tape_recorder.operation()
            def execute(self):
                if self.override_input:
                    return self.override_input
                return self.input

        Operation(3).execute()
        Operation(4).execute()
        Operation(5).execute()

        playback_counter = [0]

        def playback_function(recording):
            playback_counter[0] += 1
            if playback_counter[0] == 2:
                operation = Operation(override_input=100)
            else:
                operation = Operation()
            return operation.execute()

        def comparison_data_extractor(recording):
            self.assertIsNotNone(recording)
            return {'multiplier': 1}

        def exact_comparator_with_multiplier(recorded_result, playback_result, multiplier):
            if playback_result >= 10:
                playback_result *= 0
                recorded_result *= 0
            else:
                playback_result *= multiplier
                recorded_result *= multiplier

            return ComparatorResult(
                EqualityStatus.Equal if recorded_result * multiplier == playback_result * multiplier
                else EqualityStatus.Different, str(multiplier))

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            end_date = datetime.utcnow() + timedelta(hours=1)
            playable_recordings = find_matching_playable_recordings(
                self.tape_recorder,
                playback_function,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    end_date=end_date)
            )
            runner = Equalizer(playable_recordings,
                               result_extractor=return_value_result_extractor,
                               comparator=exact_comparator_with_multiplier,
                               comparison_data_extractor=comparison_data_extractor)

            comparison = runner.run_comparison()

        self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Equal, comparison[1].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Equal, comparison[2].comparator_status.equality_status)

        self.assertEqual('1', comparison[0].comparator_status.message)
        self.assertEqual('1', comparison[1].comparator_status.message)
        self.assertEqual('1', comparison[2].comparator_status.message)

    def test_random_sample(self):

        class Operation(object):
            def __init__(self, value=None):
                self._value = value

            @property
            @self.tape_recorder.intercept_input('input')
            def input(self):
                return self._value

            @self.tape_recorder.operation()
            def execute(self):
                return self.input

        for i in range(10):
            Operation(i).execute()

        def playback_function(recording):
            return Operation().execute()
        random.seed(12)
        first_list = None
        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            playable_recordings = find_matching_playable_recordings(
                self.tape_recorder,
                playback_function,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    random_sample=True,
                    limit=3)
            )
            first_list = map(lambda x: x.recording_id, list(playable_recordings))
            self.assertEqual(len(first_list), 3)

        random.seed(4)
        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            playable_recordings = find_matching_playable_recordings(
                self.tape_recorder,
                playback_function,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    random_sample=True,
                    limit=3)
            )
            second_list = map(lambda x: x.recording_id, list(playable_recordings))
            self.assertNotEqual(second_list, first_list)

    def test_run_with_specific_ids(self):

        class Operation(object):
            def __init__(self, value=None, override_input=None):
                self._value = value
                self.override_input = override_input

            @property
            @self.tape_recorder.intercept_input('input')
            def input(self):
                return self._value

            @self.tape_recorder.operation()
            def execute(self):
                if self.override_input:
                    return self.override_input
                return self.input

        Operation(3).execute()
        id1 = self.tape_cassette.get_last_recording_id()
        Operation(4).execute()
        Operation(5).execute()
        id2 = self.tape_cassette.get_last_recording_id()
        Operation(6).execute()

        playback_counter = [0]

        def playback_function(recording):
            playback_counter[0] += 1
            if playback_counter[0] == 2:
                operation = Operation(override_input=100)
            else:
                operation = Operation()
            return operation.execute()

        playable_recordings = by_id_playable_recordings(self.tape_recorder, playback_function, [id1, id2])
        runner = Equalizer(playable_recordings,
                           result_extractor=return_value_result_extractor,
                           comparator=exact_comparator)

        comparison = runner.run_comparison()

        self.assertEqual(id1, comparison[0].playback.original_recording.id)
        self.assertEqual(id2, comparison[1].playback.original_recording.id)
        self.assertEqual(2, len(comparison))
