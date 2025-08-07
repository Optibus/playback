import os
import shutil
import tempfile
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


class TestCachedS3TapeCassetteUseCacheTrue(TestReadOnlyCachedS3TapeCassette):
    use_cache = True

    def _test_caching(self):
        self.get_string_and_validate_reading()

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
            compressed_str = compress(bytes(encoded_full.encode('utf-8')))
        else:
            compressed_str = compress(encoded_full)

        with patch.object(S3BasicFacade, "get_string", return_value=compressed_str):
            cassette.get_recording("some_random_recording_id")

        self.assertEqual(obj, cassette.get_recording("some_random_recording_id").recording_data)
