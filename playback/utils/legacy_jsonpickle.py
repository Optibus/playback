"""
Decodes data that jsonpickle 0.9.x encoded when a later jsonpickle version is installed
"""

import base64
import json
import quopri

import jsonpickle
from jsonpickle import tags

# jsonpickle 0.9.x encoded these types with handlers that later versions removed
_LEGACY_REDUCE_HANDLER_TYPES = frozenset(
    [
        'collections.Counter',
        'collections.OrderedDict',
        'collections.deque',
        'datetime.timedelta',
        'decimal.Decimal',
        'os.stat_result',
        'time.struct_time',
    ]
)

_LEGACY_REDUCE_HANDLER_KEY = '__reduce__'

_LEGACY_DATETIME_HANDLER_TYPES = frozenset(['datetime.date', 'datetime.datetime', 'datetime.time'])

# The tags in the order in which the 0.9.x unpickler checks them
_LEGACY_RESTORE_TAGS = (
    tags.B64,
    tags.BYTES,
    tags.ID,
    tags.REF,
    tags.ITERATOR,
    tags.TYPE,
    tags.REPR,
    tags.REDUCE,
    tags.OBJECT,
    tags.FUNCTION,
    tags.TUPLE,
    tags.SET,
)

# The tags of the dicts that the 0.9.x pickler and unpickler number, lists are numbered too
_LEGACY_NUMBERED_TAGS = frozenset([tags.REPR, tags.OBJECT])


def decode_legacy(encoded):
    """
    Decodes a value that jsonpickle 0.9.x encoded
    :param encoded: Encoded value
    :type encoded: str
    :return: Decoded value
    :rtype: object
    """
    if _is_legacy_jsonpickle_installed():
        return jsonpickle.decode(encoded)

    flattened = json.loads(encoded)
    # Copies two bugs of the 0.9.x unpickler on purpose, so that a replay gives the same values with all versions
    _renumber_legacy_references(flattened)
    _upgrade_legacy_flattened(flattened)
    # jsonpickle 0.9.x does not give a reference id to a dict, v1_decode restores the ids the same way
    return jsonpickle.unpickler.Unpickler(v1_decode=True).restore(flattened)  # pylint: disable=unexpected-keyword-arg


def _renumber_legacy_references(flattened):
    """
    Changes, in place, the py/id references of a flattened value that jsonpickle 0.9.x encoded, so that later versions
    restore them to the same objects as the 0.9.x unpickler. The 0.9.x pickler numbers a py/reduce object before the
    objects in it, but the 0.9.x unpickler numbers it after them. Thus, with 0.9.x, a reference to such an object or to
    an object in it restores another object. The 0.9.x unpickler also numbers the lists in the state of an object
    without __setstate__ twice, so a later reference restores another object.
    :param flattened: Value that jsonpickle 0.9.x flattened, as loaded from JSON
    :type flattened: object
    """
    pickler_order = []
    unpickler_order = []
    references = []
    _add_legacy_restore_order(flattened, pickler_order, unpickler_order, references)

    pickler_indexes = {id(node): index for index, node in enumerate(pickler_order)}
    for reference in references:
        index = reference[tags.ID]
        if isinstance(index, int) and 0 <= index < len(unpickler_order):
            reference[tags.ID] = pickler_indexes[id(unpickler_order[index])]


def _add_legacy_restore_order(node, pickler_order, unpickler_order, references):
    """
    Walks a flattened value in the order in which the jsonpickle 0.9.x unpickler restores it
    :param node: Part of the flattened value
    :type node: object
    :param pickler_order: Gets the numbered parts, in the order in which the 0.9.x pickler numbered them
    :type pickler_order: list
    :param unpickler_order: Gets the numbered parts, in the order in which the 0.9.x unpickler numbers them
    :type unpickler_order: list
    :param references: Gets the py/id parts
    :type references: list
    """
    if isinstance(node, list):
        tag = None
        children = node
    elif isinstance(node, dict):
        tag = _legacy_restore_tag(node)
        children = _legacy_restored_children(node, tag)
    else:
        return

    if tag == tags.ID:
        references.append(node)
        return

    numbered = isinstance(node, list) or tag in _LEGACY_NUMBERED_TAGS
    if numbered or tag == tags.REDUCE:
        pickler_order.append(node)

    if numbered:
        unpickler_order.append(node)

    for child in children:
        _add_legacy_restore_order(child, pickler_order, unpickler_order, references)

    if tag == tags.REDUCE:
        unpickler_order.append(node)

    if tag == tags.OBJECT and tags.STATE in node and _is_legacy_state_restored_again(node[tags.OBJECT]):
        _add_legacy_state_restored_again(node[tags.STATE], unpickler_order)


def _legacy_restore_tag(node):
    """
    :param node: Part of a flattened value
    :type node: object
    :return: The tag by which the 0.9.x unpickler restores the part, None for a plain dict and for a value that is not
    a dict
    :rtype: str
    """
    if not isinstance(node, dict):
        return None

    return next((tag for tag in _LEGACY_RESTORE_TAGS if tag in node), None)


def _legacy_restored_children(node, tag):
    """
    :param node: Flattened dict
    :type node: dict
    :param tag: The tag by which the 0.9.x unpickler restores the dict, None for a plain dict
    :type tag: str
    :return: The parts of the dict that the 0.9.x unpickler restores, in the order in which it restores them
    :rtype: list
    """
    if tag is None:
        return [value for _, value in sorted(node.items(), key=lambda item: item[0])]

    if tag in (tags.REDUCE, tags.TUPLE, tags.SET):
        return list(node[tag])

    if tag == tags.ITERATOR:
        return [node[tag]]

    if tag == tags.OBJECT:
        return _legacy_restored_object_children(node)

    return []


def _legacy_restored_object_children(node):
    """
    :param node: Flattened object
    :type node: dict
    :return: The parts of the object that the 0.9.x unpickler restores, in the order in which it restores them
    :rtype: list
    """
    class_name = node[tags.OBJECT]
    reduce_value = node.get(_LEGACY_REDUCE_HANDLER_KEY)
    if class_name in _LEGACY_DATETIME_HANDLER_TYPES and isinstance(reduce_value, list) and len(reduce_value) == 2:
        return reduce_value[:1] + list(reduce_value[1][1:])

    if class_name in _LEGACY_REDUCE_HANDLER_TYPES and isinstance(reduce_value, list):
        return list(reduce_value)

    children = [node['default_factory']] if 'default_factory' in node else []
    if tags.NEWARGSEX in node:
        children.extend(args for args in node[tags.NEWARGSEX] if args)
    elif node.get(tags.NEWARGS, node.get(tags.INITARGS)):
        children.append(node.get(tags.NEWARGS, node.get(tags.INITARGS)))

    children.extend(
        value
        for key, value in sorted(node.items(), key=lambda item: item[0])
        if key not in tags.RESERVED and key != 'default_factory'
    )
    children.extend(node.get(tags.SEQ, []))
    if tags.STATE in node:
        children.append(node[tags.STATE])

    return children


def _is_legacy_state_restored_again(class_name):
    """
    :param class_name: The py/object name of a flattened object
    :type class_name: str
    :return: Does the 0.9.x unpickler restore the state of the object twice: the class has no __setstate__. It does
    not when the class cannot be loaded, because it then does not restore the object.
    :rtype: bool
    """
    cls = jsonpickle.unpickler.loadclass(class_name)
    return cls is not None and not hasattr(cls, '__setstate__')


def _add_legacy_state_restored_again(state, unpickler_order):
    """
    Walks the state of an object the second time that the 0.9.x unpickler restores it. To set the restored state on an
    object without __setstate__, the 0.9.x unpickler restores the values of the restored state again: of the dict, or
    of the two dicts of a (dict, slots dict) tuple, the slots dict first.
    :param state: The py/state part of a flattened object
    :type state: object
    :param unpickler_order: Gets the parts that are numbered again
    :type unpickler_order: list
    """
    if _is_legacy_plain_dict(state):
        state_dicts = [state]
    elif _legacy_restore_tag(state) == tags.TUPLE and len(state[tags.TUPLE]) == 2:
        instance_dict, slots_dict = state[tags.TUPLE]
        if not _is_legacy_plain_dict(slots_dict):
            return

        state_dicts = [slots_dict, instance_dict] if _is_legacy_plain_dict(instance_dict) else [slots_dict]
    else:
        return

    for state_dict in state_dicts:
        for _, value in sorted(state_dict.items(), key=lambda item: item[0]):
            _add_legacy_restored_again(value, unpickler_order)


def _add_legacy_restored_again(node, unpickler_order):
    """
    Walks a part of a restored state as the 0.9.x unpickler restores it again: it restores a list as a new list, which
    gets a number, and the values in a dict again. It keeps the other values. An object that was restored as its state
    list is a list here. The new list is equal to the first one, so it is added to the order as the same part, and a
    reference to it restores an equal list. But later versions do not make the new lists: two equal lists of the 0.9.x
    unpickler can be one list.
    :param node: Part of the py/state part of a flattened object
    :type node: object
    :param unpickler_order: Gets the parts that are numbered again
    :type unpickler_order: list
    """
    if _legacy_restore_tag(node) == tags.ID:
        index = node[tags.ID]
        node = unpickler_order[index] if isinstance(index, int) and 0 <= index < len(unpickler_order) else None
    elif _legacy_restore_tag(node) == tags.OBJECT and _is_legacy_object_restored_as_state_list(node):
        node = node[tags.STATE]

    if isinstance(node, list):
        unpickler_order.append(node)
        children = node
    elif _is_legacy_plain_dict(node):
        children = [value for _, value in sorted(node.items(), key=lambda item: item[0])]
    else:
        return

    for child in children:
        _add_legacy_restored_again(child, unpickler_order)


def _is_legacy_object_restored_as_state_list(node):
    """
    :param node: Flattened object
    :type node: dict
    :return: Does the 0.9.x unpickler restore the object as its py/state list: the state is a list, and the class has
    no __setstate__, __getnewargs__ or __getnewargs_ex__
    :rtype: bool
    """
    if not isinstance(node.get(tags.STATE), list):
        return False

    cls = jsonpickle.unpickler.loadclass(node[tags.OBJECT])
    return cls is not None and not any(
        hasattr(cls, name) for name in ('__setstate__', '__getnewargs__', '__getnewargs_ex__')
    )


def _is_legacy_plain_dict(node):
    """
    :param node: Part of a flattened value
    :type node: object
    :return: Is the part a dict that the 0.9.x unpickler restores as a plain dict
    :rtype: bool
    """
    return isinstance(node, dict) and _legacy_restore_tag(node) is None


def _upgrade_legacy_flattened(flattened):
    """
    Changes, in place, the parts of a flattened value that jsonpickle 0.9.x wrote in a form that later versions do not
    restore. The forms that are changed are never written by later versions.
    :param flattened: Value that jsonpickle 0.9.x flattened, as loaded from JSON
    :type flattened: object
    """
    pending = [flattened]
    while pending:
        node = pending.pop()
        if isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, dict):
            if tags.REDUCE in node:
                node.pop(tags.OBJECT, None)
            elif node.get(tags.OBJECT) in _LEGACY_REDUCE_HANDLER_TYPES and _LEGACY_REDUCE_HANDLER_KEY in node:
                reduce_value = node[_LEGACY_REDUCE_HANDLER_KEY]
                node.clear()
                node[tags.REDUCE] = reduce_value
            elif tags.BYTES in node:
                raw_bytes = quopri.decodestring(node.pop(tags.BYTES).encode('utf-8'))
                node[tags.B64] = base64.b64encode(raw_bytes).decode('ascii')

            pending.extend(node.values())


def _is_legacy_jsonpickle_installed():
    """
    :return: Is the installed jsonpickle a 0.9.x version
    :rtype: bool
    """
    return int(jsonpickle.__version__.split('.')[0]) < 1
