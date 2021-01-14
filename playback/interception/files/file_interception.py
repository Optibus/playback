from __future__ import absolute_import
import logging
import os
import base64
import sys

from playback.utils.timing_utils import Timed

_logger = logging.getLogger(__name__)


class FileInterception(object):

    ABOVE_LIMIT_CONTENT = 'above interception limit'

    def __init__(self, file_path_arg_index, file_path_arg_name, intercepted_size_limit=None):
        """
        :param file_path_arg_index: The index inside arguments that points to the file path that needs to be intercepted
        :type file_path_arg_index: int
        :param file_path_arg_name: The name of the argument that points to the file path that needs to be intercepted
        :type file_path_arg_name: str
        :param intercepted_size_limit: Files that their size in MB is above this limit will not be intercepted
        :type intercepted_size_limit: float
        """
        self.file_path_arg_index = file_path_arg_index
        self.file_path_arg_name = file_path_arg_name
        self.intercepted_size_limit = self._calculate_max_intercepted_size_limit(intercepted_size_limit)

    @staticmethod
    def _mb_size(size):
        """
        :return: Size in MB
        :rtype: float
        """
        return size / (1024.0 * 1024.0)

    @staticmethod
    def _calculate_max_intercepted_size_limit(intercepted_size_limit):
        """
        :param intercepted_size_limit: Files that their size in MB is above this limit will not be intercepted
        :type intercepted_size_limit: float
        :return: Max intercepted file size
        :rtype: float
        """
        if intercepted_size_limit is not None:
            return intercepted_size_limit

        return int(float(os.getenv('PLAYBACK_INTERCEPTED_FILE_SIZE_LIMIT', 500)))

    def _get_file_path(self, args, kwargs):
        """
        :param args: Invocation args
        :type args: tuple
        :param kwargs: Invocation kwargs
        :type kwargs: dict
        :return: Intercepted file path from invocation parameters
        :rtype: basestring
        """
        file_path = kwargs.get(self.file_path_arg_name)
        if not file_path:
            file_path = args[self.file_path_arg_index]
        return file_path

    def _intercept_file(self, args, kwargs):
        """
        Record the file passed in the args/kwargs
        :param args: Invocation args
        :type args: tuple
        :param kwargs: Invocation kwargs
        :type kwargs: dict
        :return: Intercepted result in a form that should be saved in the recording
        :rtype: dict[str, str]
        """
        file_path = self._get_file_path(args, kwargs)

        if self._is_file_above_size_limit(file_path):
            return self._above_limit_result(file_path)

        _logger.info(u'Reading intercepted file ({})'.format(file_path))

        with Timed() as timed:
            with open(file_path, "r") as f:
                content = f.read()
            _logger.info(u'Done reading content size is {:.2f}MB ({})'.format(self._mb_size(len(content)), file_path))
            result = self._serialize_file(content, file_path)

        _logger.info(u'Done preparing file for recording with in {:.2f}s ({})'.format(timed.duration, file_path))
        return result

    def _is_file_above_size_limit(self, file_path):
        """
        Checks if intercepted file is above the configured size limit for interception
        :param file_path: Path
        :type file_path: basestring
        :return: Whether the file size is above interception limit
        :rtype: bool
        """
        if self.intercepted_size_limit is not None:
            file_size_in_mb = self._mb_size(os.path.getsize(file_path))
            if file_size_in_mb > self.intercepted_size_limit:
                _logger.info(u'Intercepted file is {:.2f}MB which is above interception limit of {:.2f}MB, '
                             u'ignoring content'.format(file_size_in_mb, self.intercepted_size_limit, file_path))
                return True
        return False

    @staticmethod
    def _above_limit_result(file_path):
        """
        Returns file above limit result (removing the content)
        :param file_path: Path of file
        :type file_path: basestring
        :return: File above limit result (removing the content)
        :rtype: dict[str, str]
        """
        return {
            'file_path': file_path,
            'file_content': FileInterception.ABOVE_LIMIT_CONTENT
        }

    @staticmethod
    def _serialize_file(content, file_path):
        """
        Serialize the file content prepared for recording
        :param content: File content
        :type content: basestring
        :param file_path: Path of file
        :type file_path: basestring
        :return: Serialized form of file
        :rtype: dict[str, str]
        """

        if sys.version_info.major == 2:
            encoded_content=content.encode('base64')
        else:
            encoded_content=base64.b64encode(content)

        return {
            'file_path': file_path,
            'file_content': encoded_content
        }

    @staticmethod
    def _deserialize_file(serialized_file):
        """
        Deserialize the content into file path and file content
        :param serialized_file: Serialized form of file
        :type serialized_file: dict[str, str]
        :return: File path and file content
        :rtype: str, str
        """
        file_content = serialized_file['file_content']

        if file_content != FileInterception.ABOVE_LIMIT_CONTENT:
            if sys.version_info.major == 2:
                file_content=file_content.decode('base64')
            else:
                file_content=base64.b64decode(file_content)

        return serialized_file['file_path'], file_content
