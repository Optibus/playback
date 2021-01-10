import unittest

from playback.tape_cassettes.asynchronous.async_record_only_tape_cassette import AsyncRecordOnlyTapeCassette
from tests.mocks.delayed_in_memory_tape_cassette import DelayedInMemoryTapeCassette
from playback.utils.timing_utils import Timed


class TestAsyncTapeCassette(unittest.TestCase):

    def test_async_set_data_behavior(self):
        in_memory_cassette = DelayedInMemoryTapeCassette(delay=0.1)
        tape_cassette = AsyncRecordOnlyTapeCassette(in_memory_cassette, timeout_on_close=5)
        tape_cassette.start()

        recording = tape_cassette.create_new_recording('category')
        self.assertEqual(recording.id, recording.wrapped_recording.id)
        with Timed() as timed:
            recording.add_metadata({'c': 3, 'd': 4})
            recording.set_data('a', 2)
            recording.set_data('b', 1)
            tape_cassette.save_recording(recording)

        self.assertLess(timed.duration, 0.1)
        tape_cassette.close()
        _id = in_memory_cassette.get_last_recording_id()
        recording = in_memory_cassette.get_recording(_id)
        self.assertEqual(2, recording.get_data('a'))
        self.assertEqual(1, recording.get_data('b'))
        self.assertEqual({'c': 3, 'd': 4}, recording.get_metadata())
