from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Tuple, Dict


class InputInterceptionDataHandler(object):
    """
    A class that act as a pluggable hook that can be used during input interception when recording and playing the data
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def prepare_input_for_recording(
        self,
        interception_key,  # type: str
        result,  # type: Any
        args,  # type: Tuple
        kwargs  # type: Dict
    ):  # type: (...) -> Any
        """
        Prepare the input result that should be saved in the recording
        :param interception_key: Input interception key
        :type interception_key: basestring
        :param result: Input function invocation result (the input)
        :type result: Any
        :param args: Input invocation args
        :type args: tuple
        :param kwargs: Input invocation kwargs
        :type kwargs: dict
        :return: Input result in a form that should be saved in the recording
        :rtype: Any
        """
        pass

    @abstractmethod
    def restore_input_from_recording(
        self,
        recorded_data,  # type: Any
        args,  # type: Tuple
        kwargs  # type: Dict
    ):  # type: (...) -> Any
        """
        Restore the actual input from the recording
        :param recorded_data: Recorded data provided by the prepare method
        :type recorded_data: Any
        :param args: Input invocation args
        :type args: tuple
        :param kwargs: Input invocation kwargs
        :type kwargs: dict
        :return: Input saved to the recording
        :rtype: Any
        """
        pass
