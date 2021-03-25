# pylint: disable=not-context-manager
# pylint: disable=broad-except
from __future__ import absolute_import
from collections import namedtuple, Counter
import logging
from random import Random
from datetime import datetime
from time import time
from jsonpickle import encode, decode
from decorator import contextmanager

from playback.exceptions import InputInterceptionKeyCreationError, OperationExceptionDuringPlayback, \
    TapeRecorderException, RecordingKeyError

_logger = logging.getLogger(__name__)


def pickle_copy(value):

    """ copies any object (deeply) by pickly encoding/decoding it
    :type value: any
    :param value: the value you to be copied
    :rtype: any
    """
    return decode(encode(value, unpicklable=True))


class TapeRecorder(object):
    """
    This class is used to "record" operation and "replay" (rerun) recorded operation on any code version.
    The recording is done by placing different decorators that intercepts the operation, its inputs and outputs by using
    decorators.
    """

    DURATION = '_tape_recorder_recording_duration'
    RECORDED_AT = '_tape_recorder_recorded_at'
    OPERATION_OUTPUT_ALIAS = '_tape_recorder_operation'
    OPERATION_CLASS = '_tape_recorder_operation_class'
    EXCEPTION_IN_OPERATION = '_tape_recorder_exception_in_operation'

    def __init__(self, tape_cassette):
        """
        :param tape_cassette: The storage driver to hold the recording in
        :type tape_cassette: playback.tape_cassette.TapeCassette
        """
        self.tape_cassette = tape_cassette
        self.recording_enabled = False
        self._active_recording = None
        self._active_recording_parameters = None
        self._playback_recording = None
        self._playback_outputs = []
        self._invoke_counter = Counter()
        self._classes_recording_params = {}
        self._random = Random(110613)
        self._force_sample = False
        self._currently_in_interception = False

    @contextmanager
    def start_recording(self, category, metadata, post_operation_metadata_extractor=None):
        """
        Starts a recording scope
        :param post_operation_metadata_extractor: Callback used to extract extra metadata once the operation
        is completed and add it to the recording metadata
        :type post_operation_metadata_extractor: function
        :param metadata: Recording metadata
        :type metadata: dict
        :param category: A category to classify the recording in (e.g operation class) (serializable)
        :type category: Any
        """
        assert self._active_recording is None, 'Cannot start recording while another recording is already running'

        self._active_recording = self.tape_cassette.create_new_recording(category)
        self._active_recording_parameters = self._classes_recording_params.get(
            metadata[TapeRecorder.OPERATION_CLASS], RecordingParameters())
        _logger.info(u'Starting recording for category {} with id {}'.format(category, self._active_recording.id))
        start_time = time()
        try:
            yield
            metadata[TapeRecorder.EXCEPTION_IN_OPERATION] = False
        except Exception:
            metadata[TapeRecorder.EXCEPTION_IN_OPERATION] = True
            raise
        finally:
            # Recording was discarded
            if self._active_recording is not None:
                recording = self._active_recording
                force_sample = self.is_recording_sample_forced
                recording_parameters = self._active_recording_parameters

                # Clear recording not to leave recording in active state if we have
                # some exception raised in following code
                self._reset_active_recording()

                if not self._should_sample_active_recording(recording, recording_parameters, force_sample):
                    self.tape_cassette.abort_recording(recording)
                else:
                    duration = time() - start_time

                    self._add_post_operation_metadata(recording, metadata, post_operation_metadata_extractor, duration)

                    try:
                        self.tape_cassette.save_recording(recording)
                        _logger.info(u'Finished recording of category {} with id {}, recording duration {:.2f}'.format(
                            category, recording.id, duration))
                    except Exception:
                        _logger.exception(u'Failed saving recording of category {} with id {}'.format(
                            category, recording.id))

    def discard_recording(self):
        """
        Discards currently active recording process
        """
        if self._active_recording is not None:
            _logger.info(
                u'Recording with id {} was discarded'.format(self._active_recording.id))
            self.tape_cassette.abort_recording(self._active_recording)
            self._reset_active_recording()

    def force_sample_recording(self):
        """
        Make sure currently active recording will be sampled (unless explicitly discarded or set to ignore enforcement)
        """
        if self._active_recording is not None:
            if self._active_recording_parameters.ignore_enforced_sampling:
                return
            _logger.info(
                u'Recording with id {} sampling is enforced'.format(self._active_recording.id))
            self._force_sample = True

    @property
    def is_recording_sample_forced(self):
        """
        :return: If current recording sampling is enforced, meaning it should be kept regardless of any sampling
        calculation
        :rtype: bool
        """
        return self._force_sample

    @staticmethod
    def _add_post_operation_metadata(recording, metadata, post_operation_metadata_extractor, duration):
        """
        :param recording: Active recording
        :type recording: playback.recording.Recording
        :param metadata: Currently collected metadata
        :type metadata: dict
        :param post_operation_metadata_extractor: Callback used to extract extra metadata once the operation
        is completed and add it to the recording metadata
        :type post_operation_metadata_extractor: function
        :param duration: Recording duration
        :type duration: float
        """
        metadata[TapeRecorder.DURATION] = duration
        metadata[TapeRecorder.RECORDED_AT] = str(datetime.utcnow())
        if post_operation_metadata_extractor:
            try:
                metadata.update(post_operation_metadata_extractor())
            except Exception:
                _logger.exception(u'Exception caught while extractor post operation metadata for recording id {}, '
                                  u'skipping metadata extraction'.format(recording.id))
        recording.add_metadata(metadata)

    def _reset_active_recording(self):
        """
        Reset recording state, make tape recorder ready for next recording
        """
        self._active_recording = None
        self._active_recording_parameters = None
        self._force_sample = False
        # Clear any previous invocation counter state
        self._invoke_counter = Counter()

    def _record_data(self, key, data):
        """
        Puts current data under given key in the current recording
        :param key: Data key
        :type key: basestring
        :param data: Data to record (it needs to be serializable)
        :type data: Any
        """
        self._assert_recording()
        _logger.info(u'Recording data for recording id {} under key {}'.format(self._active_recording.id, key))
        self._active_recording[key] = data

    def _assert_recording(self):
        """
        Assert there is active recording
        """
        assert self._active_recording is not None, 'No recoding is currently being made'

    def _record_output(self, alias, invocation_number, args, kwargs, data_handler=None):
        """
        Record the given invocation as output
        :param alias: Output alias
        :type alias: str
        :param invocation_number: Current invocation number for the given alias
        :type invocation_number: int
        :param args: Invocation arguments
        :type args: tuple
        :param kwargs: Invocation keyword arguments
        :type kwargs: dict
        :param data_handler: Optional data handler that prepare and restore the output data for and from the recording
        when default pickle serialization is not enough.
        :type data_handler: playback.interception.output_interception.OutputInterceptionDataHandler
        """
        interception_key = self._output_interception_key(alias, invocation_number) + '.output'

        if data_handler:
            try:
                value = data_handler.prepare_output_for_recording(interception_key, args, kwargs)
            except Exception:
                error_message = u'Prepare output for recording error for interception key \'{}\''.format(
                    interception_key)

                _logger.exception(error_message)

                self.discard_recording()
                return
        else:
            value = {'args': list(args), 'kwargs': kwargs}

        if self.in_playback_mode:
            self._playback_outputs.append(Output(interception_key, value))
            return

        # Recording is discarded
        if self._active_recording is None:
            return

        self._record_data(interception_key, value)

    def enable_recording(self):
        """
        Enable recording and interception for all decorated places
        """
        _logger.info('Enabling recording')
        self.recording_enabled = True

    def disable_recording(self):
        """
        Disable recording of all interception in all decorated places
        """
        _logger.info('Disabling recording')
        self.recording_enabled = False

    @property
    def in_recording_mode(self):
        """
        :return: Is in recording mode
        :rtype: bool
        """
        return self.recording_enabled and self._active_recording is not None

    @property
    def in_playback_mode(self):
        """
        :return: Is in playback mode
        :rtype: bool
        """
        return self._playback_recording is not None

    @property
    def current_recording_id(self):
        """
        :return: Returns the id of recording in the current context or None if there is no such recording
        :rtype: basestring or None
        """
        if self.in_recording_mode:
            return self._active_recording.id
        if self.in_playback_mode:
            return self._playback_recording.id
        return None

    @property
    def _should_intercept(self):
        """
        :return: Should run interception
        :rtype: bool
        """
        # We don't want interception inside interception (inception)
        return not self._currently_in_interception and (self.in_recording_mode or self.in_playback_mode)

    def operation(self, metadata_extractor=None):
        """
        :param metadata_extractor: Extracts metadata from the operation when an invocation is recorded
        :type metadata_extractor: function
        :return: Decorated function that should be a recorder operation
        :rtype: function
        """
        return self._operation(class_function=False, metadata_extractor=metadata_extractor)

    def recording_params(self, recording_parameters=None, **kwargs):
        """
        :param recording_parameters: Recording Parameters objects for this operation
        :type sampling_rate: RecordingParameters
        :return: Class decorator that configure specific recording parameter for the operation class
        :rtype: function
        """

        def wrapper(cls):
            self._classes_recording_params[cls] = recording_parameters or RecordingParameters(**kwargs)
            return cls

        return wrapper

    def class_operation(self, metadata_extractor=None):
        """
        :param metadata_extractor: Extracts metadata from the operation when an invocation is recorded
        :type metadata_extractor: function
        :return: Decorated class function that should be a recorder operation
        :rtype: function
        """
        return self._operation(class_function=True, metadata_extractor=metadata_extractor)

    def _operation(self, class_function, metadata_extractor=None):
        """
        :param class_function: Is this a class function or instance function
        :type class_function: bool
        :param metadata_extractor: Extracts metadata at the end of operation when an invocation is
        recorded
        :type metadata_extractor: function
        :return: Decorated function that should be a recorder operation
        :rtype: function
        """

        def func_decoration(func):

            def decorated_function(*args, **kwargs):
                if self.in_playback_mode:
                    return self._execute_operation_func(func, args, kwargs)

                if not self.recording_enabled:
                    return func(*args, **kwargs)

                cls = args[0] if class_function else type(args[0])

                recording_parameters = self._classes_recording_params.get(cls, RecordingParameters())
                if recording_parameters.skipped:
                    return func(*args, **kwargs)

                class_name = cls.__name__

                # As meta add the operation class when possible and class name as category
                metadata = {TapeRecorder.OPERATION_CLASS: cls}

                def post_operation_metadata_extractor():
                    return metadata_extractor(*args, **kwargs)

                post_operation = post_operation_metadata_extractor if metadata_extractor else None

                with self.start_recording(
                        class_name, metadata,
                        post_operation_metadata_extractor=post_operation):
                    return self._execute_operation_func(func, args, kwargs)

            return decorated_function

        return func_decoration

    def _execute_operation_func(self, func, args, kwargs):
        """
        Executes the operation function record its output and return the result
        :param func: Operation function
        :type func: function
        :param args: Execution args
        :type args: tuple
        :param kwargs: Execution kwargs
        :type kwargs: dict
        :return: Function result
        :rtype: Any
        """
        try:
            result = func(*args, **kwargs)
        except TapeRecorderException:
            raise
        except Exception as ex:
            self._record_output(TapeRecorder.OPERATION_OUTPUT_ALIAS, invocation_number=1,
                                args=[self._serializable_exception_form(ex)], kwargs={})

            if self.in_playback_mode:
                # In playback mode we want to capture this as an error that is an output of the function
                # which is a legit recorded result, and not fail the playback it self
                raise OperationExceptionDuringPlayback()

            raise

        # We record the operation result as an output
        self._record_output(TapeRecorder.OPERATION_OUTPUT_ALIAS, invocation_number=1, args=[result],
                            kwargs={})
        return result

    def _should_sample_active_recording(self, recording, recording_parameters, force_sample):
        """
        :param recording: Active recording
        :type recording: playback.recording.Recording
        :param recording_parameters: Current recording parameters
        :type recording_parameters: RecordingParameters
        :param force_sample: Whether current recording sampling is forced

        :type force_sample: bool
        :return: Whether to sample current recording based on its class decoration and sampling calculations
        :rtype: bool
        """
        if force_sample:
            return True

        if recording_parameters.sampling_rate >= 1:
            return True

        sample_value = self._random.random()
        part_of_sample = sample_value <= recording_parameters.sampling_rate
        _logger.info(u'Recording id {} sampled = {} - ({:.3f} <= sampling rate:{:.2f})?'.format(
            recording.id, part_of_sample, sample_value, recording_parameters.sampling_rate))
        return part_of_sample

    @staticmethod
    def _serializable_exception_form(exception):
        """
        :param exception: Exception to return a serializable form
        :type exception: exceptions.Exception
        :return: Serializable form of the exception, if the exception is self is serializable will return the exception
        """
        try:
            encode(exception, unpicklable=True)
            return exception
        except Exception:
            # Upon any failure of encoding, we return a basic form of type of exception and its message
            return {'error_type': type(exception), 'error_repr': repr(exception)}

    def record_data(self, key, value):
        """
        Record given data if in recording mode
        :param key: Data recording key
        :type key: str
        :param value: Value to record (Needs to be serializable)
        :type value: Any
        """
        if not self.in_recording_mode:
            return

        self._record_data(key, value)

    def play_data(self, key):
        """
        Play recorded data if in playback mode
        :param key: Recorded data key
        :type key: str
        :return: Recorded data under given key or None if not in playback mode
        :rtype: Any
        :raise: playback.exceptions.RecordingKeyError
        """
        if not self.in_playback_mode:
            return None

        return self._playback_recording.get_data(key)

    def static_intercept_input(self, alias, alias_params_resolver=None, data_handler=None, capture_args=None,
                               run_intercepted_when_missing=False):
        """
        Decorates a static function that acts as an input to the operation, the result of the function is
        the  recorded input and the passed arguments and function name (or alias) or used as key for the input
        :param alias: Input alias, used to uniquely identify the input function, hence the name should be unique across
        all relevant inputs this operation can reach. This should be renamed as it will render previous recording
        useless
        :type alias: str
        :param alias_params_resolver: Optional function that resolve parameters inside alias if such are given,
        this is useful when you have the same input method invoked many times with the same arguments on different class
        instances
        :type alias_params_resolver: function
        :param data_handler: Optional data handler that prepare and restore the input data for and from the recording
        when default pickle serialization is not enough
        :type data_handler: playback.interception.input_interception.InputInterceptionDataHandler
        :param capture_args: If a list is given, it will annotate which arg indices and/or names should be
        captured as part of the intercepted key (invocation identification). If None, all args are captured
        :type capture_args: list of CapturedArg
        :param run_intercepted_when_missing: If no matching content is found on recording during playback,
        run the original intercepted method
        :type run_intercepted_when_missing: bool
        :return: Decorated function
        :rtype: function
        """
        return self._intercept_input(alias, alias_params_resolver, data_handler, capture_args,
                                     run_intercepted_when_missing, static_function=True)

    def intercept_input(self, alias, alias_params_resolver=None, data_handler=None, capture_args=None,
                        run_intercepted_when_missing=False):
        """
        Decorates a function that that acts as an input to the operation, the result of the function is the
        recorded input and the passed arguments and function name (or alias) or used as key for the input
        :param alias: Input alias, used to uniquely identify the input function, hence the name should be unique across
        all relevant inputs this operation can reach. This should be renamed as it will render previous recording
        useless
        :type alias: str
        :param alias_params_resolver: Optional function that resolve parameters inside alias if such are given,
        this is useful when you have the same input method invoked many times with the same arguments on different class
        instances
        :type alias_params_resolver: function
        :param data_handler: Optional data handler that prepare and restore the input data for and from the recording
        when default pickle serialization is not enough
        :type data_handler: playback.interception.input_interception.InputInterceptionDataHandler
        :param capture_args: If a list is given, it will annotate which arg indices and/or names should be
        captured as part of the intercepted key (invocation identification). If None, all args are captured
        :type capture_args: list of CapturedArg
        :param run_intercepted_when_missing: If no matching content is found on recording during playback,
        run the original intercepted method
        :type run_intercepted_when_missing: bool
        :return: Decorated function
        :rtype: function
        """
        return self._intercept_input(alias, alias_params_resolver, data_handler, capture_args,
                                     run_intercepted_when_missing, static_function=False)

    def static_intercept_output(self, alias, data_handler=None, fail_on_no_recorded_result=True):
        """
        Decorates a static function that that acts as an output of the operation, the arguments are recorded as the
        output and the result of the function is captured
        :param alias: Output alias, used to uniquely identify the input function, hence the name should be unique
        across all relevant inputs this operation can reach. This should be renamed as it will render previous
        recording useless
        :type alias: str
        :param data_handler: Optional data handler that prepare and restore the output data for and from the recording
        when default pickle serialization is not enough.
        :type data_handler: playback.interception.output_interception.OutputInterceptionDataHandler
        :param fail_on_no_recorded_result: Whether to fail if there is no recording of a result or return None.
        Setting this to False is useful when there are already pre existing recording and this is a new output
        interception while we want to be able to playback old recordings and the return value of the output is not
        actually used.
        :type fail_on_no_recorded_result: bool
        :return: Decorated function
        :rtype: function
        """
        return self._intercept_output(alias, data_handler, fail_on_no_recorded_result, static_function=True)

    def intercept_output(self, alias, data_handler=None, fail_on_no_recorded_result=True):
        """
        Decorates a function that that acts as an output of the operation, the arguments are recorded as the output and
        the result of the function is captured
        output and the result of the function is captured
        :param alias: Output alias, used to uniquely identify the input function, hence the name should be unique
        across all relevant inputs this operation can reach. This should be renamed as it will render previous
        recording useless
        :type alias: str
        :param data_handler: Optional data handler that prepare and restore the output data for and from the recording
        when default pickle serialization is not enough.
        :type data_handler: playback.interception.output_interception.OutputInterceptionDataHandler
        :param fail_on_no_recorded_result: Whether to fail if there is no recording of a result or return None.
        Setting this to False is useful when there are already pre existing recordings and this is a new output
        interception while we want to be able to playback old recordings and the return value of the output is not
        actually used. Defaults to True
        :type fail_on_no_recorded_result: bool
        :return: Decorated function
        :rtype: function
        """
        return self._intercept_output(alias, data_handler, fail_on_no_recorded_result, static_function=False)

    def _intercept_output(self, alias, data_handler, fail_on_no_recorded_result, static_function):
        """
        Decorates a function that that acts as an output of the operation, the arguments are recorded as the output and
        the result of the function is captured
        output and the result of the function is captured
        :param alias: Output alias, used to uniquely identify the input function, hence the name should be unique
        across all relevant inputs this operation can reach. This should be renamed as it will render previous
        recording useless
        :type alias: str
        :param data_handler: Optional data handler that prepare and restore the output data for and from the recording
        when default pickle serialization is not enough.
        :type data_handler: playback.interception.output_interception.OutputInterceptionDataHandler
        :param fail_on_no_recorded_result: Whether to fail if there is no recording of a result or return None.
        Setting this to False is useful when there are already pre existing recording and this is a new output
        interception while we want to be able to playback old recordings and the return value of the output is not
        actually used.
        :type fail_on_no_recorded_result: bool
        :param static_function: Is this a static function
        :type static_function: bool
        :return: Decorated function
        :rtype: function
        """

        def func_decoration(func):

            def decorated_function(*args, **kwargs):
                if not self._should_intercept:
                    return func(*args, **kwargs)

                # If same alias (function) is invoked more than once we want to track each output invocation
                self._invoke_counter[alias] += 1
                invocation_number = self._invoke_counter[alias]

                # Both in recording and playback mode we record what is sent to the output
                self._record_output(alias, invocation_number, args if static_function else args[1:], kwargs,
                                    data_handler)

                # Record output may have failed and discarded current recording which would make should intercept false
                if not self._should_intercept:
                    return func(*args, **kwargs)

                interception_key = self._output_interception_key(alias, invocation_number) + '.result'

                if self.in_playback_mode:
                    # Return recording of input invocation
                    try:
                        return self._playback_recorded_interception(interception_key, args, kwargs)
                    except RecordingKeyError:
                        if fail_on_no_recorded_result:
                            raise
                        return None

                # Record the output result so it can be returned in playback mode
                return self._execute_func_and_record_interception(func, interception_key, args, kwargs)

            return decorated_function

        return func_decoration

    def _intercept_input(self, alias, alias_params_resolver, data_handler, capture_args, run_intercepted_when_missing,
                         static_function):
        """
        Decorates a function that that acts as an input to the operation, the result of the function is the
        recorded input and the passed arguments and function name (or alias) or used as key for the input
        :param alias: Input alias, used to uniquely identify the input function, hence the name should be unique across
        all relevant inputs this operation can reach. This should be renamed as it will render previous recording
        useless
        :type alias: str
        :param alias_params_resolver: Optional function that resolve parameters inside alias if such are given,
        this is useful when you have the same input method invoked many times with the same arguments on different class
        instances
        this is useful when you have the same input method invoked many times on different class instances
        :type alias_params_resolver: function
        :param data_handler: Optional data handler that prepare and restore the input data for and from the recording
        when default pickle serialization is not enough
        :type data_handler: playback.interception.input_interception.InputInterceptionDataHandler
        :param capture_args: If a list is given, it will annotate which arg indices and/or names should be
        captured as part of the intercepted key (invocation identification). If None, all args are captured
        :type capture_args: list of CapturedArg
        :param run_intercepted_when_missing: If no matching content is found on recording during playback,
        run the original intercepted method
        :type run_intercepted_when_missing: bool
        :param static_function: Is this a static function
        :type static_function: bool
        :return: Decorated function
        :rtype: function
        """

        def func_decoration(func):

            is_property = isinstance(func, property)
            if is_property:
                func = func.__get__

            def decorated_function(*args, **kwargs):
                if not self._should_intercept:
                    return func(*args, **kwargs)

                try:
                    formatted_alias = self._format_alias(alias, alias_params_resolver, *args, **kwargs)
                    interception_key = self._input_interception_key(formatted_alias, capture_args,
                                                                    static_function, *args, **kwargs)
                except Exception as ex:
                    error_message = u'Input interception key creation error for alias \'{}\' - {}'.format(
                        alias, repr(ex))

                    if self.in_playback_mode:
                        raise InputInterceptionKeyCreationError(error_message.encode('utf-8'))

                    _logger.exception(error_message)

                    interception_key = None
                    self.discard_recording()

                if self.in_playback_mode:
                    # Return recording of input invocation
                    try:
                        return self._playback_recorded_interception(interception_key, args, kwargs, data_handler)
                    except RecordingKeyError:
                        if not run_intercepted_when_missing:
                            raise
                        # Run the original method when content was missing in recording
                        return func(*args, **kwargs)

                return self._execute_func_and_record_interception(func, interception_key, args, kwargs, data_handler)

            return property(decorated_function) if is_property else decorated_function

        return func_decoration

    @staticmethod
    def _format_alias(alias, alias_params_resolver, *args, **kwargs):
        """
        Formats the alias applying alias name resolver if provided
        :param alias: Alias to format
        :type alias: basestring
        :param alias_params_resolver: Optional function that resolve parameters inside alias if such are given,
        this is useful when you have the same input method invoked many times with the same arguments on different class
        instances
        :type alias_params_resolver: function
        :param args: Invocation args
        :type args: tuple
        :param kwargs: Invocation kwargs
        :type kwargs: dict
        :return: Formatted alias
        :rtype: basestring
        """
        if not alias_params_resolver:
            return alias

        return alias.format(**alias_params_resolver(*args, **kwargs))

    def _playback_recorded_interception(self, interception_key, args, kwargs, data_handler=None):
        """
        Playback the recorded data (value or exception) under the given interception key
        :param interception_key: Interception key of recorded data
        :type interception_key: basestring
        :param args: invocation args
        :type args: tuple
        :param kwargs: invocation kwrags
        :type kwargs: dict
        :param data_handler: Optional data handler that prepare and restore the input data for and from the recording
        :type data_handler: playback.interception.input_interception.InputInterceptionDataHandler
        :return: Recorded intercepted value
        """
        recorded = self._playback_recording.get_data(interception_key)
        if 'exception' in recorded:
            raise recorded['exception']

        value = recorded['value']
        if data_handler:
            value = data_handler.restore_input_from_recording(value, args, kwargs)
        return value

    @contextmanager
    def _enter_interception_context(self):
        """
        Activate currently in interception mode so inner methods that also marked for interception will not be
        intercepted as their output/intput is already captured by the wrapping interception
        """
        assert not self._currently_in_interception
        self._currently_in_interception = True
        try:
            yield
        finally:
            self._currently_in_interception = False

    def _execute_func_and_record_interception(self, func, interception_key, args, kwargs, data_handler=None):
        """
        Executes the given function and record the result/exception of the outcome
        :param func: Function to execute
        :type func: function
        :param interception_key: Key to record the data under
        :type interception_key: basestring
        :param args: invocation args
        :type args: tuple
        :param kwargs: invocation kwrags
        :type kwargs: dict
        :param data_handler: Optional data handler that prepare and restore the input data for and from the recording
        :type data_handler: playback.interception.input_interception.InputInterceptionDataHandler
        :return: Invocation result
        """
        # Mark that this invocation is under interception context so any inner interception will be skipped
        with self._enter_interception_context():
            try:
                result = func(*args, **kwargs)
            except Exception as ex:
                if interception_key is not None:
                    # Record exception marking it as exception so we know to throw on playback
                    self._record_data(interception_key, {'exception': ex})
                raise

        if interception_key is not None:
            try:
                recorded_result = data_handler.prepare_input_for_recording(interception_key, result, args, kwargs) \
                    if data_handler else result
            except Exception:
                error_message = u'Prepare input for recording error for interception key \'{}\''.format(
                    interception_key)

                _logger.exception(error_message)

                self.discard_recording()
                return result

            if self._active_recording_parameters.copy_data_on_intercepion:
                try:
                    recorded_result = pickle_copy(recorded_result)
                except Exception as ex:
                    _logger.warning(u"recorded data couldn't be copied (type={} exception={})".format(
                        type(recorded_result), repr(ex)))

            # Record result
            self._record_data(interception_key, {'value': recorded_result})

        return result

    def play(self, recording_id, playback_function):
        """
        Play again the recorder operation on current code
        :param recording_id: Id of the recording
        :type recording_id: basestring
        :param playback_function: A function that plays back the operation using the recording in the given id
        :type playback_function: function
        :return: Playback result of rerunning the recorded operation
        :rtype: Playback
        """
        recording = self.tape_cassette.get_recording(recording_id)
        self._playback_recording = recording
        start = time()

        try:
            playback_function(recording)
        except OperationExceptionDuringPlayback:
            # This is an exception that was raised by the played back function, should be treated as part of the
            # recording output
            pass
        finally:
            playback_duration = time() - start
            playback_outputs = self._playback_outputs
            self._playback_recording = None
            self._playback_outputs = []
            # Clear any previous invocation counter state
            self._invoke_counter = Counter()

        recorded_duration = recording.get_metadata()[TapeRecorder.DURATION]
        recorded_outputs = self._extract_recorded_output(recording)
        return Playback(playback_outputs, playback_duration, recorded_outputs, recorded_duration, recording)

    @staticmethod
    def _extract_recorded_output(recording):
        """
        :param recording:
        :type recording: playback.recording.Recording
        :return:
        :rtype:
        """
        all_output_keys = [key for key in recording.get_all_keys() if key.startswith('output:') and
                           not key.endswith('result')]
        return [Output(key, recording.get_data(key)) for key in all_output_keys]

    @staticmethod
    def _input_interception_key(alias, capture_args, static_function, *args, **kwargs):
        """
        Creates a key that uniquely represent this input invocation based on alias and invocation arguments
        :param alias: Input alias, used to uniquely identify the input function, hence the name should be unique across
        all relevant inputs this operation can reach. This should be renamed as it will render previous recording
        useless
        :type alias: str
        :param static_function: Is function static
        :type static_function: bool
        :param args: invocation args
        :type args: list
        :param kwargs: invocation kwargs
        :type kwargs: dict
        :param capture_args: If a list is given, it will annotate which arg indices and/or names should be
        captured as part of the intercepted key (invocation identification). If None, all args are captured
        :type capture_args: list of CapturedArg
        :return: Interception key
        :rtype: basestring
        """
        # Capture all args
        if capture_args is None:
            # Attempt to remove self
            args_for_keys = args[1:] if not static_function else args
            kwargs_for_key = kwargs
        # Set to not capture any args
        elif not capture_args:
            args_for_keys = []
            kwargs_for_key = {}
        else:
            args_for_keys = []
            kwargs_for_key = {}
            for captured_arg in capture_args:
                # First check if argument is in kwargs, these covers both cases where item is only defined is kwarg or
                # that it was passed as a kwarg even though it is a mandatory argument
                if captured_arg.name in kwargs:
                    kwargs_for_key[captured_arg.name] = kwargs[captured_arg.name]
                # If None it means this was captures as kwarg only, otherwise this is a mandatory argument that must
                # have an index
                elif captured_arg.position is not None:
                    args_for_keys.append(args[captured_arg.position])

        args_key = encode(args_for_keys, unpicklable=True)
        kwargs_key = encode(sorted(list(kwargs_for_key.items()), key=lambda k_v: k_v[0]), unpicklable=True)
        return u'input: {} args={}, kwargs={}'.format(alias, args_key, kwargs_key)

    @staticmethod
    def _output_interception_key(alias, invocation_number):
        """
        Creates a key that uniquely represents the output invocation based on alias in invocation count
        :param alias: output alias
        :type alias: str
        :param invocation_number: Current invocation number
        :type invocation_number: int
        :return: Interception key
        :rtype: basestring
        """
        return u'output: {} #{}'.format(alias, invocation_number)


CapturedArg = namedtuple('CapturedArg', 'position name')

Output = namedtuple('Output', 'key value')


class RecordingParameters(object):
    def __init__(self, sampling_rate=1.0, ignore_enforced_sampling=False,
                 skipped=False, copy_data_on_intercepion=False):
        """
        :param sampling_rate: Optional sampling rate (between 0 and 1) to applied on recording. Default is 1
        :type sampling_rate: float
        :param ignore_enforced_sampling: Whether to ignore enforce sample explicit calls
        :type ignore_enforced_sampling: bool
        :param skipped: This class should be skipped for recording
        :type skipped: bool
        :param copy_data_on_intercepion: copy each intercepted
               value while recording to prevent mutations, impacts performance
        :type copy_data_on_intercepion: bool
        """
        self.sampling_rate = sampling_rate
        self.ignore_enforced_sampling = ignore_enforced_sampling
        self.skipped = skipped
        self.copy_data_on_intercepion = copy_data_on_intercepion


class Playback(object):
    def __init__(self, playback_outputs, playback_duration, recorded_outputs, recorded_duration, original_recording):
        """
        :param playback_outputs: Outputs captured during playback
        :type playback_outputs: list of Output
        :param playback_duration: Duration it took to run the playback
        :type playback_duration: float
        :param recorded_outputs: Outputs captured during recording
        :type recorded_outputs: list of Output
        :param recorded_duration: Duration of the original recorded run
        :type recorded_duration: float
        :param original_recording: Recording that was used to run the playback
        :type original_recording: playback.recording.Recording
        """
        self.playback_outputs = playback_outputs
        self.playback_duration = playback_duration
        self.recorded_outputs = recorded_outputs
        self.recorded_duration = recorded_duration
        self.original_recording = original_recording
