# Flask http service example
This example creates two basic endpoints within the same flask instance that listens for POST invocations, 
these services are intercepted using the playback and each invocation is recorded and saved in a local file.
The `playback_runner.py` is demonstrating how one can replay the recorded operations and run comparison against current 
code base

# Running the example
You will need the relevant flask requirements, you can install the dev requirements which contains
the relevant flask (while being in the root project directory run `pip install -e .[dev]`)
To start the flask server run 
```python main.py``` in the flask example directory

Then you can run different post such as: 

http://localhost:5000/content_length
with example body:
```javascript
{
    "url": "https://www.google.com"
}
```

http://localhost:5000/content_first_chars
with example body:
```javascript
{
    "url": "https://www.google.com",
    "length": 10
}
```

# Inputs and outputs
Both operation share same base class and inputs and outputs flow, these functions
are intercepted with the proper decorators and will be saved in the recording
```python
class ContentBasedService(Resource):
    
    @tape_recorder.intercept_input('content_based_service.request_data')
    def _get_request_data(self):
        return request.json

    @tape_recorder.intercept_input('content_based_service.get_url_content')
    def _get_url_content(self, url):
        print("Fetching content from url: {}".format(url))
        return urllib.request.urlopen(url).read()

    @tape_recorder.intercept_output('content_based_service.persist_invocation')
    def _persist_invocation(self, url, result):
        # Mimic a persist operation for extra optional output, in this case we are not really doing anything with it but
        # it could be a data base call
        print("Persisting operation result - url: {}, result: {}".format(url, result))
```

# Operation class
We have two different operations:
* `ContentLengthEndpoint` - returns the content length of the fetched data from the given url
* `ContentFirstCharsEndpoint` - returns the first X characters of the fetched data from the given url
The `operation` decorators is considered as the entry point of the operation, this is where the interception starts
```python
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
```

# Running the playback studio flow
The `playback_runner.py` is a script that will run and compare all recorded operation against current code. You can run
it `python playback_runner.py` and see the comparison outputs of your invocations

It should look like this
```
Category ContentFirstCharsEndpoint
ContentFirstCharsEndpoint/25620aa87a9811eb9f40aae9fe8631bd: Equal - recorded: <!doctype , played_back: <!doctype 
ContentFirstCharsEndpoint/20d991cf7a9811eb9449aae9fe8631bd: Equal - recorded: <!DOCTYPE , played_back: <!DOCTYPE 

Category ContentLengthEndpoint
ContentLengthEndpoint/2825f4cc7a9811eb9322aae9fe8631bd: Equal - recorded: 15582, played_back: 15582
ContentLengthEndpoint/1c5a84597a9811eb89dcaae9fe8631bd: Equal - recorded: 511644, played_back: 511644


```

Then you can edit the code and delibiratly change it to return different result, for example
you can modify `ContentLengthEndpoint` and change its calculate length logic to return length + 1 which will create a differece between the recorded value and the produced output during playback. This will cause the playback output to look like this:
```
Category ContentFirstCharsEndpoint
ContentFirstCharsEndpoint/25620aa87a9811eb9f40aae9fe8631bd: Equal - recorded: <!doctype , played_back: <!doctype 
ContentFirstCharsEndpoint/20d991cf7a9811eb9449aae9fe8631bd: Equal - recorded: <!DOCTYPE , played_back: <!DOCTYPE 

Category ContentLengthEndpoint
ContentLengthEndpoint/2825f4cc7a9811eb9322aae9fe8631bd: Different - recorded: 15582, played_back: 15583
ContentLengthEndpoint/1c5a84597a9811eb89dcaae9fe8631bd: Different - recorded: 511644, played_back: 511645
```

This can demonstrate how a regression or a change of behaviour would look like.
