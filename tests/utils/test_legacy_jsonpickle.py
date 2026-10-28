import copy
import json
import unittest

from jsonpickle import encode

from playback.utils.legacy_jsonpickle import decode_legacy, _is_legacy_jsonpickle_installed, _upgrade_legacy_flattened
from tests.utils.legacy_jsonpickle_cases import build_cases, describe, load_fixtures


class TestLegacyJsonpickle(unittest.TestCase):

    def test_decode_values_encoded_by_jsonpickle_0_9_4(self):
        fixtures = load_fixtures()

        self.assertEqual(list(build_cases()), list(fixtures))
        for fixture in fixtures.values():
            with self.subTest(fixture['name']):
                self.assertEqual(fixture['expected'], describe(decode_legacy(fixture['encoded'])))

    @unittest.skipIf(_is_legacy_jsonpickle_installed(), 'The upgrade applies only to later jsonpickle versions')
    def test_upgrade_does_not_change_values_encoded_by_installed_jsonpickle(self):
        for name, value in build_cases().items():
            with self.subTest(name):
                flattened = json.loads(encode(value))
                upgraded = copy.deepcopy(flattened)
                _upgrade_legacy_flattened(upgraded)
                self.assertEqual(flattened, upgraded)
