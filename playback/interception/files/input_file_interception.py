from playback.interception.files.file_interception import FileInterception
from playback.interception.input_interception import InputInterceptionDataHandler


class InputInterceptionFileDataHandler(InputInterceptionDataHandler, FileInterception):
    """
    Intercept file arguments for playback
    """
    def prepare_input_for_recording(self, interception_key, result, args, kwargs):
        """
        Reads the intercepted file, encode its content as string and return it ready for recording
        :param interception_key: Input interception key
        :type interception_key: basestring
        :param result: Input function invocation result (the input)
        :type result: Any
        :param args: Input invocation args
        :type args: tuple
        :param kwargs: Input invocation kwargs
        :type kwargs: dict
        :return: Input result in a form that should be saved in the recording
        :rtype: dict[str, str]
        """
        return self._intercept_file(args, kwargs)

    def restore_input_from_recording(self, recorded_data, args, kwargs):
        """
        Create a file from the recorded content and place it in the given file path
        :param recorded_data: Recorded data provided by the prepare method
        :type recorded_data: Any
        :param args: Input invocation args
        :type args: tuple
        :param kwargs: Input invocation kwargs
        :type kwargs: dict
        :return: Path of restored file
        :rtype: basestring
        """
        file_path = self._get_file_path(args, kwargs)
        with open(file_path, "wb") as binary_file:
            __, file_content = self._deserialize_file(recorded_data)
            binary_file.write(file_content)

        return file_path
