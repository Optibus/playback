from time import time


class Timed(object):
    """
    Tiny timing util that execution time of the scope it wraps
    """
    def __init__(self):
        self.duration = None
        self._start = None

    def __enter__(self):
        self._start = time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = time() - self._start
