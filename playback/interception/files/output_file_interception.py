from playback.interception.files.file_interception import FileInterception
from playback.interception.output_interception import OutputInterceptionDataHandler


class OutputInterceptionFileDataHandler(OutputInterceptionDataHandler, FileInterception):
    """
    Intercept file arguments for playback
    """
    def prepare_output_for_recording(self, interception_key, args, kwargs):
        """
        Reads the intercepted file, encode its content as string and return it ready for recording
        :param interception_key: Input interception key
        :type interception_key: basestring
        :param args: Input invocation args
        :type args: tuple
        :param kwargs: Input invocation kwargs
        :type kwargs: dict
        :return: Input result in a form that should be saved in the recording
        :rtype: dict[str, str]
        """
        return self._intercept_file(args, kwargs)

    def restore_output_from_recording(self, recorded_data):
        """
        Create a file from the recorded content and place it in the given file path
        :param recorded_data: Recorded data provided by the prepare method
        :type recorded_data: Any
        :return: A file holder that holds the content that can be extracted to file
        :rtype: InterceptedOutputFileHolder
        """
        file_path, file_content = self._deserialize_file(recorded_data)
        return InterceptedOutputFileHolder(file_content, file_path)


class InterceptedOutputFileHolder(object):
    """
    Holds intercepted output file content
    """
    def __init__(self, file_content, output_file_path):
        """
        :param file_content: File content as string
        :type file_content: basestring
        :param output_file_path: The path of the file when it was output
        :type output_file_path: basestring
        """
        self.file_content = file_content
        self.output_file_path = output_file_path

    def to_file(self, file_path):
        """
        Writes the output file content to the given file path
        :param file_path: Path to write the content to
        :type file_path: basestring
        """
        with open(file_path, "wb") as binary_file:
            binary_file.write(self.file_content)
