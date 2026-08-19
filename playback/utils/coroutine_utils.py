try:
    from inspect import isasyncgen, iscoroutine, iscoroutinefunction
except ImportError:
    # Python 2 has no coroutines
    isasyncgen = None
    iscoroutine = None
    iscoroutinefunction = None


def is_coroutine_function(func):
    """
    Checks if the parameter is a function declared with 'async def'. A function that wraps such a function without
    being declared with 'async def' itself is not one, even when it returns the coroutine of the function it wraps
    :param func: Value to check
    :type func: Any
    :return: Is the value a coroutine function
    :rtype: bool
    """
    return iscoroutinefunction is not None and iscoroutinefunction(func)


def is_unresolved_async_result(value):
    """
    Checks if the parameter is a coroutine or an async generator, whose value is only produced once an event loop
    drives it to completion
    :param value: Value to check
    :type value: Any
    :return: Does the value still have to be driven by an event loop to produce a value
    :rtype: bool
    """
    if iscoroutine is None:
        return False

    return iscoroutine(value) or isasyncgen(value)
