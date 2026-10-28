import sys

collect_ignore = []

if sys.version_info[0] < 3:
    # Holds coroutine functions, which Python 2 cannot parse
    collect_ignore.append('test_tape_recorder_async.py')
    # Use types that Python 2 does not have
    collect_ignore.append('utils/test_legacy_jsonpickle.py')
    collect_ignore.append('recordings/test_sqlite_recording_legacy_jsonpickle.py')
    collect_ignore.append('test_cassettes/s3/test_s3_tape_cassette_legacy_jsonpickle.py')
