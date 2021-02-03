# playback [![CircleCI](https://circleci.com/gh/Optibus/playback.svg?style=shield)](https://circleci.com/gh/Optibus/playback) [![codecov](https://codecov.io/gh/Optibus/playback/branch/main/graph/badge.svg?token=CA8OMGPFQT)](https://codecov.io/gh/Optibus/playback)
A python decorator based framework that lets you "record" service operations when they are being executed,
intercepts all inputs and outputs which can later be used to replay exactly the same operation in a controlled isolated
sandbox as well as compare the output of the recorded operation vs the replayed operation.

Main usages
* Run production traffic on new code version of the service to detect regressions
* Debug production issues locally
* Access to many "Real data" scenarios to test/validate new features/behaviours

## Background
The motivation for this framework was to be able to test new code changes on actual data in production when the
alternative of canary deployment is not a viable option.
A few examples when this might happen:
* Detecting a regression is based on intimate knowledge of the service output
* The service amount of possible input permutations is large while the number of users per permutation is low which
  doesn't create a large enough statistical sample to rely on in production in order to detect regression early enough
  to rollback

On top of that, the ability to have the developer check and get accurate comparison of his code vs production while
being able to debug it, increase the productivity as you detect issues right away while developing
and quality of released code significantly as you are covering many edge cases that are hard to predict in tests

## Features
* Create a standalone "recording" of each intercepted operation with all the relevant inputs and output and save it
  to aws s3
* Replay a recorded operation via code execution anywhere
* Run an extensive comparison of recorded vs replayed

# Installation
`pip install playback-studio`

# Usage and examples - Interception and replay
## Intercepting an Operation
In order to intercept an operation you need to explicitly declare the recorded operation entry point by decorating it with
the `TapeRecorder.operation` decorator and explicitly declare what inputs and outputs needs to be intercepted by using
the `TapeRecorder.intercept_input` and `TapeRecorder.intercept_output` decorators as demonstrated below
```python
from flask import request
tape_cassette = S3TapeCassette('production-recordings', region='us-east-1', read_only=False)
tape_recorder = TapeRecorder(tape_cassette)
tape_recorder.enabled_recording()


class ServiceOperation(object):

    ...

    @tape_recorder.operation()
    def execute(self):
        """
        Executes the operation and return the key of where the result is stored
        """
        data = self.get_request_data()
        result = self.do_something_with_input(data)
        storage_key = self.store_result(result)
        return storage_key

    @tape_recorder.intercept_input(alias='service_operation.get_request_data')
    def get_request_data(self):
        """
        Reads the required input for the operation
        """
        # Get request data from flask
        return request.data

    @tape_recorder.intercept_output(alias='service_operation.store_result')
    def store_result(self, result):
        """
        Stores the operation result and return the key that can be used to fetch the result
        """
        result_key = self.put_result_in_mongo(result)
        return result_key
```
## Replaying an intercepted operation
In order to replay an operation you need the specific recording id, typically you would add this information to your
logs output. Later we will demonstrate how to look for recording ids using search filters `Equalizre` and the
`PlaybackStudio`
```python
tape_cassette = S3TapeCassette('production-recordings', region='us-east-1')
tape_recorder = TapeRecorder(tape_cassette)

def playback_function(recording):
    """
    Given a recording, starts the execution of the recorded operation
    """
    operation_class = recording.get_metadata()[TapeRecorder.OPERATION_CLASS]
    return operation_class().execute()

# Will replay recorded operation, injecting and capturing needed data in all of the intercepted inputs and outputs
tape_recorder.play(recording_id, playback_function)
```

# Framework Classes - Recording and Replaying
## `TapeRecorder` class
This class is used to "record" operation and "replay" (rerun) recorded operation on any code version.
The recording is done by placing different decorators that intercepts the operation, its inputs and outputs by using
decorators.
### `operation` decorator
```python
def operation(self, metadata_extractor=None)
```
Decorates the operation entry point, every decorated input and output that is being executed within this scope is being
intercepted and recorded or replayed, depending on whether the current context is recording or playback

* `metadata_extractor` - an optional function that can be used to add
metadata to the recording. The metadata can be used as a search filter when fetching recordings, hence it can be used
to add properties specific to the operation received parameters that make sense to filter by when you wish to replay
the operation.

### `intercept_input` decorator
```python
def intercept_input(self, alias, alias_params_resolver=None, data_handler=None, capture_args=None)
```
Decorates a function that acts as an input to the operation, the result of the function is the recorded input and the
passed arguments and alias combined are used as the key that uniquely identify the input. Upon playback, an invocation to
the intercepted method will fetch the input from the recording by combining the passed arguments and alias as the
lookup key. If no recorded value is found a `RecordingKeyError` will be raised.

* `alias` - Input alias, used to uniquely identify the input function, hence the name should be unique across all
  relevant inputs this operation can reach. This should be renamed as it will render previous recording useless
* `alias_params_resolver` - Optional function that resolve parameters inside alias if such are given, this is useful when
  you have the same input method invoked many times with the same arguments on different class instances
* `data_handler` - Optional data handler that prepare and restore the input data for and from the recording when default
  pickle serialization is not enough. This needs to be an implementation of `InputInterceptionDataHandler` class
* `capture_args` - If a list is given, it will annotate which arg indices and/or names should be captured as part of
  the intercepted key (invocation identification). If None, all args are captured

When intercepting a static method, `static_intercept_input` should be used

### `intercept_output` decorator
```python
def intercept_output(self, alias, data_handler=None, fail_on_no_recorded_result=True)
```
Decorates a function that acts as an output of the operation, the parameters passed to the function are recorded as
the output and the return value is recorded as well. The alias combined with invocation number are used as the key that
uniquely identify this output. Upon playback, an invocation to the intercepted method will construct the same
identification key and capture the outputs again (which can later be used to compare against the recorded output), and
the recorded return value will be returned.

* `alias` - Output alias, used to uniquely identify the input function, hence the name should be unique across all
  relevant inputs this operation can reach. This should be renamed as it will render previous recording useless
* `data_handler` - Optional data handler that prepare and restore the output data for and from the recording when
  default pickle serialization is not enough. This needs to be an implementation of `OutputInterceptionDataHandler` class
* `fail_on_no_recorded_result` - Whether to fail if there is no recording of a result or return None.
  Setting this to False is useful when there are already pre existing recordings and this is a new output interception
  while we want to be able to playback old recordings and the return value of the output is not actually used.
  Defaults to True

The return value of the operation is always intercepted as an output implicitly using
`TapeRecorder.OPERATION_OUTPUT_ALIAS` as the output alias

When intercepting a static method, `static_intercept_output` should be used

## `TapeCassette` class
An abstract class that acts as a storage driver for TapeRecorder to store and fetch recordings, the class have 3 main
methods that needs to be implemented
```python
def get_recording(self, recording_id)
```
Get recording stored under the given id

```python
def create_new_recording(self, category)
 ```
Creates a new recording object that is used by the tape recorded
* `category` - Specifies under which category to create the recording, represent the operation type

```python
def iter_recording_ids(self, category, start_date=None, end_date=None, metadata=None, limit=None)
```
Creates an iterator of recording ids matching the given search parameters
* `category` - Specifies which category to look for recordings
* `start_date` - Optional earliest date of when recordings were captured
* `end_date` - Optional latest date of when recordings were captured
* `metadata` - Optional dictionary to filter by captured metadata
* `limit` - Optional limit on how many matching recording ids to fetch

The framework comes with two built-in implementations:
* `InMemoryTapeCassette` - Saves recording in a dictionary, its main usage is for tests
* `S3TapeCassette` - Saves recording in AWS S3 bucket
### `S3TapeCassette` class
```python
# Instantiate a the cassette connected to bucket 'production-recordings'
# under region 'us-east-1' in read/write mode
tape_cassette = S3TapeCassette('production-recordings', region='us-east-1', read_only=False)
```
Instantiating this class relies on being able to connect to AWS S3 from current terminal/process and have read/write
access to the given bucket (for playback only read access is needed)
```python
def __init__(self, bucket, key_prefix='', region=None, transient=False, read_only=True,
             infrequent_access_kb_threshold=None, sampling_calculator=None)
```
* `bucket` - S3 Bucket name
* `key_prefix` - Each recording is saved under two keys, one containing full data and the other just the for fast lookup
  and filtering of recordings. The key structure used for recording is
  'tape_recorder_recordings/{key_prefix}<full/metadata>/{id}', this gives the option to add a prefix to the key
* `region` - This value is propagated to the underline boto client
* `transient` - Is this a transient cassette, all recording under given prefix will be deleted when closed
  (only if not read only). This is useful for testing purposes, clean up after tests
* `read_only` - If True, this cassette can only be used to fetch recordings and not to create new ones,
  any write operations will raise an assertion.
* `infrequent_access_kb_threshold` - Threshold in KB that above it object will be saved in STANDARD_IA
  (infrequent access storage class), None means never (default)
* `sampling_calculator` - Optional sampling ratio calculator function, before saving the recording this
  function will be triggered with (category, recording_size, recording),
  and the function should return a number between 0 and 1 which specify its sampling rate

# Usage and examples - Comparing replayed vs recorded operation
## Using the Equalizer
In order to run a comparison we can use the `Equalizer` class and provide it with relevant playable recordings,
in this example we will look for 5 recordings from last week using the `find_matching_recording_ids` function.
The `Equalizer` relies on:
* `playback_function` to replay the recorded operation.
* `result_extractor` to extract the result that we want to compare from the captured outputs.
* `comparator` to compare the extracted result.
```python
# Creates an iterator over relevant recordings which are ready to be played
lookup_properties = RecordingLookupProperties(start_date=datetime.utcnow() - timedelta(days=7),
                                              limit=5)
recording_ids = find_matching_recording_ids(tape_recorder,
                                            ServiceOperation.__name__,
                                            lookup_properties)


def result_extractor(outputs):
    """
    Given recording or playback outputs, find the relevant output which is the result that
    needs to be compared
    """
    # Find the relevant captured output
    output = next(o for o in outputs if 'service_operation.store_result' in o.key)
    # Return the captured first arg as the result that needs to be compared
    return output.value['args'][0]


def comparator(recorded_result, replay_result):
    """
    Compare the operation captured output result
    """
    if recorded_result == replay_result:
        return ComparatorResult(EqualityStatus.Equal, "Value is {}".format(recorded_result))
    return ComparatorResult(EqualityStatus.Different,
                            "{recorded_result} != {replay_result}".format(
                                recorded_result=recorded_result, replay_result=replay_result))


def player(recording_id):
    return tape_recorder.play(recording_id, playback_function)


# Run comparison and output comparison result using the Equalizer
equalizer = Equalizer(recording_ids, player, result_extractor, comparator)

for comparison_result in equalizer.run_comparison():
    print('Comparison result {recording_id} is: {result}'.format(
        recording_id=comparison_result.playback.original_recording.id,
        result=comparison_result.comparator_status))
```

# Framework Classes - Comparing replayed vs recorded
## `Equalizer` class
The `Equalizer` is used to replay multiple recordings of a single operation and conduct a comparison between the
recorded results (outputs) vs the replayed results. Underline it uses the `TapeRecorder` in order to replay the
operations and the `TapeCassette` to look for and fetch relevant recordings

```python
def __init__(self, recording_ids, player, result_extractor, comparator,
             comparison_data_extractor=None, compare_execution_config=None)
```
* `recording_ids` - Iterator of recording ids to play and compare the results.
* `player` - A function that plays a recording given an id.
* `result_extractor` - A function used to extract the results that needs to be compared from the recording and playback
  outputs.
* `comparator` - A function used to create the comparison result by comparing the recorded vs replayed result.
* `comparison_data_extractor` - A function used to extract optional data from the recording that will be passed to the
  comparator.
* `compare_execution_config` -  Configuration specific to the comparison execution flow

For more context, you acn look at the [basic service operation](examples/basic_service_operation.py/) example

## Usage and examples - Comparing recorded vs replayed multiple operations in one flow
When a code change may affect multiple operations or when you want to have a general regression job running you can use
the `PlaybackStudio` and `EqualizerTuner` to run multiple operation together and aggregate the results.
Moreover the `EqualizerTuner` can be used as a factory to create the relevant plugin functions required to setup an
`Equalizer` to run a comparison of a specific operation

```python
# Will run 10 playbacks per category
lookup_properties = RecordingLookupProperties(start_date, limit=10)
catagories = ['ServiceOperationA', 'ServiceOperationB']
equalizer_tuner = MyEqualizerTuner()

studio = PlaybackStudio(categories, equalizer_tuner, tape_recorder, lookup_properties)
categories_comparison = studio.play()
```
Implementing an `EqualizerTuner`
```python
class MyEqualizerTuner(EqualizerTuner):
    def create_category_tuning(self, category):
        if category == 'ServiceOperationA':
            return EqualizerTuning(operation_a_playback_function,
                                   operation_a_result_extractor,
                                   operation_a_comparator)
        if category == 'ServiceOperationB':
            return EqualizerTuning(operation_b_playback_function,
                                   operation_b_result_extractor,
                                   operation_b_comparator)
```

# Framework Classes - Comparing replayed vs recorded
## `PlaybackStudio` class
The studio runs many playbacks for one or more categories (operation), and uses the `Equalizer` to conduct a comparison
between the recorded outputs to the playback outputs

```python
def __init__(self, categories, equalizer_tuner, tape_recorder, lookup_properties=None,
             recording_ids=None, compare_execution_config=None)
```
* `categories` - Categories (operations) to conduct comparison for
* `equalizer_tuner` - Given a category return a corresponding equalizer tuning to be used for playback and comparison
* `tape_recorder` - The tape recorder that will be used to play the recordings
* `lookup_properties` - Optional `RecordingLookupProperties` used to filter recordings by
* `recording_ids` - Optional specific recording ids, if given the `categories` and `lookup_properties` are ignored and
  only the given recording ids will be played
* `compare_execution_config` -  Configuration specific to the comparison execution flow

## `EqualizerTuner` class
An abstract class that is used to create an `EqualizerTuning` per category that contains the correct plugins (functions)
that are required to play the operation and compare its results

```python
def create_category_tuning(self, category)
```
Create a new `EqualizerTuning` for the given category

```python
class EqualizerTuning(object):
    def __init__(self, playback_function, result_extractor, comparator,
                 comparison_data_extractor=None):
        self.playback_function = playback_function
        self.result_extractor = result_extractor
        self.comparator = comparator
        self.comparison_data_extractor = comparison_data_extractor
```

# Contribution
Feel free to send pull requests and raise issues. Make sure to add/modify tests to cover your changes.
Please squash your commits in the pull request to one commit. If there is a good logical reason to break it into
few commits, multiple pull requests are preferred unless there is a good logical reason to bundle the commits to the
same pull request.

Please pay attention that as of now, this framework is compatible with both python 2 and 3, hence any changes should
keep that. We use the six framework to help keep this support.

## Running tests
Tests are automatically run in the ci flow using circle-ci. In order to run them locally you should install
development requirements:
`pip install -e .[dev]`
and then run `pytest tests`
