import os
import logging
import tempfile
from tempfile import gettempdir
from io import open, BufferedReader

from playback.tape_cassettes.s3.s3_basic_facade import S3BasicFacade
from playback.tape_cassettes.s3.s3_tape_cassette import S3TapeCassette

logger = logging.getLogger(__name__)


class CachedS3BasicFacade(S3BasicFacade):
    DEFAULT_CACHE_PATH = os.path.join(gettempdir(), "recordings_cache")

    def __init__(self, bucket, region=None, cache_path=None, use_cache=True):
        super(CachedS3BasicFacade, self).__init__(bucket, region)
        self.use_cache = use_cache
        if cache_path is None:
            cache_path = self.DEFAULT_CACHE_PATH
        self.cache_path = cache_path
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)

        metadata_cache_path = os.path.join(self.cache_path, 'metadata')
        if not os.path.exists(metadata_cache_path):
            os.makedirs(metadata_cache_path)

    def get_string(self, key):
        """
        Get the string that associated with the given key from local cache. If fails for any reason
        fall back to fetching from S3 store.

        :param key: S3 key
        :type key: str
        :return: The string from S3
        :rtype: bytes
        """
        if not self.use_cache:
            logger.info("use_cache is False ignoring all caching mechanisms")
            return super(CachedS3BasicFacade, self).get_string(key)
        local_key_path = self._get_cache_path(key)
        found_locally = False
        if os.path.exists(local_key_path):
            with open(local_key_path, "rb") as fid:
                raw_data = fid.read()
                logger.info("File was found in local cache {}".format(local_key_path))
                found_locally = True
        else:
            logger.info(
                "File does not exist locally at {}, trying to fetch from S3".format(local_key_path)
            )
            raw_data = super(CachedS3BasicFacade, self).get_string(key)
        try:
            if not found_locally:
                self.cache_data_in_local_path(local_key_path, raw_data)
        # We want a cache fail proof mechanism hence we catch any exception report it and ignore the failure.
        except Exception as caching_error:   # pylint: disable=broad-except
            logger.info("Caching mechanism failed caching_error: {}".format(caching_error))
        return raw_data

    def get_buffered_reader(self, key):
        """
        Get the object that associated with the given key from local cache. If fails for any reason
        fall back to fetching from S3 store.
        """
        if not self.use_cache:
            logger.info("use_cache is False ignoring all caching mechanisms")
            return super(CachedS3BasicFacade, self).get_buffered_reader(key)
        local_key_path = self._get_cache_path(key)
        found_locally = False
        if os.path.exists(local_key_path):
            raw_data = open(local_key_path, "rb")
            logger.info("File was found in local cache {}".format(local_key_path))
            found_locally = True
        else:
            logger.info(
                "File does not exist locally at {}, trying to fetch from S3".format(local_key_path)
            )
            raw_data = super(CachedS3BasicFacade, self).get_buffered_reader(key)
        try:
            if not found_locally:
                self.cache_data_in_local_path(local_key_path, raw_data)
                # we need to open the file again, since the original stream has been consumed
                return open(local_key_path, "rb")
        # We want a cache fail proof mechanism hence we catch any exception report it and ignore the failure.
        except Exception as caching_error:   # pylint: disable=broad-except
            # at this point we don't know if the stream was consumed or not, so we need to get the data again
            raw_data = super(CachedS3BasicFacade, self).get_buffered_reader(key)
            logger.info("Caching mechanism failed caching_error: {}".format(caching_error))

        return raw_data

    @staticmethod
    def cache_data_in_local_path(local_full_key_path, raw_data):
        """
         Cache raw_data in local path local_full_key_path

        Uses atomic write (write to temp file, then rename) to prevent zero-size
        cache files when the write fails partway through. Reads streams into memory
        first to avoid compatibility issues with io.BufferedReader wrapping objects
        that don't fully implement RawIOBase (e.g. boto3 StreamingBody on PyPy3
        which lacks readinto()).

        :param local_full_key_path: path for local cache
        :type local_full_key_path: str
        :param raw_data: raw data to be cached
        :type raw_data: bytes | BufferedReader
        """
        data = raw_data.read() if hasattr(raw_data, 'read') else raw_data
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(local_full_key_path))
        try:
            with os.fdopen(tmp_fd, 'wb') as fid:
                fid.write(data)
            os.rename(tmp_path, local_full_key_path)
        except BaseException:
            os.unlink(tmp_path)
            raise
        logger.info("Caching in {} succeeded".format(local_full_key_path))

    def _get_cache_path(self, key):
        recording_id = os.path.basename(key)
        # metadata should be cached separately from the main recording, so we need to detect
        # it and prepare the cache path accordingly
        if 'metadata' in key:
            path_suffix = "metadata/{}".format(recording_id)
        else:
            path_suffix = recording_id

        return os.path.join(self.cache_path, path_suffix)


class CachedReadOnlyS3TapeCassette(S3TapeCassette):
    def __init__(  # pylint: disable=too-many-arguments
        self,
        bucket,
        key_prefix="",
        region=None,
        transient=False,
        read_only=True,
        infrequent_access_kb_threshold=None,
        sampling_calculator=None,
        local_path=None,
        use_cache=True,
    ):
        if read_only is not True:
            raise ValueError("CachedReadOnlyS3TapeCassette is designed to be in read_only state only")
        super(CachedReadOnlyS3TapeCassette, self).__init__(
            bucket, key_prefix, region, transient, read_only=read_only,
            infrequent_access_kb_threshold=infrequent_access_kb_threshold,
            sampling_calculator=sampling_calculator
        )
        self._s3_facade = CachedS3BasicFacade(self.bucket, region=region, cache_path=local_path, use_cache=use_cache)
