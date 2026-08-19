import sys

collect_ignore = []

if sys.version_info[0] < 3:
    # Holds coroutine functions, which Python 2 cannot parse
    collect_ignore.append('test_tape_recorder_async.py')
