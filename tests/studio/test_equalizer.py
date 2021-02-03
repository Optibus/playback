# p3ready
from __future__ import absolute_import
import unittest

from contextlib2 import suppress
from datetime import datetime, timedelta
from mock import patch
import random
from parameterized import parameterized

from playback.studio.recordings_lookup import find_matching_recording_ids, RecordingLookupProperties

from playback.studio.equalizer import Equalizer, EqualityStatus, ComparatorResult, CompareExecutionConfig
from playback.tape_recorder import TapeRecorder
from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette
from six.moves import range


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

    @parameterized.expand([("compare_in_dedicated_process", True),
                           ("playback_same_process", False),
                           ])
    def test_equal_comparison(self, name, compare_in_dedicated_process):

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

        def player(recording_id):
            return self.tape_recorder.play(recording_id, playback_function)

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            end_date = datetime.utcnow() + timedelta(hours=1)
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(start_date=start_date, end_date=end_date),
            )

            runner = Equalizer(playable_recordings, player, result_extractor=return_value_result_extractor,
                               comparator=exact_comparator, 
                               compare_execution_config=CompareExecutionConfig(
                                   keep_results_in_comparison=True,
                                   compare_in_dedicated_process=compare_in_dedicated_process
                               ))

            with patch.object(Equalizer, '_play_and_compare_recording',
                              wraps=runner._play_and_compare_recording) as wrapped:
                comparison = list(runner.run_comparison())
            if compare_in_dedicated_process:
                wrapped.assert_not_called()
            else:
                wrapped.assert_called()

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

    @parameterized.expand([("compare_in_dedicated_process", True),
                           ("playback_same_process", False),
                           ])
    def test_with_exception_comparison(self, name, compare_in_dedicated_process):

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

            def player(recording_id):
                return self.tape_recorder.play(recording_id, playback_function)

            with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                              wraps=self.tape_cassette.iter_recording_ids):
                start_date = datetime.utcnow() - timedelta(hours=1)
                playable_recordings = find_matching_recording_ids(
                    self.tape_recorder,
                    category=Operation.__name__,
                    lookup_properties=RecordingLookupProperties(start_date=start_date),
                )
                runner = Equalizer(playable_recordings, player, result_extractor=return_value_result_extractor,
                                   comparator=exact_comparator, compare_execution_config=CompareExecutionConfig(
                                       keep_results_in_comparison=True,
                                       compare_in_dedicated_process=compare_in_dedicated_process
                                   ))

                comparison = list(runner.run_comparison())

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

    @parameterized.expand([("compare_in_dedicated_process", True),
                           ("playback_same_process", False),
                           ])
    def test_with_failure_comparison(self, name, compare_in_dedicated_process):

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

        def result_extractor(outputs):
            value = next(o.value['args'][0] for o in outputs if TapeRecorder.OPERATION_OUTPUT_ALIAS in o.key)
            if value == 4:
                raise Exception('extract error')
            return value

        def player(recording_id):
            return self.tape_recorder.play(recording_id, playback_function)

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            end_date = datetime.utcnow() + timedelta(hours=1)
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(start_date=start_date, end_date=end_date),
            )

            runner = Equalizer(playable_recordings, player, result_extractor=result_extractor,
                               comparator=exact_comparator,
                               compare_execution_config=CompareExecutionConfig(
                                   keep_results_in_comparison=False,
                                   compare_in_dedicated_process=compare_in_dedicated_process
                               ))

            with patch.object(Equalizer, '_play_and_compare_recording',
                              wraps=runner._play_and_compare_recording) as wrapped:
                comparison = list(runner.run_comparison())
            if compare_in_dedicated_process:
                wrapped.assert_not_called()
            else:
                wrapped.assert_called()

        self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Failed, comparison[1].comparator_status.equality_status)

        self.assertIsNone(comparison[0].expected)
        self.assertIsNone(comparison[0].actual)

    @parameterized.expand([("compare_in_dedicated_process", True),
                           ("playback_same_process", False),
                           ])
    def test_comparison_with_meta_and_limit_filtering(self, name, compare_in_dedicated_process):

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

        def player(recording_id):
            return self.tape_recorder.play(recording_id, playback_function)

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    metadata={'meta': 'b'},
                    limit=1),
            )
            runner = Equalizer(playable_recordings, player, result_extractor=return_value_result_extractor,
                               comparator=exact_comparator,
                               compare_execution_config=CompareExecutionConfig(
                                   keep_results_in_comparison=True,
                                   compare_in_dedicated_process=compare_in_dedicated_process
                               ))

            comparison = list(runner.run_comparison())

        self.assertEqual(1, len(comparison))
        self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)

        mock.assert_called_with(Operation.__name__, start_date=start_date, end_date=None,
                                limit=1, metadata={'meta': 'b'})
        self.assertEqual(4, comparison[0].expected)
        self.assertEqual(4, comparison[0].actual)

    @parameterized.expand([("compare_in_dedicated_process", True),
                           ("playback_same_process", False),
                           ])
    def test_equal_comparison_with_message(self, name, compare_in_dedicated_process):

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

        def player(recording_id):
            return self.tape_recorder.play(recording_id, playback_function)

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            end_date = datetime.utcnow() + timedelta(hours=1)
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    end_date=end_date)
            )
            runner = Equalizer(playable_recordings, player, result_extractor=return_value_result_extractor,
                               comparator=exact_comparator_with_message,
                               compare_execution_config=CompareExecutionConfig(
                                   keep_results_in_comparison=True,
                                   compare_in_dedicated_process=compare_in_dedicated_process
                               ))

            comparison = list(runner.run_comparison())

        self.assertEqual(EqualityStatus.Equal, comparison[0].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Different, comparison[1].comparator_status.equality_status)
        self.assertEqual(EqualityStatus.Failed, comparison[2].comparator_status.equality_status)

        self.assertEqual(EqualityStatus.Equal.name, comparison[0].comparator_status.message)
        self.assertEqual(EqualityStatus.Different.name, comparison[1].comparator_status.message)
        self.assertEqual(EqualityStatus.Failed.name, comparison[2].comparator_status.message)

    @parameterized.expand([("compare_in_dedicated_process", True),
                           ("playback_same_process", False),
                           ])
    def test_equal_comparison_comparator_data_extraction(self, name, compare_in_dedicated_process):

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

        def player(recording_id):
            return self.tape_recorder.play(recording_id, playback_function)

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
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    end_date=end_date)
            )
            runner = Equalizer(playable_recordings, player, result_extractor=return_value_result_extractor,
                               comparator=exact_comparator_with_multiplier,
                               comparison_data_extractor=comparison_data_extractor,
                               compare_execution_config=CompareExecutionConfig(
                                   keep_results_in_comparison=True,
                                   compare_in_dedicated_process=compare_in_dedicated_process
                               ))

            comparison = list(runner.run_comparison())

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
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    random_sample=True,
                    limit=3)
            )
            first_list = list(playable_recordings)
            self.assertEqual(len(first_list), 3)

        random.seed(4)
        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(
                    start_date=start_date,
                    random_sample=True,
                    limit=3)
            )
            second_list = list(playable_recordings)
            self.assertNotEqual(second_list, first_list)

    @parameterized.expand([("compare_in_dedicated_process", True),
                           ("playback_same_process", False),
                           ])
    def test_run_with_specific_ids(self, name, compare_in_dedicated_process):

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

        def player(recording_id):
            return self.tape_recorder.play(recording_id, playback_function)

        runner = Equalizer([id1, id2], player, result_extractor=return_value_result_extractor,
                           comparator=exact_comparator,
                           compare_execution_config=CompareExecutionConfig(
                               keep_results_in_comparison=True,
                               compare_in_dedicated_process=compare_in_dedicated_process
                           ))

        comparison = list(runner.run_comparison())

        self.assertEqual(id1, comparison[0].playback.original_recording.id)
        self.assertEqual(id2, comparison[1].playback.original_recording.id)
        self.assertEqual(2, len(comparison))

    def test_equalizer_recycle_process_thread(self):
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

        for i in range(20):
            Operation(i).execute()

        def playback_function(recording):
            return Operation().execute()

        def player(recording_id):
            return self.tape_recorder.play(recording_id, playback_function)

        with patch.object(InMemoryTapeCassette, 'iter_recording_ids',
                          wraps=self.tape_cassette.iter_recording_ids) as mock:
            start_date = datetime.utcnow() - timedelta(hours=1)
            end_date = datetime.utcnow() + timedelta(hours=1)
            playable_recordings = find_matching_recording_ids(
                self.tape_recorder,
                category=Operation.__name__,
                lookup_properties=RecordingLookupProperties(start_date=start_date, end_date=end_date),
            )

            runner = Equalizer(playable_recordings, player, result_extractor=return_value_result_extractor,
                               comparator=exact_comparator,
                               compare_execution_config=CompareExecutionConfig(
                                   keep_results_in_comparison=True,
                                   compare_in_dedicated_process=True,
                                   compare_process_recycle_rate=2
                               ))

            with patch.object(Equalizer, '_create_new_player_process',
                              wraps=runner._create_new_player_process) as wrapped:
                comparison = list(runner.run_comparison())

            self.assertEqual(10, wrapped.call_count)

        self.assertEqual(20, len(comparison))
        for c in comparison:
            self.assertEqual(EqualityStatus.Equal, c.comparator_status.equality_status)