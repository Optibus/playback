import copy
import json
import unittest

from jsonpickle import encode

from playback.tape_recorder import TapeRecorder
from playback.utils.legacy_jsonpickle import (
    decode_legacy,
    _is_legacy_jsonpickle_installed,
    normalize_interception_key,
    _upgrade_legacy_flattened,
    upgrade_legacy_interception_key,
)
from tests.utils.legacy_jsonpickle_cases import (
    KEY_ALIAS,
    KEY_FIXTURES_PATH,
    build_cases,
    build_key_cases,
    describe,
    load_fixtures,
)


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


class TestLegacyInterceptionKeys(unittest.TestCase):

    NOT_NORMALIZED_CASES = ('shared list and dict',)

    def test_legacy_key_matches_key_of_installed_jsonpickle(self):
        fixtures = load_fixtures(KEY_FIXTURES_PATH)
        cases = build_key_cases()

        self.assertEqual(list(cases), list(fixtures))
        for name, (args, kwargs) in cases.items():
            if name in self.NOT_NORMALIZED_CASES:
                continue

            with self.subTest(name):
                legacy_key = normalize_interception_key(upgrade_legacy_interception_key(fixtures[name]['key']))
                self.assertEqual(legacy_key, normalize_interception_key(self._key(args, kwargs)))

    @unittest.skipIf(_is_legacy_jsonpickle_installed(), 'jsonpickle 0.9.x sorts the dict keys when it encodes them')
    def test_dict_order_is_normalized(self):
        legacy_key = load_fixtures(KEY_FIXTURES_PATH)['dict']['key']
        key = self._key(*build_key_cases()['dict'])

        self.assertNotEqual(upgrade_legacy_interception_key(legacy_key), key)
        self.assertEqual(
            normalize_interception_key(upgrade_legacy_interception_key(legacy_key)), normalize_interception_key(key)
        )

    @unittest.skipIf(_is_legacy_jsonpickle_installed(), 'jsonpickle 0.9.x sorts the dict keys when it encodes them')
    def test_key_with_reference_id_and_dicts_in_other_order_is_not_normalized(self):
        legacy_key = load_fixtures(KEY_FIXTURES_PATH)['shared list and dict']['key']
        key = self._key(*build_key_cases()['shared list and dict'])

        self.assertNotEqual(
            normalize_interception_key(upgrade_legacy_interception_key(legacy_key)), normalize_interception_key(key)
        )

    def test_upgrade_and_normalize_do_not_change_other_keys(self):
        for key in ('output: get #1', 'input: get args=not json, kwargs=[]'):
            with self.subTest(key):
                self.assertEqual(key, upgrade_legacy_interception_key(key))
                self.assertEqual(key, normalize_interception_key(key))

    def test_normalize_sorts_dict_keys(self):
        key = self._key(({'b': 1, 'a': {'d': 2, 'c': 3}},), {'limit': 5})

        self.assertEqual(
            'input: get args={"py/tuple": [{"a": {"c": 3, "d": 2}, "b": 1}]}, kwargs=[{"py/tuple": ["limit", 5]}]',
            normalize_interception_key(key),
        )

    @staticmethod
    def _key(args, kwargs):
        return TapeRecorder._input_interception_key(KEY_ALIAS, None, True, *args, **kwargs)
