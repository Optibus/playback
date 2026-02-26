import os
import shutil
import tempfile
from io import BufferedReader, BytesIO
from zlib import compress

import six
from jsonpickle import encode
from mock import patch

from playback.tape_cassettes.cached import cached_facade
from playback.tape_cassettes.cached.cached_facade import CachedReadOnlyS3TapeCassette, CachedS3BasicFacade
from playback.tape_cassettes.s3.s3_basic_facade import S3BasicFacade
import unittest


class TestReadOnlyCachedS3TapeCassette(unittest.TestCase):

    use_cache = True
    CACHE_PATH = "use_temp"
    first_run = False
    fail_on_caching = False

    def setUp(self):
        self.resource_files_path = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "cached_recordings")
        recording_file_name = "some_random_recording_id"
        # Use Python version specific resource file
        resource_file_name = recording_file_name + ("" if six.PY2 else "_py3")
        recording_path = "operation_name/partition_date"
        self.recording_id = os.path.join(recording_path, recording_file_name)
        self.resource_file_location = os.path.join(self.resource_files_path, resource_file_name)
        self.tmp_path = tempfile.mkdtemp()
        CachedS3BasicFacade.DEFAULT_CACHE_PATH = os.path.join(self.tmp_path, "default_cache", "recordings_cache")
        self.s3_files_location = os.path.join(self.tmp_path, "s3")
        os.makedirs(os.path.join(self.s3_files_location, recording_path))

        self.s3_file_path = os.path.join(self.s3_files_location, self.recording_id)

        self.cache_path = None if self.CACHE_PATH == "default" else os.path.join(self.tmp_path, "cache",
                                                                                 "recordings_cache")
        if self.cache_path:
            self.cache_file_path = os.path.join(self.cache_path, recording_file_name)
        else:
            self.cache_file_path = os.path.join(CachedS3BasicFacade.DEFAULT_CACHE_PATH, recording_file_name)

        # Make sure initial directory state is as needed for default dir or not and or first run or not
        file_path = os.path.dirname(self.cache_file_path)
        if not self.first_run:
            os.makedirs(file_path)
        else:
            if os.path.exists(file_path):
                shutil.rmtree(file_path)

        self.tape_cassette = CachedReadOnlyS3TapeCassette(
            bucket="some_bucket",
            key_prefix="test",
            local_path=self.cache_path,
            use_cache=self.use_cache,
        )

    def tearDown(self):
        """Tear down the temporary directory after the test."""
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def create_mocked_method(self):
        def mocked_method(*args, **kwargs):
            # Use the same file mode as the cached facade for consistency
            mode = "r" if six.PY2 else "rb"
            with open(self.s3_file_path, mode) as fid:
                return fid.read()

        return mocked_method

    def get_string_and_validate_reading(self):
        with patch.object(S3BasicFacade, "get_string", new=self.create_mocked_method()):
            recording = self.tape_cassette._s3_facade.get_string(self.recording_id)
        # Always get raw data
        if six.PY2:
            self.assertEqual(recording, "Some raw data")
        else:
            self.assertEqual(recording, b"Some raw data")

    def get_buffered_reader_and_validate_reading(self):
        def get_buffered_reader_mock(*_args, **_kwargs):
            return BufferedReader(BytesIO(b"Some raw data"))
        with patch.object(S3BasicFacade, "get_buffered_reader", new=get_buffered_reader_mock):
            recording = self.tape_cassette._s3_facade.get_buffered_reader(self.recording_id)

        raw_data = recording.read()

        if six.PY2:
            self.assertEqual(raw_data, "Some raw data")
        else:
            self.assertEqual(raw_data, b"Some raw data")


class TestCachedS3TapeCassetteUseCacheTrue(TestReadOnlyCachedS3TapeCassette):
    use_cache = True

    def _test_caching(self):
        self.get_string_and_validate_reading()
        self.get_buffered_reader_and_validate_reading()

        # Always cache in full path location
        self.assertTrue(os.path.exists(self.cache_file_path))

    def test_get_from_mocked_s3_and_cache(self):
        # No cache, fetch from (mocked) S3 and cache
        shutil.copyfile(self.resource_file_location, self.s3_file_path)

        self._test_caching()
        self.assertTrue(os.path.exists(self.s3_file_path))

    def test_get_from_cache_only(self):
        # File no longer in S3 (mocked directory is empty) but cache exists in full path only
        shutil.copyfile(self.resource_file_location, self.cache_file_path)

        self._test_caching()
        self.assertFalse(os.path.exists(self.s3_file_path))


class TestCachedS3TapeCassetteWithUseCacheFalse(TestReadOnlyCachedS3TapeCassette):
    use_cache = False

    def _test_reading(self):
        self.get_string_and_validate_reading()
        self.get_buffered_reader_and_validate_reading()

        # use_cache is False hence
        # Do not cache in full path location
        self.assertFalse(os.path.exists(self.cache_file_path))

    def test_get_from_mocked_s3_and_do_not_cache(self):
        # No cache, fetch from (mocked) S3 and do not cache
        shutil.copyfile(self.resource_file_location, self.s3_file_path)

        self._test_reading()

    def test_get_from_full_cache_only(self):
        # File no longer in S3 (mocked directory is empty) cache exists but we do not look for it there
        shutil.copyfile(self.resource_file_location, self.cache_file_path)

        # Since use_cache is false we will try to read from s3 and fail
        try:
            self._test_reading()
            self.fail("IOError should raise")
        except IOError:
            pass


class TestCachedS3TapeCassetteWithDefaultCachePath(TestReadOnlyCachedS3TapeCassette):

    CACHE_PATH = "default"

    def test_default_cache_path(self):
        self.assertTrue(os.path.exists(self.tape_cassette._s3_facade.cache_path))
        self.assertEqual(self.tape_cassette._s3_facade.cache_path, CachedS3BasicFacade.DEFAULT_CACHE_PATH)


class TestCachedS3TapeCassetteFirstRunCreateDir(TestReadOnlyCachedS3TapeCassette):

    first_run = True

    def test_first_run_creates_directories(self):
        self.assertTrue(os.path.exists(self.tape_cassette._s3_facade.cache_path))


class TestCachedS3TapeCassetteFirstRunCreateDirWithDefaultCacheDir(TestReadOnlyCachedS3TapeCassette):

    first_run = True
    CACHE_PATH = "default"

    def test_first_run_creates_default_directories(self):
        self.assertTrue(os.path.exists(self.tape_cassette._s3_facade.cache_path))
        self.assertEqual(self.tape_cassette._s3_facade.cache_path, CachedS3BasicFacade.DEFAULT_CACHE_PATH)


class TestCachedS3TapeCassetteFailsOnCaching(TestReadOnlyCachedS3TapeCassette):

    fail_on_caching = True

    def test_cache_is_failing(self):

        error_message = "Caching failing for some reason"

        def mocked_fail(msg, *args, **kwargs):
            if ("Caching in" in msg and "succeeded" in msg) or "Caching mechanism failed caching_error" in msg:
                raise ValueError(error_message)

        shutil.copyfile(self.resource_file_location, self.s3_file_path)
        with patch.object(cached_facade.logger, 'info', new=mocked_fail):
            try:
                self.get_string_and_validate_reading()
                self.fail("A cached error should be raised")
            except ValueError as e:
                self.assertEqual(str(e), error_message)

            os.remove(self.cache_file_path)

            try:
                self.get_buffered_reader_and_validate_reading()
                self.fail("A cached error should be raised")
            except ValueError as e:
                self.assertEqual(str(e), error_message)


class TestCacheDataAtomicWrite(TestReadOnlyCachedS3TapeCassette):
    """Test that cache_data_in_local_path uses atomic writes and handles non-BufferedReader streams."""

    def test_cache_from_bytes(self):
        """Test caching raw bytes data."""
        data = b"Some raw data"
        CachedS3BasicFacade.cache_data_in_local_path(self.cache_file_path, data)
        with open(self.cache_file_path, "rb") as fid:
            self.assertEqual(fid.read(), data)

    def test_cache_from_buffered_reader(self):
        """Test caching from a BufferedReader."""
        data = b"Some raw data"
        reader = BufferedReader(BytesIO(data))
        CachedS3BasicFacade.cache_data_in_local_path(self.cache_file_path, reader)
        with open(self.cache_file_path, "rb") as fid:
            self.assertEqual(fid.read(), data)

    def test_cache_from_stream_without_readinto(self):
        """Test caching from a stream that has read() but not readinto() (e.g. boto3 StreamingBody on PyPy3)."""
        class FakeStreamingBody(object):
            def __init__(self, content):
                self._content = content
                self._pos = 0

            def read(self, amt=None):
                if amt is None:
                    data = self._content[self._pos:]
                    self._pos = len(self._content)
                else:
                    data = self._content[self._pos:self._pos + amt]
                    self._pos += len(data)
                return data

            def readable(self):
                return True

        data = b"Some raw data from streaming body"
        stream = FakeStreamingBody(data)
        self.assertFalse(hasattr(stream, 'readinto'))

        CachedS3BasicFacade.cache_data_in_local_path(self.cache_file_path, stream)
        with open(self.cache_file_path, "rb") as fid:
            self.assertEqual(fid.read(), data)

    def test_no_zero_size_file_on_write_failure(self):
        """Test that a failed write does not leave a zero-size file."""
        class FailingReader(object):
            def read(self, amt=None):
                raise IOError("simulated read failure")

        try:
            CachedS3BasicFacade.cache_data_in_local_path(self.cache_file_path, FailingReader())
        except IOError:
            pass
        self.assertFalse(os.path.exists(self.cache_file_path))


class TestCreateTapeCassetteNotInReadOnlyState(unittest.TestCase):
    def test_create_tape_cassette_not_in_read_only_state(self):
        try:
            CachedReadOnlyS3TapeCassette(
                bucket="some_bucket",
                key_prefix="test",
                read_only=False)
            self.fail("CachedReadOnlyS3TapeCassette must be created in a read only state")
        except ValueError as e:
            self.assertEqual(str(e), "CachedReadOnlyS3TapeCassette is designed to be in read_only state only")


class TestCachedS3TapeCassette(TestReadOnlyCachedS3TapeCassette):
    """
    Test class for CachedS3TapeCassette
    """

    def test_cached_s3_tape_cassette(self):
        cassette = CachedReadOnlyS3TapeCassette(
            bucket="some_bucket",
            key_prefix="test",
            local_path=self.cache_path,
            use_cache=True
        )

        obj = dict(a="a", b=1)
        encoded_full = encode(obj, unpicklable=True)

        if six.PY3 and isinstance(encoded_full, str):
            compressed_str = compress(encoded_full.encode('utf-8'))
        else:
            compressed_str = compress(encoded_full)

        def get_string_mock(*_args, **_kwargs):
            return b'{"foo": "bar"}'

        def get_buffered_reader_mock(*_args, **_kwargs):
            return BufferedReader(BytesIO(compressed_str))

        with patch.object(S3BasicFacade, "get_string", new=get_string_mock):
            with patch.object(S3BasicFacade, "get_buffered_reader", new=get_buffered_reader_mock):
                cassette.get_recording("some_random_recording_id")

        recording = cassette.get_recording("some_random_recording_id")

        self.assertEqual(obj, recording.recording_data)
        self.assertLessEqual({
            "foo": "bar",
        }.items(), recording.get_metadata().items())
