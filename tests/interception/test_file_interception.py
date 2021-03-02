import unittest
from random import randint
from tempfile import gettempdir
from datetime import datetime
import os
from contextlib import contextmanager

from playback.interception.files.file_interception import FileInterception
from playback.interception.files.input_file_interception import InputInterceptionFileDataHandler
from playback.interception.files.output_file_interception import OutputInterceptionFileDataHandler


def write_to_file(file_name, content):
    """
    Writes text to a file
    """
    with open(file_name, "w") as text_file:
        text_file.write(str(content))


def read_from_file(file_name):
    """
    Reads text from a file
    """
    with open(file_name, "rb") as text_file:
        return text_file.read()


@contextmanager
def temp_file():
    file_name = os.path.join(gettempdir(), '{}_{}tmp'.format(randint(0, 10000), datetime.now()))
    try:
        yield file_name
    finally:
        try:
            os.remove(file_name)
        except OSError:
            pass


@contextmanager
def temp_env(var_name, new_value):
    """
    Sets temporary and restores a given environment variable. The new value would be converted to string by str
    :param var_name: The name on the variable
    :type var_name: basestring
    :param new_value: The new value
    :type new_value: object # the would be converted using str(o)
    """
    variable_defined = var_name in os.environ
    if variable_defined:
        prev_value = os.getenv(var_name)
    os.environ[var_name] = str(new_value)
    try:
        yield
    finally:
        if variable_defined:
            os.environ[var_name] = prev_value
        else:
            del (os.environ[var_name])


class TestInputInterceptionFileDataHandler(unittest.TestCase):

    def test_prepare_and_restore(self):
        data_handler = InputInterceptionFileDataHandler(file_path_arg_index=0, file_path_arg_name='file_name')
        with temp_file() as file_name:
            write_to_file(file_name, 'some random meaningless content')
            prepared_input = data_handler.prepare_input_for_recording('key', '', [file_name], {})
            self.assertEqual(file_name, prepared_input['file_path'])

            with temp_file() as restore_file:
                data_handler.restore_input_from_recording(prepared_input, [restore_file], {})
                self.assertEqual(read_from_file(restore_file), read_from_file(file_name))

        with temp_file() as file_name:
            write_to_file(file_name, 'some random meaningless content')
            prepared_input = data_handler.prepare_input_for_recording('key', '', [], {'file_name': file_name})
            self.assertEqual(file_name, prepared_input['file_path'])

            with temp_file() as restore_file:
                data_handler.restore_input_from_recording(prepared_input, [], {'file_name': restore_file})
                self.assertEqual(read_from_file(restore_file), read_from_file(file_name))


class TestOutputInterceptionFileDataHandler(unittest.TestCase):

    def test_prepare_and_restore(self):
        data_handler = OutputInterceptionFileDataHandler(file_path_arg_index=0, file_path_arg_name='file_name')
        with temp_file() as file_name:
            write_to_file(file_name, 'some random meaningless content')
            prepared_input = data_handler.prepare_output_for_recording('key', [file_name], {})
            self.assertEqual(file_name, prepared_input['file_path'])

            with temp_file() as restore_file:
                file_holder = data_handler.restore_output_from_recording(prepared_input)
                file_holder.to_file(restore_file)
                self.assertEqual(read_from_file(restore_file), read_from_file(file_name))
                self.assertEqual(file_holder.file_content, read_from_file(file_name))
                self.assertEqual(file_name, file_holder.output_file_path)

        with temp_file() as file_name:
            write_to_file(file_name, 'some random meaningless content')
            prepared_input = data_handler.prepare_output_for_recording('key', [], {'file_name': file_name})
            self.assertEqual(file_name, prepared_input['file_path'])

            with temp_file() as restore_file:
                file_holder = data_handler.restore_output_from_recording(prepared_input)
                file_holder.to_file(restore_file)
                self.assertEqual(read_from_file(restore_file), read_from_file(file_name))
                self.assertEqual(file_holder.file_content, read_from_file(file_name))
                self.assertEqual(file_name, file_holder.output_file_path)

    def test_intercept_with_file_limit(self):
        data_handler = OutputInterceptionFileDataHandler(file_path_arg_index=0, file_path_arg_name='file_name',
                                                         intercepted_size_limit=1)
        with temp_file() as file_name:
            # Write 2MB file, while interception limit is 2MB
            write_to_file(file_name, 'a' * 2 * 1024 * 1024)
            prepared_input = data_handler.prepare_output_for_recording('key', [file_name], {})
            self.assertEqual(file_name, prepared_input['file_path'])
            self.assertEqual(FileInterception.ABOVE_LIMIT_CONTENT, prepared_input['file_content'])

            with temp_file() as restore_file:
                file_holder = data_handler.restore_output_from_recording(prepared_input)
                file_holder.to_file(restore_file)
                self.assertEqual(FileInterception.ABOVE_LIMIT_CONTENT, read_from_file(restore_file))
                self.assertEqual(FileInterception.ABOVE_LIMIT_CONTENT, file_holder.file_content)
                self.assertEqual(file_name, file_holder.output_file_path)

    def test_intercept_with_file_limit_with_env_variable(self):
        with temp_env('PLAYBACK_INTERCEPTED_FILE_SIZE_LIMIT', '1'):
            data_handler = OutputInterceptionFileDataHandler(file_path_arg_index=0, file_path_arg_name='file_name')
            with temp_file() as file_name:
                # Write 2MB file, while interception limit is 2MB
                write_to_file(file_name, 'a' * 2 * 1024 * 1024)
                prepared_input = data_handler.prepare_output_for_recording('key', [file_name], {})
                self.assertEqual(file_name, prepared_input['file_path'])
                self.assertEqual(FileInterception.ABOVE_LIMIT_CONTENT, prepared_input['file_content'])

                with temp_file() as restore_file:
                    file_holder = data_handler.restore_output_from_recording(prepared_input)
                    file_holder.to_file(restore_file)
                    self.assertEqual(FileInterception.ABOVE_LIMIT_CONTENT, read_from_file(restore_file))
                    self.assertEqual(FileInterception.ABOVE_LIMIT_CONTENT, file_holder.file_content)
                    self.assertEqual(file_name, file_holder.output_file_path)
