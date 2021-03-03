# We create the tape recorder singleton that will be used by the endpoints
import os

from playback.tape_cassettes.asynchronous.async_record_only_tape_cassette import AsyncRecordOnlyTapeCassette
from playback.tape_cassettes.file_based.file_based_tape_cassette import FileBasedTapeCassette
from playback.tape_recorder import TapeRecorder

tape_recorder = TapeRecorder(None)
tape_recorder.disable_recording()

# For demonstration purpose, persist file in underline recordings dir
recordings_path = os.path.dirname(os.path.realpath(__file__)) + '/recordings'


def init_recording_mode():
    """
    Initialize and start the tape cassette and tape recorder for recording mode.
    in order for the recording not to be blocking and part of the operation latency, we wrap it with the asynchronous
    tape cassette which will flush the recording to a file in a separate thread, reducing the impact on the thread
    that executes the operation
    """
    print("Starting recording mode - recordings will be saved to {}".format(recordings_path))
    tape_cassette = AsyncRecordOnlyTapeCassette(FileBasedTapeCassette(recordings_path))
    tape_cassette.start()
    tape_recorder.tape_cassette = tape_cassette
    # This will activate the tape recorder in recording mode
    tape_recorder.enable_recording()


def init_playback_mode():
    print("Starting playback mode - recordings will be read from {}".format(recordings_path))
    tape_cassette = FileBasedTapeCassette(recordings_path)
    tape_recorder.tape_cassette = tape_cassette
