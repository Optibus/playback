class TapeRecorderException(Exception):
    """
    Base exception for tape recorder
    """
    pass


class InputInterceptionKeyCreationError(TapeRecorderException):
    """
    Exception while creating input interception key
    """
    pass


class RecordingKeyError(TapeRecorderException):
    """
    Exception when key is not found in a recording
    """
    pass


class OperationExceptionDuringPlayback(TapeRecorderException):
    """
    Exception was caught when running the function during a playback
    """
    pass


class NoSuchRecording(TapeRecorderException):
    """
    Recording with given key is not found
    """
    def __init__(self, recording_id):
        """
        :param recording_id: Missing recording id
        :type recording_id: basestring
        """
        super(NoSuchRecording, self).__init__(recording_id.encode('utf-8'))
