from flask import Flask
from flask_restplus import Api

from examples.flask.playback_context import init_recording_mode
from examples.flask.web_services import ContentLengthEndpoint, ContentFirstCharsEndpoint

app = Flask(__name__)
api = Api(app)
api.add_resource(ContentLengthEndpoint, '/content_length')
api.add_resource(ContentFirstCharsEndpoint, '/content_first_chars')


if __name__ == '__main__':
    init_recording_mode()
    app.run(host='0.0.0.0', port=5000, debug=True)
