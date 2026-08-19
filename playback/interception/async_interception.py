"""
The coroutine flavour of the interceptions declared on a TapeRecorder.

An intercepted 'async def' function returns a coroutine, so wrapping it in a plain function would record and play
back the coroutine object instead of the value it resolves to. The wrappers here await the intercepted function,
which makes the awaited value the recorded input/output and lets playback return it to the caller of the wrapper.

This module holds Python 3 only syntax and is imported lazily by playback.tape_recorder.
"""
# The wrappers here are part of the interception flow of TapeRecorder and drive its internals
# pylint: disable=protected-access
from playback.exceptions import RecordingKeyError


def async_input_interception(tape_recorder, func, params):
    """
    Wraps a coroutine function that acts as an input to the operation
    :param tape_recorder: Tape recorder that holds the recording this interception takes part in
    :type tape_recorder: playback.tape_recorder.TapeRecorder
    :param func: Coroutine function to intercept
    :type func: function
    :param params: Arguments the input interception was declared with
    :type params: playback.tape_recorder.InputInterceptionParams
    :return: Decorated coroutine function
    :rtype: function
    """

    async def decorated_function(*args, **kwargs):
        if not tape_recorder._should_intercept:
            return await func(*args, **kwargs)

        possible_keys, interception_key = tape_recorder._resolve_input_interception_keys(
            params.alias, params.alias_params_resolver, params.capture_args, params.fallback_aliases,
            params.static_function, args, kwargs)

        if tape_recorder.in_playback_mode:
            # Return recording of input invocation
            try:
                return tape_recorder._playback_recorded_interception(possible_keys, args, kwargs, params.data_handler)
            except RecordingKeyError:
                if params.run_intercepted_when_missing:
                    # Run the original method when content was missing in recording
                    return await func(*args, **kwargs)
                if params.value_when_missing:
                    return tape_recorder._resolve_value_when_missing(params.value_when_missing, args, kwargs)
                raise

        return await _await_func_and_record_interception(tape_recorder, func, interception_key, args, kwargs,
                                                         params.data_handler)

    return decorated_function


def async_output_interception(tape_recorder, func, params):
    """
    Wraps a coroutine function that acts as an output of the operation
    :param tape_recorder: Tape recorder that holds the recording this interception takes part in
    :type tape_recorder: playback.tape_recorder.TapeRecorder
    :param func: Coroutine function to intercept
    :type func: function
    :param params: Arguments the output interception was declared with
    :type params: playback.tape_recorder.OutputInterceptionParams
    :return: Decorated coroutine function
    :rtype: function
    """

    async def decorated_function(*args, **kwargs):
        if not tape_recorder._should_intercept:
            return await func(*args, **kwargs)

        interception_key = tape_recorder._record_intercepted_output(
            params.alias, params.data_handler, params.static_function, args, kwargs)

        # Record output may have failed and discarded current recording which would make should intercept false
        if interception_key is None:
            return await func(*args, **kwargs)

        if tape_recorder.in_playback_mode:
            # Return recording of input invocation
            try:
                return tape_recorder._playback_recorded_interception([interception_key], args, kwargs)
            except RecordingKeyError:
                if params.fail_on_no_recorded_result:
                    raise
                return params.default_result_when_not_recorded

        # Record the output result so it can be returned in playback mode
        return await _await_func_and_record_interception(tape_recorder, func, interception_key, args, kwargs)

    return decorated_function


async def _await_func_and_record_interception(tape_recorder, func, interception_key, args, kwargs, data_handler=None):
    """
    Awaits the given coroutine function and records the result/exception of the outcome
    :param tape_recorder: Tape recorder that holds the recording this interception takes part in
    :type tape_recorder: playback.tape_recorder.TapeRecorder
    :param func: Coroutine function to await
    :type func: function
    :param interception_key: Key to record the data under
    :type interception_key: Optional[str]
    :param args: invocation args
    :type args: tuple
    :param kwargs: invocation kwrags
    :type kwargs: dict
    :param data_handler: Optional data handler that prepare and restore the input data for and from the recording
    :type data_handler: playback.interception.input_interception.InputInterceptionDataHandler
    :return: Invocation result
    """
    # Mark that this invocation is under interception context so any inner interception will be skipped. The context
    # is held across the await, hence it must be scoped to the running task and not to the thread
    with tape_recorder._enter_interception_context():
        try:
            result = await func(*args, **kwargs)
        except Exception as ex:
            tape_recorder._record_interception_exception(interception_key, ex)
            raise

    tape_recorder._record_interception_result(interception_key, result, args, kwargs, data_handler)
    return result
