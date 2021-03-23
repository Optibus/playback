import multiprocessing as mp
import os
import signal
from collections import Counter, namedtuple
from time import time

from enum import Enum
import logging

_logger = logging.getLogger(__name__)


"""
Equal               - The recorded and playback compared outputs are considered equal
Fixed               - The playback output is considered as a fix to the matched errornous recorded output
Different           - The recorded and playback compared outputs are considered different
Failed              - The playback output is considered as a failure compared to the recorded output
EqualizerFailure    - The framework have failed running the comparison
"""
EqualityStatus = Enum('EqualityStatus', 'Equal Fixed Different Failed EqualizerFailure')


class ComparatorResult(object):
    def __init__(self, equality_status, message=None, diff=None):
        """
        :param equality_status: Equality status between expected and actual
        :type equality_status: EqualityStatus
        :param message: Optional comparison message
        :type message: basestring
        """
        self.equality_status = equality_status
        self.message = message
        self.diff = diff

    def __str__(self):
        if not self.message:
            return u'{}'.format(self.equality_status.name)

        return u'{} - {}'.format(self.equality_status.name, self.message)

    @staticmethod
    def failure_result(exception):
        """
        :param exception: Exception to wrap with failure result
        :type exception: builtins.Exception
        :return: Failure comparator result representing the given exception
        :rtype: ComparatorResult
        """
        return ComparatorResult(EqualityStatus.EqualizerFailure, str(exception))


class Comparison(object):
    def __init__(self, comparator_result, expected, actual, expected_is_exception, actual_is_exception, playback,
                 recording_id):
        """
        :param comparator_result: Result of comparison between expected and actual
        :type comparator_result: ComparatorResult
        :param expected: Expected result (recording)
        :type expected: Any
        :param actual: Actual result (playback)
        :type actual: Any
        :param expected_is_exception: Is expected result an exception (recording)
        :type expected_is_exception: bool
        :param actual_is_exception: Is actual result an exception (recording)
        :type actual_is_exception: bool
        :param playback: Play operation result
        :type playback: playback.tape_recorder.Playback
        :param recording_id: Id of compared recording
        :type recording_id: str
        """
        self.comparator_status = comparator_result
        self.expected = expected
        self.actual = actual
        self.expected_is_exception = expected_is_exception
        self.actual_is_exception = actual_is_exception
        self.playback = playback
        self.recording_id = recording_id

    def __str__(self):
        result = self.comparator_status.equality_status.name
        if self.comparator_status.message:
            result += u' - ' + self.comparator_status.message
        return result


class CompareExecutionConfig(object):
    def __init__(self, keep_results_in_comparison=False, compare_in_dedicated_process=False,
                 compare_process_recycle_rate=5, compare_process_timeout=10 * 60):
        """
        :param keep_results_in_comparison: Whether to keep results in the comparison result object
        :type keep_results_in_comparison: bool
        :param compare_in_dedicated_process: Whether to conduct the comparison in a dedicated process that is recycled
        every X comparisons or conduct in this process main thread
        :type compare_in_dedicated_process: bool
        :param compare_process_recycle_rate: If comparing in a dedicated process, specified after how many comparison
        should that process be recycled
        :type compare_process_recycle_rate: int
        :param compare_process_timeout: Time in seconds to wait for compare process to end before aborting it
        :type compare_process_timeout: float
        """
        self.keep_results_in_comparison = keep_results_in_comparison
        self.compare_in_dedicated_process = compare_in_dedicated_process
        self.compare_process_recycle_rate = compare_process_recycle_rate
        self.compare_process_timeout = compare_process_timeout


PlayAndCompareResult = namedtuple(
        'PlayAndCompareResult',
        'comparator_result playback recorded_result_is_exception playback_result_is_exception')


class Equalizer(object):
    def __init__(self, recording_ids, player, result_extractor, comparator, comparison_data_extractor=None,
                 compare_execution_config=None):
        """
        :param recording_ids: Iterator of playable recordings to compare
        :type recording_ids: collections.Iterator[str]
        :param player: A function that plays a recording given an id
        :type player: function
        collections.Iterator[playback.comparison.recordings_lookup.PlayableRecording]
        :param result_extractor: A function used to extract the results that needs to be compared from the recording
        and playback outputs
        :type result_extractor: function
        :param comparison_data_extractor: A function used to extract optional data from the recording that will be
        passed to the comparator
        :type comparison_data_extractor: function
        :param comparator: A function used to create the comparison result by comparing the recorded vs replayed result
        :type comparator: function
        :param compare_execution_config: Configuration specific to the comparison execution flow
        :type compare_execution_config: CompareExecutionConfig
        """
        self.recording_ids = recording_ids
        self.player = player
        self.result_extractor = result_extractor
        self.comparison_data_extractor = comparison_data_extractor
        self.comparator = comparator
        self.compare_execution_config = compare_execution_config or CompareExecutionConfig()
        # Init multiprocess related properties
        self._compare_tasks = mp.Queue()
        self._compare_results = mp.Queue()
        self._terminate_process = mp.Event()
        self._compare_process = None
        self._compare_process_age = 0

    def run_comparison(self):
        """
        Runs a comparison between recorded results and their corresponding playbacks
        :return: Comparison result
        :rtype: collections.Iterator[Comparison]
        """
        counter = Counter()
        iteration = 0
        completed = False
        try:
            for iteration, recording_id in enumerate(self.recording_ids, start=1):
                try:
                    play_and_compare_result = self._play_and_compare_recording_within_worker(recording_id)
                    playback = play_and_compare_result.playback

                    # Since comparison was done in another process and result may not be serializable accross processes,
                    # we have to re-extract here again if needed, if playback is None it means we had an error too early
                    # to be able to extract results
                    if playback is not None and self.compare_execution_config.keep_results_in_comparison:
                        recorded_result = self.result_extractor(playback.recorded_outputs)
                        playback_result = self.result_extractor(playback.playback_outputs)
                    else:
                        recorded_result = None
                        playback_result = None

                    comparison = Comparison(
                        play_and_compare_result.comparator_result,
                        recorded_result,
                        playback_result,
                        play_and_compare_result.recorded_result_is_exception,
                        play_and_compare_result.playback_result_is_exception,
                        playback,
                        recording_id
                    )

                    _logger.info(u'Recording {} Comparison result: {}'.format(recording_id,
                                                                              comparison))

                    counter[comparison.comparator_status.equality_status] += 1

                    if iteration % 10 == 0:
                        _logger.info(u'Iteration {} {}'.format(
                            iteration, Equalizer._comparison_stats_repr(counter)))

                    yield comparison
                except Exception as ex:  # pylint: disable=broad-except
                    _logger.info(u'Failed playing recording id {} - {}'.format(recording_id, ex))

                    counter[EqualityStatus.EqualizerFailure] += 1
                    yield Comparison(
                        ComparatorResult.failure_result(ex),
                        None,
                        None,
                        False,
                        False,
                        None,
                        recording_id)

            completed = True

        finally:
            self._terminate_process.set()
            self._compare_tasks.close()
            self._compare_results.close()
            log_prefix = u'Completed all' if completed else u'Error during playback, executed'
            _logger.info(u'{} {} iterations, {}'.format(
                log_prefix, iteration, Equalizer._comparison_stats_repr(counter)))

    def _play_and_compare_recording_within_worker(self, recording_id):
        """
        Play the given recording id and compare the outputs in a worker, the worker process is determined by the
        'playback_in_dedicated_process' flag, If True it will use a dedicated process, else it will run within this
        process
        :param recording_id: Recording id to play
        :type recording_id: str
        :return: Comparison result, playback result, is recorded result an exception,
        is playback result an exception
        :rtype: PlayAndCompareResult
        """
        if not self.compare_execution_config.compare_in_dedicated_process:
            return self._play_and_compare_recording(recording_id)

        self._create_or_recycle_player_process_if_needed()

        # Queue the task for the playback process and wait for its result
        self._compare_tasks.put(recording_id)
        start_time = time()
        timed_out = True
        while time() - start_time <= self.compare_execution_config.compare_process_timeout:
            try:
                succeeded, result = self._compare_results.get(True, 1)
                timed_out = False

                if not succeeded:
                    raise Exception(result)

                break
            except mp.queues.Empty:
                if not self._compare_process.is_alive():
                    self._compare_process = None
                    raise Exception("playback process have died")

        if timed_out:
            self._handle_compare_execution_timeout()

        return result

    def _handle_compare_execution_timeout(self):
        """
        Handle the case that we had a timeout during comparison, killing the process if it is still alive
        """
        _logger.warning('Waiting for comparison result timed out')
        if self._compare_process.is_alive():
            try:
                self._kill_compare_process()
            except OSError as ex:
                # Don't fail when could not kill
                _logger.warning(u'Error while killing worker, {}'.format(str(ex)))
        self._compare_process = None
        raise Exception("timeout while running recording playback and comparison")

    def _kill_compare_process(self):
        """
        Kills the compare process
        :raise exceptions.OSError
        """
        os.kill(self._compare_process.pid, signal.SIGKILL)

    def _create_or_recycle_player_process_if_needed(self):
        """
        Creates a new player resources if one of the following conditions is met:
        (1) This is the first time this method is invoked, hence there is no process already running
        (2) The age of the process (number of playbacks it ran) exceeds the recycle rate
        """
        # Process too old, recycle
        if self._compare_process is not None and \
                self._compare_process_age >= self.compare_execution_config.compare_process_recycle_rate:
            # Signal process to terminate and wait for it to do so
            self._terminate_process.set()
            self._compare_process.join()
            self._compare_process = None
            # Reset terminate state
            self._terminate_process.clear()

        if self._compare_process is None:
            self._create_new_player_process()

        # Increase process age
        self._compare_process_age += 1

    def _create_new_player_process(self):
        """
        Creates and start new player process, ready to take playback tasks
        """
        self._compare_process = mp.Process(
            target=self._playback_process_target, name='Playback runner')
        self._compare_process.start()
        self._compare_process_age = 0

    def _playback_process_target(self):
        """
        Entry point for the playback process (target function),
        """
        while not self._terminate_process.is_set():
            try:
                recording_id = self._compare_tasks.get(True, 0.05)
                try:
                    execution_result = self._play_and_compare_recording(recording_id)
                    self._compare_results.put((True, execution_result))
                except Exception as ex:  # pylint: disable=broad-except
                    logging.info(u'Failure during play and compare in playback process of id {} - {}'.format(
                        recording_id, ex))
                    self._compare_results.put((False, str(ex)))
            except mp.queues.Empty:
                # Every 0.05 second the process will get this as we poll with 0.05 second timeout
                # (in order to listen to termination event)
                pass

    def _play_and_compare_recording(self, recording_id):
        """
        Plays the given recording id and compare its results
        :param recording_id: Recording id to run and compare results
        :type recording_id: str
        :return: Comparison result, playback result, is recorded result an exception,
        is playback result an exception
        :rtype: PlayAndCompareResult
        """
        playback = None
        recorded_result_is_exception = None
        playback_result_is_exception = None

        try:
            playback = self.player(recording_id)

            recorded_result = self.result_extractor(playback.recorded_outputs)
            playback_result = self.result_extractor(playback.playback_outputs)

            recorded_result_is_exception = isinstance(recorded_result, Exception)
            playback_result_is_exception = isinstance(playback_result, Exception)

            comparison_data = {} if self.comparison_data_extractor is None else \
                self.comparison_data_extractor(playback.original_recording)

            comparator_result = self.comparator(recorded_result, playback_result, **comparison_data)
            if not isinstance(comparator_result, ComparatorResult):
                comparator_result = ComparatorResult(comparator_result)

            return PlayAndCompareResult(comparator_result,
                                        playback,
                                        recorded_result_is_exception,
                                        playback_result_is_exception)

        except Exception as ex:  # pylint: disable=broad-except
            return PlayAndCompareResult(ComparatorResult.failure_result(ex),
                                        playback,
                                        recorded_result_is_exception,
                                        playback_result_is_exception)

    @staticmethod
    def _comparison_stats_repr(counter):
        """
        :param counter:
        :type counter: collections.Counter
        :return: Representation of comparison statistics
        :rtype: str
        """
        return u'comparison stats: (equal - {}, fixed - {}, diff - {}, failed - {}, equalizer failures - {}'.format(
            counter[EqualityStatus.Equal],
            counter[EqualityStatus.Fixed],
            counter[EqualityStatus.Different],
            counter[EqualityStatus.Failed],
            counter[EqualityStatus.EqualizerFailure])
