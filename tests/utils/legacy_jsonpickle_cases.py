import json
import os
import time
from collections import OrderedDict, Counter, deque, defaultdict, namedtuple
from collections.abc import Iterator
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from enum import Enum

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), '..', 'resources', 'legacy_jsonpickle_fixtures.json')
KEY_FIXTURES_PATH = os.path.join(os.path.dirname(__file__), '..', 'resources', 'legacy_jsonpickle_key_fixtures.json')
KEY_ALIAS = 'get'


def load_fixtures(path=FIXTURES_PATH):
    """
    :param path: Fixtures file, FIXTURES_PATH or KEY_FIXTURES_PATH
    :type path: str
    :return: The cases as encoded by jsonpickle 0.9.4, by case name
    :rtype: OrderedDict
    """
    with open(path) as fixtures_file:
        return OrderedDict((fixture['name'], fixture) for fixture in json.load(fixtures_file))


class Color(Enum):
    RED = 1
    BLUE = 2


class Node(object):
    def __init__(self, name):
        self.name = name
        self.children = []
        self.parent = None


class WithState(object):
    def __init__(self, values):
        self.values = values

    def __getstate__(self):
        return {'stored': self.values}

    def __setstate__(self, state):
        self.values = state['stored']


class WithSlots(object):
    __slots__ = ('first', 'second')

    def __init__(self, first, second):
        self.first = first
        self.second = second


class TaggedList(list):
    pass


class TaggedDict(dict):
    pass


class Reduced(object):
    def __init__(self, values):
        self.values = values

    def __reduce__(self):
        return Reduced, (self.values,)


class StateWithoutSetstate(object):
    def __init__(self, values):
        self.values = values

    def __getstate__(self):
        return {'values': self.values}


class ListState(object):
    def __init__(self, values):
        self.values = values

    def __getstate__(self):
        return self.values


class SlotsStateWithoutSetstate(object):
    def __init__(self, first, second):
        self.first = first
        self.second = second

    def __getstate__(self):
        return {'first': self.first}, {'second': self.second}


class ListSlotsStateWithoutSetstate(object):
    def __init__(self, first, second):
        self.first = first
        self.second = second

    def __getstate__(self):
        return {'first': self.first}, [self.second]


class BytesState(object):
    def __init__(self, raw):
        self.raw = raw

    def __getstate__(self):
        return self.raw

    def __setstate__(self, state):
        self.raw = state


class WithNewArgsEx(object):
    def __new__(cls, first, second=None):
        instance = super(WithNewArgsEx, cls).__new__(cls)
        instance.first = first
        instance.second = second
        return instance

    def __getnewargs_ex__(self):
        return (self.first,), {'second': self.second}


Fingerprint = namedtuple('Fingerprint', 'name version')


def build_cases():
    """
    Values that cover the encodings that changed after jsonpickle 0.9.x, alone and with shared references
    """
    shared_list = [1, 2]
    shared_node = Node('shared')
    root = Node('root')
    child = Node('child')
    child.parent = root
    root.children.append(child)
    tagged_list = TaggedList([shared_list, 3])
    tagged_list.tag = 'tagged'
    shared_frozenset = frozenset([5])
    reduced_values = [6, 7]
    reduced = Reduced(reduced_values)
    state_values = [14, 15]
    after_state = ['after state']

    return OrderedDict(
        [
            ('enum', Color.RED),
            ('frozenset', frozenset([3])),
            ('timedelta', timedelta(days=1, seconds=2)),
            ('decimal', Decimal('1.10')),
            ('ordered dict', OrderedDict([('z', 1), ('y', 2)])),
            ('counter', Counter('aab')),
            ('struct time', time.gmtime(0)),
            ('stat result', os.stat_result(range(10))),
            ('datetime', datetime(2026, 1, 2, 3, 4, 5, 6)),
            ('aware datetime', datetime(2026, 1, 2, tzinfo=timezone(timedelta(hours=2)))),
            ('date', date(2026, 1, 2)),
            ('bytes', bytes(range(100))),
            ('bytes of jsonpickle 0.9.3', bytes(range(100))),
            ('bytes state of jsonpickle 0.9.3', BytesState(b'\x00\x01 abc=\xff')),
            ('namedtuple', Fingerprint('data', 3)),
            ('state object', WithState([shared_list, shared_list])),
            ('slots object', WithSlots(shared_list, shared_list)),
            ('list subclass', tagged_list),
            ('dict subclass', TaggedDict(b=shared_list, a=shared_list)),
            ('default dict', defaultdict(list, {'k': shared_list})),
            ('set and tuple', [{(1, 2)}, (shared_list, shared_list)]),
            ('shared list in dict', {'b': shared_list, 'a': shared_list}),
            ('shared list in two dicts', [{'k': shared_list}, {'k': shared_list}]),
            ('shared object', [shared_node, shared_node]),
            ('cycle', root),
            ('shared list in iterator', [iter([shared_list, 3]), shared_list]),
            ('shared new argument', [WithNewArgsEx(shared_list, [4]), shared_list]),
            ('shared legacy types', [timedelta(seconds=7), Color.BLUE, frozenset([4]), shared_list, shared_list]),
            ('ordered dict then list', [OrderedDict([('z', shared_list)]), shared_list]),
            ('shared frozenset', [shared_frozenset, shared_frozenset]),
            ('shared reduce argument', [reduced, reduced_values, reduced]),
            (
                'state without setstate',
                [
                    WithState([10]),
                    StateWithoutSetstate({'list': [8, 9], 'dict': {'list': [11]}}),
                    after_state,
                    after_state,
                ],
            ),
            ('slots state without setstate', [SlotsStateWithoutSetstate([12], [13]), after_state, after_state]),
            (
                'list state in state without setstate',
                [StateWithoutSetstate({'list state': ListState([16])}), after_state, after_state],
            ),
            (
                'list slots state without setstate',
                [ListSlotsStateWithoutSetstate([17], [18]), after_state, after_state],
            ),
            (
                'object in state without setstate',
                [StateWithoutSetstate({'object': Node('in state'), 'list': [19]}), after_state, after_state],
            ),
            (
                'shared list in state without setstate',
                [
                    StateWithoutSetstate({'list': state_values, 'same list': state_values}),
                    ['before'],
                    after_state,
                    after_state,
                ],
            ),
            (
                'recording like',
                {
                    '_metadata': {'_tape_recorder_operation_class': Node, 'duration': 1.5},
                    'input: get args={"py/tuple": []}, kwargs=[]': {'value': [Color.RED, shared_list, shared_node]},
                    'output: store #1': {'args': (shared_list, {'when': timedelta(hours=1)}), 'kwargs': {}},
                    'output: _tape_recorder_operation #1': {'args': [shared_node, Decimal('2.5')], 'kwargs': {}},
                },
            ),
        ]
    )


def build_key_cases():
    """
    Arguments of intercepted inputs, as (args, kwargs). The keys of each dict are inserted in an order that is not
    sorted, as jsonpickle 0.9.x writes them.
    """

    def make_dict(*pairs):
        assert list(pairs) != sorted(pairs, key=lambda pair: pair[0])
        return dict(pairs)

    shared_list = [1, 2]
    node = Node('node')
    node.children.append(Node('child'))

    return OrderedDict(
        [
            ('dict', ((make_dict(('plan_id', 1), ('_id', make_dict(('$in', [3, 1, 2]), ('$exists', True)))),), {})),
            ('enum', ((Color.RED, 'x'), {})),
            ('enum in dict', ((make_dict(('module', Color.BLUE), ('enabled', True)),), {})),
            ('timedelta and decimal', ((timedelta(days=1), Decimal('1.5')), {})),
            ('bytes', ((bytes(range(100)),), {})),
            ('ordered dict', ((OrderedDict([('z', 1), ('y', 2)]),), {})),
            ('namedtuple', ((Fingerprint('data', 3),), {})),
            ('object', ((node,), {})),
            ('frozenset', ((frozenset([1]),), {})),
            ('datetime', ((datetime(2026, 1, 2, 3, 4, 5),), {})),
            ('kwargs', ((), {'query': make_dict(('status', 'active'), ('ids', [1, 2])), 'limit': 5})),
            ('shared list', (([shared_list, shared_list],), {})),
            ('shared list and dict', ((make_dict(('b', shared_list), ('a', shared_list)),), {})),
        ]
    )


def describe(value, seen=None):
    """
    Text form of a value that shows its type, its content and which containers and objects are shared
    """
    seen = {} if seen is None else seen
    tracked_types = (list, dict, Node, WithState, WithSlots, Reduced, StateWithoutSetstate, SlotsStateWithoutSetstate)
    if isinstance(value, tracked_types + (deque,)):
        if id(value) in seen:
            return '<ref {}>'.format(seen[id(value)][0])

        # Keeps the value alive, so that a temporary value does not give its id to a later value
        seen[id(value)] = (len(seen) + 1, value)

    if isinstance(value, Node):
        return 'Node({}, children={}, parent={})'.format(
            value.name, describe(value.children, seen), describe(value.parent, seen)
        )

    if isinstance(value, WithState):
        return 'WithState({})'.format(describe(value.values, seen))

    if isinstance(value, WithSlots):
        return 'WithSlots({}, {})'.format(describe(value.first, seen), describe(value.second, seen))

    if isinstance(value, Reduced):
        return 'Reduced({})'.format(describe(value.values, seen))

    if isinstance(value, StateWithoutSetstate):
        return 'StateWithoutSetstate({})'.format(describe(value.values, seen))

    if isinstance(value, SlotsStateWithoutSetstate):
        return 'SlotsStateWithoutSetstate({}, {})'.format(describe(value.first, seen), describe(value.second, seen))

    if isinstance(value, BytesState):
        return 'BytesState({})'.format(describe(value.raw, seen))

    if isinstance(value, WithNewArgsEx):
        return 'WithNewArgsEx({}, {})'.format(describe(value.first, seen), describe(value.second, seen))

    if isinstance(value, Iterator):
        return 'iterator[{}]'.format(', '.join(describe(item, seen) for item in value))

    if isinstance(value, (TaggedList, TaggedDict)):
        content = list(value) if isinstance(value, list) else dict(value)
        return '{}({}, {})'.format(type(value).__name__, describe(content, seen), describe(value.__dict__, seen))

    if isinstance(value, dict):
        items = value.items() if isinstance(value, OrderedDict) else sorted(value.items(), key=lambda item: item[0])
        return '{}{{{}}}'.format(
            type(value).__name__, ', '.join('{!r}: {}'.format(key, describe(item, seen)) for key, item in items)
        )

    if isinstance(value, (list, deque)):
        return '{}[{}]'.format(type(value).__name__, ', '.join(describe(item, seen) for item in value))

    if isinstance(value, (time.struct_time, os.stat_result)):
        return '{}({!r})'.format(type(value).__name__, tuple(value))

    if isinstance(value, tuple) and not hasattr(value, '_fields') and type(value) is tuple:
        return 'tuple({})'.format(', '.join(describe(item, seen) for item in value))

    return '{}({!r})'.format(type(value).__name__, value)
