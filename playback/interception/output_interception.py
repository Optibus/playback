from abc import ABCMeta, abstractmethod


class OutputInterceptionDataHandler(object):
    """
    A class that act as a pluggable hook that can be used during output interception when recording and playing the data
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def prepare_output_for_recording(self, interception_key, args, kwargs):
        """
        Prepare the input result that should be saved in the recording
        :param interception_key: Output interception key
        :type interception_key: basestring
        :param args: Output invocation args
        :type args: tuple
        :param kwargs: Output invocation kwargs
        :type kwargs: dict
        :return: Output result in a form that should be saved in the recording
        :rtype: Any
        """
        pass

    @abstractmethod
    def restore_output_from_recording(self, recorded_data):
        """
        Restore the actual input from the recording
        :param recorded_data: Recorded data provided by the prepare method
        :type recorded_data: Any
        :return: Object representing the output that was saved to the recording
        :rtype: Any
        """
        pass
