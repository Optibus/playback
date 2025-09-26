from typing import Type

from playback.recording import Recording
from playback.recordings.memory.memory_recording import MemoryRecording
from playback.recordings.sqlite.sqlite_recording import SqliteRecording


def get_recording_class(metadata):
    # type: (dict) -> Type[Recording]
    """
    Returns the appropriate recording class based on the metadata provided.
    """
    recording_type = metadata.get('_recording_type', 'memory') or 'memory'

    if recording_type == "sqlite":
        recording_class = SqliteRecording
    elif recording_type == "memory":
        recording_class = MemoryRecording
    else:
        raise Exception('Unsupported recording type {}'.format(recording_type))

    return recording_class
