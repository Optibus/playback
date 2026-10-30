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
    # Copies a bug of the 0.9.x unpickler on purpose, so that a replay gives the same values with all versions
    _renumber_legacy_references(flattened)
    _upgrade_legacy_flattened(flattened)
    # jsonpickle 0.9.x does not give a reference id to a dict, v1_decode restores the ids the same way
    return jsonpickle.unpickler.Unpickler(v1_decode=True).restore(flattened)  # pylint: disable=unexpected-keyword-arg


def _renumber_legacy_references(flattened):
    """
    Changes, in place, the py/id references of a flattened value that jsonpickle 0.9.x encoded, so that later versions
    restore them to the same objects as the 0.9.x unpickler. The 0.9.x pickler numbers a py/reduce object before the
    objects in it, but the 0.9.x unpickler numbers it after them. Thus, with 0.9.x, a reference to such an object or to
    an object in it restores another object.
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
        tag = next((tag for tag in _LEGACY_RESTORE_TAGS if tag in node), None)
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
