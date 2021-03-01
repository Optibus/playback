import os

import six
from flask import request
from flask_restplus import Resource

from playback.tape_cassettes.file_based.file_based_tape_cassette import FileBasedTapeCassette
from playback.tape_recorder import TapeRecorder

# For demonstration purpose, persist file in underline recordings dir
recordings_path = os.path.dirname(os.path.realpath(__file__)) + '/recordings'

tape_cassette = FileBasedTapeCassette(recordings_path)
tape_recorder = TapeRecorder(tape_cassette)
tape_recorder.enable_recording()


class ContentBasedService(Resource):
    @tape_recorder.intercept_input('content_based_service.request_data')
    def _get_request_data(self):
        return request.json

    @tape_recorder.intercept_input('content_based_service.get_url_content')
    def _get_url_content(self, url):
        print("Fetching content from url: {}".format(url))
        if six.PY3:
            import urllib.request
            return urllib.request.urlopen(url).read()
        else:
            import urllib2
            return urllib2.urlopen(url).read().decode("utf8")

    @tape_recorder.intercept_output('content_based_service.persist_invocation')
    def _persist_invocation(self, url, result):
        # Mimic a persist operation for extra optional output, in this case we are not really doing anything with it but
        # it could be a data base call
        print("Persisting operation result - url: {}, result: {}".format(url, result))


class ContentLengthEndpoint(ContentBasedService):

    @tape_recorder.operation()
    def post(self):
        # First input - read the data from the request
        request_data = self._get_request_data()
        url = request_data['url']
        # Second input - read the data from the request url. The url passed to the input is part of the intercepted key,
        # if the code would change and upon playback the url would be different due to code changes, the call to
        # _get_url_content will fail with missing key
        content = self._get_url_content(url)
        content_length = len(content)
        self._persist_invocation(url, content_length)
        return content_length


class ContentFirstCharsEndpoint(ContentBasedService):

    @tape_recorder.operation()
    def post(self):
        # First input - read the data from the request
        request_data = self._get_request_data()
        url = request_data['url']
        length = request_data['length']
        # Second input - read the data from the request url. The url passed to the input is part of the intercepted key,
        # if the code would change and upon playback the url would be different due to code changes, the call to
        # _get_url_content will fail with missing key
        content = self._get_url_content(url)
        content_chars = content[:length]
        self._persist_invocation(url, content_chars)
        return content_chars
