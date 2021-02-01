import random
from datetime import datetime, timedelta
from uuid import uuid1

from playback.studio.equalizer import Equalizer, ComparatorResult, EqualityStatus
from playback.studio.recordings_lookup import RecordingLookupProperties, find_matching_recording_ids
from playback.tape_cassettes.in_memory.in_memory_tape_cassette import InMemoryTapeCassette
from playback.tape_recorder import TapeRecorder

tape_cassette = InMemoryTapeCassette()
tape_recorder = TapeRecorder(tape_cassette)


class ServiceOperation(object):

    @tape_recorder.operation()
    def execute(self):
        """
        Executes the operation and return the key of where the result is stored
        """
        data = self.get_request_data()
        result = self.do_something_with_input(data)
        storage_key = self.store_result(result)
        return storage_key

    @tape_recorder.intercept_input(alias='service_operation.get_request_data')
    def get_request_data(self):
        """
        Reads the required input for the operation
        """
        # Fake input that will be captured in the recording
        return random.randint(0, 10)

    @tape_recorder.intercept_output(alias='service_operation.store_result')
    def store_result(self, result):
        """
        Stores the operation result and return the key that can be used to fetch the result
        """
        result_key = self.put_result_in_mongo(result)
        return result_key

    def do_something_with_input(self, input):
        """
        Apply some logic on input
        """
        return input * 2

    def put_result_in_mongo(self, result):
        """
        Stores the result in mongo
        """
        # Fake output, we don't really need to store anything in the example, return a fake document id
        return uuid1().hex


# Run the operation 5 times and record it
tape_recorder.enable_recording()

for __ in range(10):
    ServiceOperation().execute()


def playback_function(recording):
    """
    Given a recording, replay the recorded operation
    """
    operation_class = recording.get_metadata()[TapeRecorder.OPERATION_CLASS]
    return operation_class().execute()


# Replay last recorded operation
tape_recorder.play(tape_cassette.get_last_recording_id(), playback_function)


# Creates an iterator over relevant recordings which are ready to be played
lookup_properties = RecordingLookupProperties(start_date=datetime.utcnow() - timedelta(days=7),
                                              limit=5)
recording_ids = find_matching_recording_ids(tape_recorder, ServiceOperation.__name__, lookup_properties)


def result_extractor(outputs):
    """
    Given recording or playback outputs, find the relevant output which is the result that needs to be compared
    """
    # Find the relevant captured output
    output = next(o for o in outputs if 'service_operation.store_result' in o.key)
    # Return the captured first arg as the result that needs to be compared
    return output.value['args'][0]


def comparator(recorded_result, replay_result):
    """
    Compare the operation captured output result
    """
    if recorded_result == replay_result:
        return ComparatorResult(EqualityStatus.Equal, "Value is {}".format(recorded_result))
    return ComparatorResult(EqualityStatus.Different,
                            "{recorded_result} != {replay_result}".format(
                                recorded_result=recorded_result, replay_result=replay_result))


def player(recording_id):
    return tape_recorder.play(recording_id, playback_function)


# Run comparison and output comparison result using the Equalizer
equalizer = Equalizer(recording_ids, player, result_extractor, comparator)

for comparison_result in equalizer.run_comparison():
    print('Comparison result {recording_id} is: {result}'.format(
        recording_id=comparison_result.playback.original_recording.id,
        result=comparison_result.comparator_status))
