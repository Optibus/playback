import os
import logging
from tempfile import gettempdir
from six import PY2

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

    def get_string(self, key):
        """
        Get the string that associated with the given key from local cache. If fails for any reason
        fall back to fetching from S3 store.

        :param key: S3 key
        :type key: str
        :return: The string from S3
        :rtype: str
        """
        if not self.use_cache:
            logger.info("use_cache is False ignoring all caching mechanisms")
            return super(CachedS3BasicFacade, self).get_string(key)
        key_file_name = os.path.basename(key)
        local_key_path = os.path.join(self.cache_path, key_file_name)
        found_locally = False
        if os.path.exists(local_key_path):
            mode = "r" if PY2 else "rb"
            with open(local_key_path, mode) as fid:
                raw_data = fid.read()
                logger.info("File {} was found in local cache {}".format(key_file_name, local_key_path))
                found_locally = True
        else:
            logger.info(
                "File {} does not exist locally at {}, trying to fetch from S3".format(key_file_name,
                                                                                       local_key_path)
            )
            raw_data = super(CachedS3BasicFacade, self).get_string(key)
        try:
            if not found_locally:
                self.cache_data_in_local_path(local_key_path, raw_data)
        # We want a cache fail proof mechanism hence we catch any exception report it and ignore the failure.
        except Exception as caching_error:   # pylint: disable=broad-except
            logger.info("Caching mechanism failed caching_error: {}".format(caching_error))
        return raw_data

    @staticmethod
    def cache_data_in_local_path(local_full_key_path, raw_data):
        """
         Cache raw_data in local path local_full_key_path
        :param local_full_key_path: path for local cache
        :type local_full_key_path: str
        :param raw_data: raw data to be cached
        :type raw_data: str
        """
        mode = "w" if PY2 else "wb"
        with open(local_full_key_path, mode) as fid:
            fid.write(raw_data)
        logger.info("Caching in {} succeeded".format(local_full_key_path))


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
