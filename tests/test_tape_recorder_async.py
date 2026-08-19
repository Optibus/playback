import asyncio
import functools
import unittest

from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette
from playback.tape_recorder import TapeRecorder


def _hide_coroutine_function(func):
    """
    Mimics a decorator that wraps a coroutine function without being declared with 'async def' itself, which hides
    the coroutine function from an interception declared above it
    :param func: Coroutine function to wrap
    :type func: function
    :return: A plain function returning the coroutine of the wrapped function
    :rtype: function
    """

    @functools.wraps(func)
    def decorated(*args, **kwargs):
        return func(*args, **kwargs)

    return decorated


class TestTapeRecorderAsync(unittest.TestCase):

    def setUp(self):
        self.tape_cassette = InMemoryTapeCassette()
        self.tape_recorder = TapeRecorder(self.tape_cassette, random_seed=110613)
        self.tape_recorder.enable_recording()

    def _assert_playback_vs_recording(self, playback_result, result):
        """
        :param playback_result: Playback result
        :type playback_result: playback.tape_recorder.Playback
        :param result: Operation result
        :type result: Any
        """
        self.assertCountEqual(playback_result.recorded_outputs, playback_result.playback_outputs)

        operation_output = next(po for po in playback_result.playback_outputs
                                if TapeRecorder.OPERATION_OUTPUT_ALIAS in po.key)
        self.assertEqual(result, operation_output.value['args'][0])

    def _recorded_input_keys(self, recording_id):
        """
        :param recording_id: Id of the recording to look in
        :type recording_id: str
        :return: All input interception keys held by the recording
        :rtype: list of str
        """
        recording = self.tape_cassette.get_recording(recording_id)
        return [key for key in recording.get_all_keys() if key.startswith('input:')]

    def test_async_input_interception_records_the_awaited_value(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('input')
            async def get_value(self):
                await asyncio.sleep(0)
                return 5

        result = Operation().execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        recording = self.tape_cassette.get_recording(recording_id)
        input_keys = self._recorded_input_keys(recording_id)
        self.assertEqual(1, len(input_keys))
        self.assertEqual({'value': 5}, recording.get_data(input_keys[0]))

    def test_record_and_playback_operation_with_async_input(self):
        invocations = []

        class Operation(object):

            def __init__(self, seed):
                self.seed = seed

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('input')
            async def get_value(self):
                invocations.append(self.seed)
                await asyncio.sleep(0)
                return self.seed

        result = Operation(5).execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        # A different seed makes the played back operation return 7 if the recorded input is not used
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation(7).execute())

        self._assert_playback_vs_recording(playback_result, result)
        self.assertEqual([5], invocations)

    def test_record_and_playback_operation_with_async_input_raising_error(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                try:
                    return asyncio.run(self.get_value())
                except ValueError as ex:
                    return 'caught {}'.format(ex)

            @self.tape_recorder.intercept_input('input')
            async def get_value(self):
                await asyncio.sleep(0)
                raise ValueError('input failed')

        result = Operation().execute()
        self.assertEqual('caught input failed', result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_operation_with_async_output(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.send_values())

            async def send_values(self):
                return await self.send_value(4) + await self.send_value(3)

            @self.tape_recorder.intercept_output('output')
            async def send_value(self, value):
                await asyncio.sleep(0)
                return value

        result = Operation().execute()
        self.assertEqual(7, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)
        self.assertEqual([{'args': [4], 'kwargs': {}}, {'args': [3], 'kwargs': {}}],
                         [output.value for output in playback_result.playback_outputs
                          if 'output' in output.key and TapeRecorder.OPERATION_OUTPUT_ALIAS not in output.key])

    def test_record_and_playback_operation_with_async_static_input(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value(2, b=3))

            @staticmethod
            @self.tape_recorder.static_intercept_input('input')
            async def get_value(a, b=2):
                await asyncio.sleep(0)
                return a + b

        result = Operation().execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)

    def test_record_and_playback_operation_with_async_static_output(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.send_value(4, arg='a'))

            @staticmethod
            @self.tape_recorder.static_intercept_output('output_function')
            async def send_value(value, arg=None):
                await asyncio.sleep(0)
                return value

        result = Operation().execute()
        self.assertEqual(4, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)
        self.assertIn('output_function', playback_result.playback_outputs[0].key)

    def test_record_and_playback_concurrently_intercepted_async_inputs(self):
        invocations = []

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_values())

            async def get_values(self):
                return list(await asyncio.gather(self.get_value('a'), self.get_value('b')))

            @self.tape_recorder.intercept_input('input')
            async def get_value(self, key):
                invocations.append(key)
                # Suspending inside the interception lets the sibling interception start while this one is open
                await asyncio.sleep(0.01)
                return 'value-{}'.format(key)

        result = Operation().execute()
        self.assertEqual(['value-a', 'value-b'], result)

        recording_id = self.tape_cassette.get_last_recording_id()
        self.assertEqual(2, len(self._recorded_input_keys(recording_id)))

        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)
        self.assertEqual(['a', 'b'], invocations)

    def test_async_interception_inside_async_interception_is_not_recorded(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('outer input')
            async def get_value(self):
                return await self.get_inner_value()

            @self.tape_recorder.intercept_input('inner input')
            async def get_inner_value(self):
                await asyncio.sleep(0)
                return 5

        result = Operation().execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        input_keys = self._recorded_input_keys(recording_id)
        self.assertEqual(1, len(input_keys))
        self.assertIn('outer input', input_keys[0])

    def test_sync_interception_inside_async_interception_is_not_recorded(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('outer input')
            async def get_value(self):
                await asyncio.sleep(0)
                return self.get_inner_value()

            @self.tape_recorder.intercept_input('inner input')
            def get_inner_value(self):
                return 5

        result = Operation().execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        input_keys = self._recorded_input_keys(recording_id)
        self.assertEqual(1, len(input_keys))
        self.assertIn('outer input', input_keys[0])

    def test_async_input_interception_run_intercepted_when_missing(self):
        class OperationOld(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            async def get_value(self):
                await asyncio.sleep(0)
                return 5

        class OperationNew(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('input', run_intercepted_when_missing=True)
            async def get_value(self):
                await asyncio.sleep(0)
                return 5

        result = OperationOld().execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: OperationNew().execute())

        self._assert_playback_vs_recording(playback_result, result)

    def test_async_input_interception_value_when_missing(self):
        class OperationOld(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            async def get_value(self):
                await asyncio.sleep(0)
                return 5

        class OperationNew(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('input', value_when_missing=5)
            async def get_value(self):
                raise AssertionError('should not be invoked when a value when missing is given')

        result = OperationOld().execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: OperationNew().execute())

        self._assert_playback_vs_recording(playback_result, result)

    def test_recording_is_discarded_when_an_input_interception_returns_a_coroutine(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('input')
            @_hide_coroutine_function
            async def get_value(self):
                await asyncio.sleep(0)
                return 5

        result = Operation().execute()
        self.assertEqual(5, result)
        self.assertIsNone(self.tape_cassette.get_last_recording_id())

    def test_async_interception_is_not_recorded_when_recording_is_disabled(self):
        self.tape_recorder.disable_recording()

        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.get_value())

            @self.tape_recorder.intercept_input('input')
            async def get_value(self):
                await asyncio.sleep(0)
                return 5

        result = Operation().execute()
        self.assertEqual(5, result)
        self.assertIsNone(self.tape_cassette.get_last_recording_id())

    def test_record_and_playback_concurrently_intercepted_async_outputs(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.send_values())

            async def send_values(self):
                return list(await asyncio.gather(self.send_value('a'), self.send_value('b')))

            @self.tape_recorder.intercept_output('output')
            async def send_value(self, key):
                # Suspending inside the interception lets the sibling interception start while this one is open
                await asyncio.sleep(0.01)
                return 'value-{}'.format(key)

        result = Operation().execute()
        self.assertEqual(['value-a', 'value-b'], result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)
        # An output is keyed by its invocation number, which is taken when the interception opens and not when the
        # coroutine resolves, so concurrent invocations are numbered in the order they were started
        self.assertEqual([{'args': ['a'], 'kwargs': {}}, {'args': ['b'], 'kwargs': {}}],
                         [output.value for output in playback_result.playback_outputs
                          if 'output' in output.key and TapeRecorder.OPERATION_OUTPUT_ALIAS not in output.key])

    def test_record_and_playback_operation_with_async_output_raising_error(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                try:
                    return asyncio.run(self.send_value())
                except ValueError as ex:
                    return 'caught {}'.format(ex)

            @self.tape_recorder.intercept_output('output')
            async def send_value(self):
                await asyncio.sleep(0)
                raise ValueError('output failed')

        result = Operation().execute()
        self.assertEqual('caught output failed', result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: Operation().execute())

        self._assert_playback_vs_recording(playback_result, result)

    def test_async_output_interception_default_result_when_not_recorded(self):
        class OperationOld(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.send_value(5))

            @self.tape_recorder.intercept_output('output_function')
            async def send_value(self, value):
                await asyncio.sleep(0)
                return value

        class OperationNew(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.send_values())

            async def send_values(self):
                value = await self.send_value(5)
                val1, val2 = await self.send_new_value(value)
                return val1 + val2

            @self.tape_recorder.intercept_output('output_function')
            async def send_value(self, value):
                await asyncio.sleep(0)
                return value

            @self.tape_recorder.intercept_output('output_new_function', fail_on_no_recorded_result=False,
                                                 default_result_when_not_recorded=(2, 4))
            async def send_new_value(self, value):
                await asyncio.sleep(0)
                return value, value * 2

        result = OperationOld().execute()
        self.assertEqual(5, result)

        recording_id = self.tape_cassette.get_last_recording_id()
        playback_result = self.tape_recorder.play(recording_id,
                                                  playback_function=lambda recording: OperationNew().execute())

        self.assertEqual({'args': [5], 'kwargs': {}}, playback_result.playback_outputs[0].value)
        self.assertEqual({'args': [5], 'kwargs': {}}, playback_result.playback_outputs[1].value)
        self.assertIn('output_function', playback_result.playback_outputs[0].key)
        self.assertIn('output_new_function', playback_result.playback_outputs[1].key)
        operation_output = next(po for po in playback_result.playback_outputs
                                if TapeRecorder.OPERATION_OUTPUT_ALIAS in po.key)
        self.assertEqual(6, operation_output.value['args'][0])

    def test_recording_is_discarded_when_an_output_interception_returns_a_coroutine(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.send_value())

            @self.tape_recorder.intercept_output('output')
            @_hide_coroutine_function
            async def send_value(self):
                await asyncio.sleep(0)
                return 5

        result = Operation().execute()
        self.assertEqual(5, result)
        self.assertIsNone(self.tape_cassette.get_last_recording_id())

    def test_recording_is_discarded_when_an_interception_returns_an_async_generator(self):
        class Operation(object):

            @self.tape_recorder.operation()
            def execute(self):
                return asyncio.run(self.collect_values())

            async def collect_values(self):
                return [value async for value in self.stream_values()]

            @self.tape_recorder.intercept_input('input')
            async def stream_values(self):
                yield 5
                yield 7

        result = Operation().execute()
        self.assertEqual([5, 7], result)
        self.assertIsNone(self.tape_cassette.get_last_recording_id())

    def test_recording_is_discarded_when_an_operation_returns_a_coroutine(self):
        class Operation(object):

            @self.tape_recorder.operation()
            async def execute(self):
                return await self.get_value()

            @self.tape_recorder.intercept_input('input')
            async def get_value(self):
                await asyncio.sleep(0)
                return 5

        result = asyncio.run(Operation().execute())
        self.assertEqual(5, result)
        self.assertIsNone(self.tape_cassette.get_last_recording_id())
