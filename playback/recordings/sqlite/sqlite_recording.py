import io
import os
import shutil
import tempfile
from contextlib import contextmanager, closing

from jsonpickle import encode, decode

from playback.exceptions import RecordingKeyError
from playback.recording import Recording


class SqliteRecording(Recording):
    """
    Recording implementation using SQLite as a storage backend. It's more memory-efficient than the in-memory
    implementation but equally easy to use.
    """
    @staticmethod
    def new(_id=None):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as db_file:
            return SqliteRecording(_id=_id, db_file_name=db_file.name)

    @staticmethod
    def from_buffered_reader(recording_id, buffered_reader, recording_metadata=None):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as db_file:
            shutil.copyfileobj(buffered_reader, db_file)

            return SqliteRecording(_id=recording_id, db_file_name=db_file.name, recording_metadata=recording_metadata)

    @contextmanager
    def as_buffered_reader(self):
        with io.open(self._db_file_name, "rb") as f:
            yield f, os.path.getsize(self._db_file_name)

    def __init__(self, db_file_name, _id=None, recording_metadata=None):
        super(SqliteRecording, self).__init__(_id=_id)

        self._db_file_name = db_file_name
        self.recording_metadata = recording_metadata or {}
        self.recording_metadata["_recording_type"] = "sqlite"

        with self._connection() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, value TEXT)")

    @contextmanager
    def _connection(self):
        # the sqlite3 module is imported locally only when needed because it can cause issues on some platforms
        import sqlite3  # pylint: disable=import-outside-toplevel
        # Set the isolation level to None to enable autocommit.
        # Wrapped in closing, because the sqlite3.connect context manager does not close the connection, which
        # leads to increased memory usage.
        with closing(sqlite3.connect(self._db_file_name, isolation_level=None)) as connection:
            connection.row_factory = sqlite3.Row
            yield connection

    def _set_data(self, key, value):
        with self._connection() as connection:
            connection.execute("INSERT OR REPLACE INTO data VALUES (?, ?)", (key, encode(value, unpicklable=True)))

    def get_data(self, key):
        return self.get_data_direct(key)

    def get_data_direct(self, key):
        with self._connection() as connection:
            data = connection.execute("SELECT value FROM data WHERE key=?", (key,))
            data = data.fetchone()
            if data is None:
                raise RecordingKeyError(u'Key \'{}\' not found in recording'.format(key).encode("utf-8"))

        return decode(data["value"])

    def get_all_keys(self):
        with self._connection() as connection:
            data = connection.execute("SELECT key FROM data")

            return [row["key"] for row in data]

    def _add_metadata(self, metadata):
        self.recording_metadata.update(metadata)

    def get_metadata(self):
        return self.recording_metadata
