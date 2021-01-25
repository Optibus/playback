from playback.recording import Recording
from playback.tape_cassette import TapeCassette
from threading import Event, Lock, Thread
import logging


_logger = logging.getLogger(__name__)


class AsyncRecordOnlyTapeCassette(TapeCassette):
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
        self._recording_operation_buffer = []
        self._stop_event = Event()
        self._lock = Lock()
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

    def iter_recording_ids(self, category, start_date=None, end_date=None):
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
        return AsyncRecording(self.wrapped_tape_cassette.create_new_recording(category), self._add_async_operation)

    def _add_async_operation(self, func):
        """
        Adds operation to be executed asynchronously
        :param func: Operation to execute
        :type func: function
        """
        with self._lock:
            self._recording_operation_buffer.append(func)

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
            self._flush_recording()
            self._stop_event.wait(self._flush_interval)
        _logger.info('Async recording thread signaled to stop thread, flushing any pending recording')

        # Flush any pending recording
        self._flush_recording()
        _logger.info('Async recording thread stopped')

    def _flush_recording(self):
        """
        Flush current pending recording to the underlying storage, this method is blocking till recording is done
        """
        # We don't want to keep the lock while doing actual recording, hence we copy the buffer state and release
        # the lock
        _logger.debug('Flushing pending recording operations')
        with self._lock:
            current_flushed_operations = self._recording_operation_buffer
            self._recording_operation_buffer = []

        # Execute actual recording
        for recording_operation in current_flushed_operations:
            try:
                recording_operation()
            except Exception:
                _logger.exception(u"Error running recording operation")


class AsyncRecording(Recording):
    """
    Wraps a recording with asynchronous set behaviour
    """

    def __init__(self, wrapped_recording, add_async_operation_callback):
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

    def _set_data(self, key, value):
        """
        Sets data in the recording
        :param key: data key
        :type key: basestring
        :param value: data value (serializable)
        :type value: Any
        """
        self._add_async_operation_callback(lambda: self.wrapped_recording.set_data(key, value))

    def get_data(self, key):
        raise Exception("AsyncTapeCassette should only be used for recording, not playback")

    def get_all_keys(self):
        raise Exception("AsyncTapeCassette should only be used for recording, not playback")

    def _add_metadata(self, metadata):
        """
        :param metadata: Metadata to add to the recording
        :type metadata: dict
        """
        self._add_async_operation_callback(lambda: self.wrapped_recording.add_metadata(metadata))

    def get_metadata(self):
        raise Exception("AsyncTapeCassette should only be used for recording, not playback")
