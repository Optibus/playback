# p3ready
from __future__ import absolute_import

import unittest

from playback.tape_cassette import TapeCassette


class TestTapeCassette(unittest.TestCase):

    def test_metadata_content_filter_by_number_value(self):
        recording_metadata = {'key1': 5, 'key2': "bla"}
        filter_metadata = {'key1': 5}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_number_value_not_found(self):
        recording_metadata = {'key1': 5, 'key2': "bla"}
        filter_metadata = {'key1': 8}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_string_value(self):
        recording_metadata = {'key1': 5, 'key2': "bla"}
        filter_metadata = {'key2': "bla"}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_string_value_not_found(self):
        recording_metadata = {'key1': 5, 'key2': "bla"}
        filter_metadata = {'key2': "bla1"}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_list_value(self):
        recording_metadata = {'key1': 5, 'key2': "bla"}
        filter_metadata = {'key2': ["bla", "bla2"]}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        recording_metadata = {'key1': 5, 'key2': "bla2"}
        filter_metadata = {'key2': ["bla", "bla2"]}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_list_operator_object_value(self):
        recording_metadata = {'key1': 5, 'key2': "bla"}
        filter_metadata = {'key2': ["bla4", "bla5", {'operator': '=', 'value': "bla"}]}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_list_value_not_found(self):
        recording_metadata = {'key1': 5, 'key2': "bla"}
        filter_metadata = {'key2': ["bla1", "bla2"]}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        recording_metadata = {'key1': 5, 'key2': "bla2"}
        filter_metadata = {'key2': ["bla", "bla3"]}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_object_value(self):
        recording_metadata = {'key1': 5, 'key2': "bla", 'obj': {'key1': 6, 'key2': "bla"}}
        filter_metadata = {'obj': {'key1': 6, 'key2': "bla"}}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        filter_metadata = {'obj': {'key1': 6, 'key2': "bla1"}}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_operator_object_value_equal(self):
        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 5}
        filter_metadata = {'duration': {'operator': '=', 'value': 5}}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 6}
        filter_metadata = {'duration': {'operator': '=', 'value': 5}}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_operator_object_value_less(self):
        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 4.9}
        filter_metadata = {'duration': {'operator': '<', 'value': 5}}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 5}
        filter_metadata = {'duration': {'operator': '<', 'value': 5}}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_operator_object_value_less_equal(self):
        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 5}
        filter_metadata = {'duration': {'operator': '<=', 'value': 5}}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 5.1}
        filter_metadata = {'duration': {'operator': '<=', 'value': 5}}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_operator_object_value_greater(self):
        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 5.1}
        filter_metadata = {'duration': {'operator': '>', 'value': 5}}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 5}
        filter_metadata = {'duration': {'operator': '>', 'value': 5}}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

    def test_metadata_content_filter_by_operator_object_value_greater_equal(self):
        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 5.1}
        filter_metadata = {'duration': {'operator': '>=', 'value': 5}}
        self.assertTrue(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))

        recording_metadata = {'key1': 5, 'key2': "bla", 'duration': 4.9}
        filter_metadata = {'duration': {'operator': '>=', 'value': 5}}
        self.assertFalse(TapeCassette.match_against_recorded_metadata(filter_metadata, recording_metadata))
