# p3ready
from __future__ import absolute_import
from __future__ import print_function
import unittest
from random import shuffle, random

from jsonpickle import encode, decode
from mock import patch
from playback.exceptions import InputInterceptionKeyCreationError, RecordingKeyError
from playback.interception.input_interception import InputInterceptionDataHandler
from time import sleep

from playback.interception.output_interception import OutputInterceptionDataHandler
from playback.tape_recorder import TapeRecorder, CapturedArg, RecordingParameters, pickle_copy
from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette
import six
from six.moves import range


class TestTapeRecorder(unittest.TestCase):

    def setUp(self):
        self.tape_cassette = InMemoryTapeCassette()
        self.tape_recorder = TapeRecorder(self.tape_cassette)
        self.tape_recorder.enable_recording()

    def test_record_and_playback_basic_operation_no_parameters(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 5

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def _assert_playback_vs_recording(self, playback_result, result):
        """
        :param playback_result: Playback result
        :type playback_result: playback.tape_recorder.Playback
        :param result: Operation result
        :type result: Any
        """
        if six.PY3:
            self.assertCountEqual(playback_result.recorded_outputs, playback_result.playback_outputs)
        else:
            self.assertItemsEqual(playback_result.recorded_outputs, playback_result.playback_outputs)

        operation_output = next(po for po in playback_result.playback_outputs
                                if TapeRecorder.OPERATION_OUTPUT_ALIAS in po.key)
        self.assertEqual(result, operation_output.value['args'][0])
        self.assertGreater(playback_result.playback_duration, 0)
        self.assertGreater(playback_result.recorded_duration, 0)

    def test_record_and_playback_basic_operation_data_interception_no_arguments(self):
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value()

            @self.tape_recorder.intercept_input('input')
            def get_value(self):
                return self.seed

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_data_interception_property(self):
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value

            @self.tape_recorder.intercept_input('input')
            @property
            def get_value(self):
                return self.seed

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_data_interception_with_arguments(self):
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                val1 = self.get_value(2, b=3)
                val2 = self.get_value(4, b=6)
                return val1 + val2

            @self.tape_recorder.intercept_input('input')
            def get_value(self, a, b=2):
                return (a + b) * self.seed

        instance = Operation(seed=1)
        result = instance.execute()
        self.assertEqual(15, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_static_data_interception_with_arguments(self):
        class Operation(object):

            seed = 0

            @self.tape_recorder.operation()
            def execute(self):
                val1 = self.get_value(2, b=3)
                val2 = self.get_value(4, b=6)
                return val1 + val2

            @staticmethod
            @self.tape_recorder.static_intercept_input('input')
            def get_value(a, b=2):
                return (a + b) * Operation.seed

        instance = Operation()
        Operation.seed = 1
        result = instance.execute()
        self.assertEqual(15, result)

        Operation.seed = 0
        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_data_interception_with_arguments_and_metadata(self):
        def operation_metadata_extractor(obj):
            return {'type': type(obj)}

        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation(metadata_extractor=operation_metadata_extractor)
            def execute(self):
                val1 = self.get_value(2, b=3)
                val2 = self.get_value(4, b=6)
                return val1 + val2

            @self.tape_recorder.intercept_input('input')
            def get_value(self, a, b=2):
                return (a + b) * self.seed

        instance = Operation(seed=1)
        result = instance.execute()
        self.assertEqual(15, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        recording = self.tape_cassette.get_recording(recording_id)
        # pickle encode decode doesn't reconstruct actuall class if this is an inner class
        operation_decoded = decode(encode(Operation, unpicklable=False))
        self.assertDictContainsSubset({'type': operation_decoded, TapeRecorder.OPERATION_CLASS: operation_decoded},
                                      recording.get_metadata())
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_no_parameters_with_output(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                x = 0
                x += self.output(4, arg='a')
                x += self.output(3, arg='b')
                return x

            @self.tape_recorder.intercept_output('output_function')
            def output(self, value, arg=None):
                return value

        instance = Operation()
        result = instance.execute()
        self.assertEqual(7, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)

        self.assertEqual({'args': [4], 'kwargs': {'arg': 'a'}}, playback_result.playback_outputs[0].value)
        self.assertEqual({'args': [3], 'kwargs': {'arg': 'b'}}, playback_result.playback_outputs[1].value)
        self.assertNotEqual(playback_result.playback_outputs[0].key, playback_result.playback_outputs[1].key)
        self.assertIn('output_function', playback_result.playback_outputs[0].key)
        self.assertIn('output_function', playback_result.playback_outputs[1].key)

    def test_record_and_playback_basic_operation_no_parameters_with_static_output(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                x = 0
                x += self.output(4, arg='a')
                x += self.output(3, arg='b')
                return x

            @staticmethod
            @self.tape_recorder.static_intercept_output('output_function')
            def output(value, arg=None):
                return value

        instance = Operation()
        result = instance.execute()
        self.assertEqual(7, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)

        self.assertEqual({'args': [4], 'kwargs': {'arg': 'a'}}, playback_result.playback_outputs[0].value)
        self.assertEqual({'args': [3], 'kwargs': {'arg': 'b'}}, playback_result.playback_outputs[1].value)
        self.assertNotEqual(playback_result.playback_outputs[0].key, playback_result.playback_outputs[1].key)
        self.assertIn('output_function', playback_result.playback_outputs[0].key)
        self.assertIn('output_function', playback_result.playback_outputs[1].key)

    def test_record_and_playback_basic_operation_similar_duration(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                sleep(0.5)
                return 5

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self.assertLessEqual(abs(playback_result.recorded_duration - playback_result.playback_duration), 0.1)

    def test_record_and_playback_basic_operation_class_extraction_in_metadata(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 5

            @classmethod
            @self.tape_recorder.class_operation()
            def class_execute(cls):
                return 5

        instance = Operation()
        self.assertEqual(5, instance.execute())

        recording_id = self.tape_cassette.get_last_recording_id()
        recording = self.tape_cassette.get_recording(recording_id)
        # pickle encode decode doesn't reconstruct actuall class if this is an inner class
        operation_decoded = decode(encode(Operation, unpicklable=False))
        self.assertDictContainsSubset({TapeRecorder.OPERATION_CLASS: operation_decoded}, recording.get_metadata())

        self.assertEqual(5, instance.class_execute())

        recording_id = self.tape_cassette.get_last_recording_id()
        recording = self.tape_cassette.get_recording(recording_id)
        # Inner classes are not unpicklable back to class upon decode
        self.assertDictContainsSubset({TapeRecorder.OPERATION_CLASS: operation_decoded}, recording.get_metadata())

    def test_drop_recording_direct_api_call(self):
        local_tape_recorder = self.tape_recorder

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                local_tape_recorder.discard_recording()
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, '_save_recording', wraps=self.tape_cassette._save_recording) \
                as intercepted_save, \
                patch.object(InMemoryTapeCassette, 'abort_recording', wraps=self.tape_cassette.abort_recording) \
                as intercepted_abort:
            result = instance.execute()
            intercepted_save.assert_not_called()
            intercepted_abort.assert_called()

        self.assertEqual(5, result)

    def test_skip_recording_decorator(self):

        @self.tape_recorder.recording_params(RecordingParameters(skipped=True))
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, 'create_new_recording', wraps=self.tape_cassette.create_new_recording) \
                as intercepted:
            result = instance.execute()
            intercepted.assert_not_called()

        self.assertEqual(5, result)

    def test_skip_recording_decorator_compatible(self):
        @self.tape_recorder.recording_params(skipped=True)
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, 'create_new_recording', wraps=self.tape_cassette.create_new_recording) \
                as intercepted:
            result = instance.execute()
            intercepted.assert_not_called()

        self.assertEqual(5, result)

    def test_input_interception_key_failure(self):

        class UnencodeableObject(object):
            def __getstate__(self):
                raise Exception()

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                param = UnencodeableObject()
                value = self.input(param)
                return value

            @self.tape_recorder.intercept_input('input')
            def input(self, param):
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, '_save_recording', wraps=self.tape_cassette._save_recording) \
                as intercepted_save, \
                patch.object(InMemoryTapeCassette, 'abort_recording', wraps=self.tape_cassette.abort_recording) \
                as intercepted_abort:
            result = instance.execute()
            intercepted_save.assert_not_called()
            intercepted_abort.assert_called()

        self.assertEqual(5, result)

    def test_input_interception_key_failure_during_playback(self):

        class UnencodeableObject(object):
            def __getstate__(self):
                raise Exception()

        class Operation(object):

            def __init__(self, raise_on_get=False):
                self.raise_on_get = raise_on_get

            @self.tape_recorder.operation()
            def execute(self):
                param = UnencodeableObject() if self.raise_on_get else object()
                value = self.input(param)
                return value

            @self.tape_recorder.intercept_input('input')
            def input(self, param):
                return 5

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        with self.assertRaises(InputInterceptionKeyCreationError):
            self.tape_recorder.play(recording_id, playback_function=lambda recording: Operation(True).execute())

    def test_input_interception_key_missing_during_playback(self):

        class Operation(object):

            def __init__(self, input_key):
                self.input_key = input_key

            @self.tape_recorder.operation()
            def execute(self):
                value = self.input(self.input_key)
                return value

            @self.tape_recorder.intercept_input('input')
            def input(self, param):
                return 5

        instance = Operation('key1')
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        with self.assertRaises(RecordingKeyError):
            self.tape_recorder.play(recording_id, playback_function=lambda recording: Operation('key2').execute())

    def test_output_interception_key_missing_during_playback(self):

        class Operation(object):

            def __init__(self, output_method):
                self.output_method = output_method

            @self.tape_recorder.operation()
            def execute(self):
                value = getattr(self, self.output_method)()
                return value

            @self.tape_recorder.intercept_output('output_function')
            def output(self):
                return 5

            @self.tape_recorder.intercept_output('output_missing')
            def output_missing(self):
                return 5

        instance = Operation('output')
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        with self.assertRaises(RecordingKeyError):
            self.tape_recorder.play(recording_id,
                                    playback_function=lambda recording: Operation('output_missing').execute())

    def test_record_and_playback_basic_operation_metadata_extractor_raise_exception(self):
        def operation_metadata_extractor(*args, **kwargs):
            raise Exception('Meta exception')

        class Operation(object):

            @self.tape_recorder.operation(metadata_extractor=operation_metadata_extractor)
            def execute(self):
                return 5

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_save_recording_raise_exception(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 5

        with patch.object(InMemoryTapeCassette, '_save_recording', side_effect=Exception()):
            instance = Operation()
            result = instance.execute()
            self.assertEqual(5, result)

    def test_record_and_playback_basic_operation_no_parameters_raise_error(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                raise ValueError("Error")

        instance = Operation()
        with self.assertRaises(ValueError) as e:
            instance.execute()
        self.assertEqual("Error", str(e.exception))

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        operation_output = next(po for po in playback_result.playback_outputs
                                if TapeRecorder.OPERATION_OUTPUT_ALIAS in po.key)
        self.assertEqual(ValueError, type(operation_output.value['args'][0]))
        self.assertEqual("Error", str(operation_output.value['args'][0]))
        self.assertEqual(len(playback_result.recorded_outputs), len(playback_result.playback_outputs))
        self.assertGreater(playback_result.playback_duration, 0)
        self.assertGreater(playback_result.recorded_duration, 0)
        self.assertDictContainsSubset({TapeRecorder.EXCEPTION_IN_OPERATION: True},
                                      playback_result.original_recording.get_metadata())

    def test_record_and_playback_basic_operation_no_parameters_raise_unserializable_error(self):

        class UnserializableException(Exception):
            def __getstate__(self):
                raise Exception("Unserializable")

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                raise UnserializableException("Error")

        instance = Operation()
        with self.assertRaises(UnserializableException) as e:
            instance.execute()
        self.assertEqual("Error", str(e.exception))

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        operation_output = next(po for po in playback_result.playback_outputs
                                if TapeRecorder.OPERATION_OUTPUT_ALIAS in po.key)
        self.assertEqual(UnserializableException, operation_output.value['args'][0]['error_type'])
        self.assertIn('Error', operation_output.value['args'][0]['error_repr'])
        self.assertEqual(len(playback_result.recorded_outputs), len(playback_result.playback_outputs))
        self.assertGreater(playback_result.playback_duration, 0)
        self.assertGreater(playback_result.recorded_duration, 0)
        self.assertDictContainsSubset({TapeRecorder.EXCEPTION_IN_OPERATION: True},
                                      playback_result.original_recording.get_metadata())

    def test_record_and_playback_basic_operation_data_interception_no_arguments_raise_exception(self):
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                try:
                    self.get_value()
                except Exception as ex:
                    return str(ex)

            @self.tape_recorder.intercept_input('input')
            def get_value(self):
                raise Exception(self.seed)

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual('5', result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_output_interception_no_arguments_raise_exception(self):
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                try:
                    self.output()
                except Exception as ex:
                    return str(ex)

            @self.tape_recorder.intercept_output('output_function')
            def output(self):
                raise Exception(self.seed)

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual("5", result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_sampling_rate_class_level_decorator(self):

        @self.tape_recorder.recording_params(RecordingParameters(sampling_rate=0.1))
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, 'save_recording', wraps=self.tape_cassette.create_new_recording) \
                as intercepted:
            calls = 100
            for __ in range(calls):
                result = instance.execute()
                self.assertEqual(5, result)

            call_ratio = float(intercepted.call_count)/calls
            print('Call ratio {}'.format(call_ratio))
            self.assertAlmostEqual(0.1, call_ratio, places=1)

    def test_operation_with_input_dict_as_key(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                # We are shuffling here hoping to get different internal order for the dict between calls but still
                # see we are consistent on input interception is these are equivalent dicts
                items = list(range(100))
                shuffle(items)
                argument = {'key{}'.format(i): i for i in items}
                return self.get_value(argument)

            @self.tape_recorder.intercept_input('input')
            def get_value(self, json_dict):
                return json_dict['key5']

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_operation_with_alias_param_resolver(self):
        class ValueCreator(object):
            def __init__(self, name, value):
                self.name = name
                self.value = value

            @self.tape_recorder.intercept_input('input.{name}', alias_params_resolver=lambda s: {'name': s.name})
            def get_value(self):
                return self.value

        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                # We check that we are capturing different value interceptions even though we pass same arguments to
                # the intercepted method by using a param resolver that will provide unique interception key for each
                # invocation
                return self.get_value('a', self.seed) + self.get_value('b', self.seed * 2)

            @staticmethod
            def get_value(name, value):
                return ValueCreator(name, value).get_value()

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual(15, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_operation_with_input_interception_data_handler(self):
        test_self = self

        class XorDataHandler(InputInterceptionDataHandler):

            def prepare_input_for_recording(self, interception_key, result, args, kwargs):
                test_self.assertIn('value_input', interception_key)
                test_self.assertEqual(5, result)
                test_self.assertEqual(('x', ), args[1:])
                test_self.assertEqual({'b': 'y'}, kwargs)
                return 5 ^ 3141

            def restore_input_from_recording(self, recorded_data, args, kwargs):
                # Applying same xor twice return original result
                return recorded_data ^ 3141

        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value('x', b='y')

            @self.tape_recorder.intercept_input('value_input', data_handler=XorDataHandler())
            def get_value(self, a, b=None):
                return self.seed

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        # Check the recording it self contains the modified value
        recording = self.tape_cassette.get_recording(recording_id)
        key = next(k for k in recording.get_all_keys() if 'value_input' in k)
        self.assertEqual(5 ^ 3141, recording.get_data(key)['value'])

        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_input_interception_data_handler_failure(self):

        class ErrorDataHandler(InputInterceptionDataHandler):

            def prepare_input_for_recording(self, interception_key, result, args, kwargs):
                raise Exception('error')

            def restore_input_from_recording(self, recorded_data, args, kwargs):
                pass

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value() + self.get_value2()

            @self.tape_recorder.intercept_input('value_input', data_handler=ErrorDataHandler())
            def get_value(self):
                return 5

            @self.tape_recorder.intercept_input('value_input2')
            def get_value2(self):
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, '_save_recording', wraps=self.tape_cassette._save_recording) \
                as intercepted:
            result = instance.execute()
            intercepted.assert_not_called()

        self.assertEqual(10, result)

    def test_record_and_playback_basic_operation_data_interception_with_all_arguments_ignored_as_key(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                arg1 = random()
                arg2 = random()
                val1 = self.get_value(arg1, b=arg2)
                return val1

            @self.tape_recorder.intercept_input('input', capture_args=[])
            def get_value(self, a, b=2):
                return 5

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_basic_operation_data_interception_with_false_capture_args(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                arg1 = random()
                arg2 = random()
                val1 = self.get_value(arg1, b=arg2)
                return val1

            @self.tape_recorder.intercept_input('input', capture_args=False)
            def get_value(self, a, b=2):
                return 5

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_sampling_rate_with_enforced_recording(self):
        local_tape_recorder = self.tape_recorder
        test_self = self

        @self.tape_recorder.recording_params(RecordingParameters(sampling_rate=0.2))
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                local_tape_recorder.force_sample_recording()
                test_self.assertTrue(local_tape_recorder.is_recording_sample_forced)
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, '_save_recording', wraps=self.tape_cassette._save_recording) \
                as intercepted:
            calls = 10
            for __ in range(calls):
                result = instance.execute()
                self.assertEqual(5, result)

            call_ratio = float(intercepted.call_count)/calls
            print('Call ratio {}'.format(call_ratio))
            self.assertEqual(1, call_ratio)

    def test_sampling_rate_with_ignore_enforced_recording(self):
        local_tape_recorder = self.tape_recorder
        test_self = self

        @self.tape_recorder.recording_params(RecordingParameters(sampling_rate=0.1, ignore_enforced_sampling=True))
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                local_tape_recorder.force_sample_recording()
                test_self.assertFalse(local_tape_recorder.is_recording_sample_forced)
                return 5

        instance = Operation()
        with patch.object(InMemoryTapeCassette, '_save_recording', wraps=self.tape_cassette._save_recording) \
                as intercepted_save,\
                patch.object(InMemoryTapeCassette, 'abort_recording', wraps=self.tape_cassette.abort_recording) \
                as intercepted_abort:
            calls = 100
            for __ in range(calls):
                result = instance.execute()
                self.assertEqual(5, result)

            expected_aborted = calls - intercepted_save.call_count
            call_ratio = float(intercepted_save.call_count) / calls
            print('Call ratio {}'.format(call_ratio))
            self.assertAlmostEqual(0.1, call_ratio, places=1)
            self.assertEqual(expected_aborted, intercepted_abort.call_count)

    def test_record_and_playback_basic_operation_data_interception_with_specific_arguments_ignored_as_key(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                # This is random to see that capture args is only capturing the requested arg index
                arg1 = random()
                arg2 = 'b'
                arg3 = 'c'
                # This is random to see that capture args is only capturing the requested arg kwargs
                arg4 = random()
                arg5 = 'e'
                val1 = self.get_value(arg1, arg2, c=arg3, d=arg4, e=arg5)
                return val1

            @self.tape_recorder.intercept_input('input', capture_args=[CapturedArg(2, 'b'), CapturedArg(3, 'c'),
                                                                       CapturedArg(None, 'e'), CapturedArg(None, 'f')])
            def get_value(self, a, b, c, d=None, e=None, f=None):
                return 5

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_operation_with_output_interception_data_handler(self):
        test_self = self

        class XorDataHandler(OutputInterceptionDataHandler):

            def prepare_output_for_recording(self, interception_key, args, kwargs):
                test_self.assertIn('output_function', interception_key)
                test_self.assertEqual((5, ), args)
                test_self.assertEqual({'arg': 'a'}, kwargs)
                return args[0] ^ 3141

            def restore_output_from_recording(self, recorded_data):
                # Applying same xor twice return original result
                return recorded_data ^ 3141

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return self.output(5, arg='a')

            @self.tape_recorder.intercept_output('output_function', data_handler=XorDataHandler())
            def output(self, value, arg=None):
                return value

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        # Check the recording it self contains the modified value
        recording = self.tape_cassette.get_recording(recording_id)
        key = next(k for k in recording.get_all_keys() if 'output_function' in k)
        self.assertEqual(5 ^ 3141, recording.get_data(key))
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)

        self.assertEqual(result, XorDataHandler().restore_output_from_recording(
            playback_result.playback_outputs[0].value))

    def test_output_interception_data_handler_failure(self):

        class ErrorDataHandler(OutputInterceptionDataHandler):

            def prepare_output_for_recording(self, interception_key, args, kwargs):
                raise Exception('error')

            def restore_output_from_recording(self, recorded_data):
                pass

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return self.output(5) + self.output2(5)

            @self.tape_recorder.intercept_output('output_function', data_handler=ErrorDataHandler())
            def output(self, value):
                return value

            @self.tape_recorder.intercept_output('output_function2')
            def output2(self, value):
                return value

        instance = Operation()
        with patch.object(InMemoryTapeCassette, '_save_recording', wraps=self.tape_cassette._save_recording) \
                as intercepted:
            result = instance.execute()
            intercepted.assert_not_called()

        self.assertEqual(10, result)

    def test_record_and_playback_basic_operation_data_interception_inside_interception(self):
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value()

            @self.tape_recorder.intercept_input('input')
            def get_value(self):
                return self.get_inner_value()

            @self.tape_recorder.intercept_input('inner_input')
            def get_inner_value(self):
                return self.seed

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)

        # Check the recording it self does not contain the inner interception
        recording = self.tape_cassette.get_recording(recording_id)
        self.assertIsNone(next((k for k in recording.get_all_keys() if 'inner_input' in k), None))

    def test_record_and_playback_basic_operation_new_output_added_post_recording(self):
        class OperationOld(object):

            @self.tape_recorder.operation()
            def execute(self):
                return self.output(5)

            @self.tape_recorder.intercept_output('output_function')
            def output(self, value):
                return value

        class OperationNew(object):

            @self.tape_recorder.operation()
            def execute(self):
                value = self.output(5)
                self.output_new(value)
                return value

            @self.tape_recorder.intercept_output('output_function')
            def output(self, value):
                return value

            @self.tape_recorder.intercept_output('output_new_function', fail_on_no_recorded_result=False)
            def output_new(self, value):
                return value

        instance = OperationOld()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: OperationNew().execute())

        self.assertEqual({'args': [5], 'kwargs': {}}, playback_result.playback_outputs[0].value)
        self.assertEqual({'args': [5], 'kwargs': {}}, playback_result.playback_outputs[1].value)
        self.assertNotEqual(playback_result.playback_outputs[0].key, playback_result.playback_outputs[1].key)
        self.assertIn('output_function', playback_result.playback_outputs[0].key)
        self.assertIn('output_new_function', playback_result.playback_outputs[1].key)

    def test_current_recording_id(self):
        tape_recorder = self.tape_recorder

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return tape_recorder.current_recording_id

        instance = Operation()
        result = instance.execute()
        recording_id = self.tape_cassette.get_last_recording_id()
        self.assertEqual(recording_id, result)

        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        operation_output = next(po for po in playback_result.playback_outputs
                                if TapeRecorder.OPERATION_OUTPUT_ALIAS in po.key)
        self.assertEqual(recording_id, operation_output.value['args'][0])

        self.tape_recorder.disable_recording()
        instance = Operation()
        self.assertIsNone(instance.execute())

    def test_record_and_playback_record_and_play_data(self):
        tape_recorder = self.tape_recorder

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                data = tape_recorder.play_data('data')
                tape_recorder.record_data('data', data)
                if tape_recorder.in_playback_mode:
                    return data

                data = 5
                tape_recorder.record_data('data', data)
                return data

        instance = Operation()
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        with patch.object(TapeRecorder, 'play_data', wraps=tape_recorder.play_data) as wrapped:
            playback_result = self.tape_recorder.play(recording_id,
                                                      playback_function=lambda recording: Operation().execute())
        self._assert_playback_vs_recording(playback_result, result)
        wrapped.assert_called()

    @patch('playback.tape_recorder.pickle_copy', side_effect=pickle_copy)
    def test_record_and_playback_basic_operation_data_interception_copy_data(self, wrapped_encode):
        @self.tape_recorder.recording_params(RecordingParameters(copy_data_on_intercepion=True))
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value()

            @self.tape_recorder.intercept_input('input')
            def get_value(self):
                return self.seed

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        wrapped_encode.assert_called_with(5)
        self._assert_playback_vs_recording(playback_result, result)

    @patch('playback.tape_recorder.pickle_copy')
    def test_record_and_playback_basic_operation_data_interception_copy_data_exception(self, wrapped_decode):

        @self.tape_recorder.recording_params(RecordingParameters(copy_data_on_intercepion=True))
        class Operation(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value()

            @self.tape_recorder.intercept_input('input')
            def get_value(self):
                return self.seed

        def cannot(input):
            raise Exception('cannot')

        wrapped_decode.side_effect = cannot

        instance = Operation(5)
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())
        wrapped_decode.assert_called()
        self._assert_playback_vs_recording(playback_result, result)

    def test_intercept_input_activate_original_method_on_missing(self):
        class OperationOld(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value()

            def get_value(self):
                return self.seed

        class OperationNew(object):

            def __init__(self, seed=0):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return self.get_value()

            @self.tape_recorder.intercept_input('input', run_intercepted_when_missing=True)
            def get_value(self):
                return self.seed

        instance = OperationOld(5)
        result = instance.execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: OperationNew(5).execute())
        self._assert_playback_vs_recording(playback_result, result)
