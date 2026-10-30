import copy
import json
import unittest

from jsonpickle import encode

from playback.utils.legacy_jsonpickle import decode_legacy, _is_legacy_jsonpickle_installed, _upgrade_legacy_flattened
from tests.utils.legacy_jsonpickle_cases import build_cases, describe, load_fixtures


class TestLegacyJsonpickle(unittest.TestCase):

    NOT_SHARED_LIKE_0_9_4_CASES = ('shared list in state without setstate',)

    def test_decode_values_encoded_by_jsonpickle_0_9_4(self):
        fixtures = load_fixtures()

        self.assertEqual(list(build_cases()), list(fixtures))
        for fixture in fixtures.values():
            if fixture['name'] in self.NOT_SHARED_LIKE_0_9_4_CASES:
                continue

            with self.subTest(fixture['name']):
                self.assertEqual(fixture['expected'], describe(decode_legacy(fixture['encoded'])))

    @unittest.skipIf(_is_legacy_jsonpickle_installed(), 'jsonpickle 0.9.x restores the list in the state twice')
    def test_list_shared_in_state_without_setstate_stays_shared(self):
        fixture = load_fixtures()['shared list in state without setstate']
        state_object, _, _, reference = decode_legacy(fixture['encoded'])

        self.assertEqual([14, 15], reference)
        self.assertIs(state_object.values['same list'], reference)
        self.assertIs(state_object.values['list'], state_object.values['same list'])

    @unittest.skipIf(_is_legacy_jsonpickle_installed(), 'The upgrade applies only to later jsonpickle versions')
    def test_upgrade_does_not_change_values_encoded_by_installed_jsonpickle(self):
        for name, value in build_cases().items():
            with self.subTest(name):
                flattened = json.loads(encode(value))
                upgraded = copy.deepcopy(flattened)
                _upgrade_legacy_flattened(upgraded)
                self.assertEqual(flattened, upgraded)
