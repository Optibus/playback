import threading

try:
    from contextvars import ContextVar
except ImportError:  # pragma: no cover
    # Python 2 and Python 3.6 and below
    ContextVar = None


class InterceptionContext(object):
    """
    Holds whether an interception is currently in progress, in the narrowest scope the runtime provides.

    Where context variables are available the flag is context local, which gives each asyncio task its own value,
    so coroutines that are intercepted concurrently do not observe each other as an enclosing interception.
    Each thread holds its own value in both implementations.
    """

    def __init__(self):
        self._context_var = ContextVar('currently_in_interception', default=False) if ContextVar else None
        self._thread_locals = threading.local() if ContextVar is None else None

    @property
    def currently_in_interception(self):
        """
        :return: Is an interception currently in progress
        :rtype: bool
        """
        if self._context_var is not None:
            return self._context_var.get()

        return getattr(self._thread_locals, 'currently_in_interception', False)  # pragma: no cover

    @currently_in_interception.setter
    def currently_in_interception(self, value):
        """
        :param value: Is an interception currently in progress
        :type value: bool
        """
        if self._context_var is not None:
            self._context_var.set(value)
        else:  # pragma: no cover
            self._thread_locals.currently_in_interception = value
