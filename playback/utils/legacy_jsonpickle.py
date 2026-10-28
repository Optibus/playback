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
    _upgrade_legacy_flattened(flattened)
    # jsonpickle 0.9.x does not give a reference id to a dict, v1_decode restores the ids the same way
    return jsonpickle.unpickler.Unpickler(v1_decode=True).restore(flattened)  # pylint: disable=unexpected-keyword-arg


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
