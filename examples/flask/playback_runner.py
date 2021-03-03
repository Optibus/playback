from examples.flask.playback_context import tape_recorder, init_playback_mode
from playback.studio.equalizer import ComparatorResult, EqualityStatus
from playback.studio.equalizer_tuning import EqualizerTuner, EqualizerTuning
from playback.studio.studio import PlaybackStudio
from playback.tape_recorder import TapeRecorder


class ContentBasedEqualizerTune(EqualizerTuner):

    @staticmethod
    def playback_function(recording):
        """
        Rerun the operation given the recording
        """
        # The class it self is saved as metadata, we instantiate it and trigger the post method
        operation_class = recording.get_metadata()[TapeRecorder.OPERATION_CLASS]()
        operation_class.post()

    @staticmethod
    def result_extractor(outputs):
        """
        For this service we consider the return result of the operation as its output
        """
        return next(o.value['args'][0] for o in outputs if TapeRecorder.OPERATION_OUTPUT_ALIAS in o.key)

    @staticmethod
    def comparator(recorded, played_back):
        """
        Compare recorded value vs the playback back value, doing a basic equality check
        """
        equal = recorded == played_back
        return ComparatorResult(EqualityStatus.Equal if equal else EqualityStatus.Different,
                                message="recorded: {}, played_back: {}".format(recorded, played_back))

    def create_category_tuning(self, category):
        """
        Create a tuning with the needed plugins to rerun the operation and compare the results
        """
        return EqualizerTuning(self.playback_function, self.result_extractor, self.comparator)


init_playback_mode()


studio = PlaybackStudio(categories=['ContentLengthEndpoint', 'ContentFirstCharsEndpoint'],
                        equalizer_tuner=ContentBasedEqualizerTune(),
                        tape_recorder=tape_recorder)

# Run on all categories recording, compare them and output the result
for category, category_comparisons in studio.play().items():
    print('Category {}'.format(category))
    for comparison_result in category_comparisons:
        print('{recording_id}: {result}'.format(
            recording_id=comparison_result.recording_id,
            result=comparison_result.comparator_status))
    print('')
