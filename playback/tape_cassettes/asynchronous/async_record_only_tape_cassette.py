import logging
import queue
from threading import Event, Thread

from playback.recordings.memory.memory_recording import MemoryRecording
from playback.tape_cassette import TapeCassette

_logger = logging.getLogger(__name__)


class AsyncRecordOnlyTapeCassette(TapeCassette):
    # pylint: disable=too-many-instance-attributes
    """
    Wraps TapeCassette with asynchronous execution of the operation that change the state of the recording, this
    cassette can only be used for recording and for playback
    """
    def __init__(self, tape_cassette, flush_interval=0.1, timeout_on_close=10):
        """
        :param tape_cassette: The storage driver to hold the recording in and wrap with asynchronous behaviour
        :type tape_cassette: playback.tape_cassette.TapeCassette
        :param flush_interval: Interval to flush recording to the underlying storage (tape cassette)
        :type flush_interval: float
        :param timeout_on_close: How much time to wait for joining recording thread on close
        :type timeout_on_close: float
        """
        self.wrapped_tape_cassette = tape_cassette
        self._flush_interval = flush_interval
        self._timeout_on_close = timeout_on_close
        self._stop_event = Event()
        self._operations_queue = queue.Queue()
        self._update_recording_thread = Thread(target=self._recording_loop, name="AsyncTapeCassette Thread")
        self._update_recording_thread.setDaemon(True)
        self._started = False

    def start(self):
        """
        Starts the recording thread
        """
        _logger.info("Starting AsyncTapeCassette")
        self._started = True
        self._update_recording_thread.start()

    def close(self):
        """
        Signal the cassette to close, this will signal the underlying thread to stop waiting for more recording and
        will join it until its completed sending remaining recordings using the given timeout
        """
        _logger.info("Shutting down AsyncTapeCassette (joining for {}s)".format(self._timeout_on_close))
        self._started = False
        self._stop_event.set()
        try:
            self._update_recording_thread.join(self._timeout_on_close)
        except RuntimeError:
            # If thread was not started
            pass
        self.wrapped_tape_cassette.close()
        _logger.info("AsyncTapeCassette has shutdown")

    def get_recording(self, recording_id):
        raise TypeError("AsyncTapeCassette should only be used for recording, not playback")

    def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None,
                           random_results=False):
        raise TypeError("AsyncTapeCassette should only be used for recording, not playback")

    def extract_recording_category(self, recording_id):
        raise TypeError("AsyncTapeCassette should only be used for recording, not playback")

    def create_new_recording(self, category):
        """
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        :return: Creates a new recording object
        :rtype: playback.recording.Recording
        """
        assert self._started, "Recording thread is not running"
        # The assumption is that create new recording is not a long running task and hence we can do it synchronously,
        # if that will not be the case the creation it self needs to become async as well
        return AsyncRecording(
            self.wrapped_tape_cassette.create_new_recording(category),
            self._add_async_operation,
            self._wait_for_operations_processing
        )

    def _add_async_operation(self, func):
        """
        Adds operation to be executed asynchronously
        :param func: Operation to execute
        :type func: function
        """
        
        self._operations_queue.put(func)

    def _wait_for_operations_processing(self):
        """
        Waits for the completion of all operations in the operations queue.
V
        This method blocks the execution until all tasks in the operations queue
        have been processed and marked as complete.
        """
        self._operations_queue.join()

    def _save_recording(self, recording):
        """
        Saves given recording
        :param recording: Recording to save
        :type recording: AsyncRecording
        """
        self._add_async_operation(lambda: self.wrapped_tape_cassette.save_recording(recording.wrapped_recording))

    def _recording_loop(self):
        """
        Runs the recording loop in a dedicated thread
        """
        _logger.info('Async recording thread started')
        while not self._stop_event.is_set():
            self._consume_operations_queue()
            self._stop_event.wait(self._flush_interval)

        _logger.info('Async recording thread signaled to stop thread, flushing any pending recording')

        # Consume any remaining operations (like `save_recording` operation)
        self._consume_operations_queue()
        _logger.info('Async recording thread stopped')

    def _consume_operations_queue(self):
        """
        Consumes the whole operations queue
        """
        while True:
            try:
                operation = self._operations_queue.get_nowait()

                try:
                    operation()
                except Exception as ex:  # pylint: disable=broad-except
                    _logger.exception(u"Error running recording operation - {}".format(ex))

                # Mark the task as done. Once all tasks have been marked as completed,
                # the join() method will return.
                self._operations_queue.task_done()
            except queue.Empty:
                break


class AsyncRecording(MemoryRecording):
    """
    Wraps a recording with asynchronous set behaviour, keep recording data transient in memory during the recording for
    being able to fetch data from the recording or the metadata if needed
    """

    def __init__(self, wrapped_recording, add_async_operation_callback, wait_for_operations_processing):
        """
        :param wrapped_recording: Recording to wrap with asynchronous set data
        :type wrapped_recording: Recording
        :param add_async_operation_callback: A callback to add operations to be executed asynchronously
        :type add_async_operation_callback: function
        """
        # This cassette is only used for recording, hence it has no use of keeping the playback factory
        super(AsyncRecording, self).__init__(wrapped_recording.id)
        self.wrapped_recording = wrapped_recording
        self._add_async_operation_callback = add_async_operation_callback
        self._wait_for_operations_processing = wait_for_operations_processing

    def _set_data(self, key, value):
        """
        Sets data in the recording
        :param key: data key
        :type key: basestring
        :param value: data value (serializable)
        :type value: Any
        """
        # We don't want to save the intercepted value in the AsyncRecording itself to not consume memory.
        # If needed, the data can be acquired from the wrapped "real" recording. But we are setting en empty value
        # so that the call to `get_all_keys` can still be done without the need of flushing the wrapped recording.
        super(AsyncRecording, self)._set_data(key, None)
        self._add_async_operation_callback(lambda: self.wrapped_recording.set_data(key, value))

    def _add_metadata(self, metadata):
        """
        :param metadata: Metadata to add to the recording
        :type metadata: dict
        """
        super(AsyncRecording, self)._add_metadata(metadata)
        self._add_async_operation_callback(lambda: self.wrapped_recording.add_metadata(metadata))

    def get_data(self, key):
        self._wait_for_operations_processing()
        return self.wrapped_recording.get_data(key)

    def get_data_direct(self, key):
        self._wait_for_operations_processing()
        return self.wrapped_recording.get_data_direct(key)
