import unittest

from playback.tape_cassettes.asynchronous.async_record_only_tape_cassette import AsyncRecordOnlyTapeCassette
from tests.mocks.delayed_in_memory_tape_cassette import DelayedInMemoryTapeCassette
from playback.utils.timing_utils import Timed


class TestAsyncTapeCassette(unittest.TestCase):

    def test_async_set_data_behavior(self):
        self._test_async_data_set_behavior(add_error_op=False)

    def test_async_set_data_behavior_with_error_op(self):
        self._test_async_data_set_behavior(add_error_op=True)

    def _test_async_data_set_behavior(self, add_error_op):
        in_memory_cassette = DelayedInMemoryTapeCassette(delay=0.1)
        tape_cassette = AsyncRecordOnlyTapeCassette(in_memory_cassette, timeout_on_close=5)
        tape_cassette.start()
        recording = tape_cassette.create_new_recording('category')
        self.assertEqual(recording.id, recording.wrapped_recording.id)

        def error_operation():
            raise Exception('mock')

        with Timed() as timed:
            recording.add_metadata({'c': 3, 'd': 4})
            recording.set_data('a', 2)
            recording.set_data('b', 1)

            if add_error_op:
                tape_cassette._add_async_operation(error_operation)

            tape_cassette.save_recording(recording)
        self.assertLess(timed.duration, 0.1)
        tape_cassette.close()
        _id = in_memory_cassette.get_last_recording_id()
        recording = in_memory_cassette.get_recording(_id)
        self.assertEqual(2, recording.get_data('a'))
        self.assertEqual(1, recording.get_data('b'))
        self.assertEqual({'c': 3, 'd': 4}, recording.get_metadata())

    def test_read_operation_raising_errors(self):
        in_memory_cassette = DelayedInMemoryTapeCassette(delay=0.1)
        tape_cassette = AsyncRecordOnlyTapeCassette(in_memory_cassette, timeout_on_close=5)
        tape_cassette.start()
        try:
            with self.assertRaises(TypeError):
                tape_cassette.get_recording('a')
            with self.assertRaises(TypeError):
                tape_cassette.iter_recording_ids('a')
            with self.assertRaises(TypeError):
                tape_cassette.extract_recording_category('a')

            recording = tape_cassette.create_new_recording('category')
            with self.assertRaises(TypeError):
                recording.get_data('a')
            with self.assertRaises(TypeError):
                recording.get_all_keys()
            with self.assertRaises(TypeError):
                recording.get_metadata()
        finally:
            tape_cassette.close()

    def test_close_without_open_no_error(self):
        in_memory_cassette = DelayedInMemoryTapeCassette(delay=0.1)
        tape_cassette = AsyncRecordOnlyTapeCassette(in_memory_cassette, timeout_on_close=5)
        tape_cassette.close()
