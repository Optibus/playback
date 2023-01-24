from jsonpickle import encode, decode


def pickle_copy(value):
    """ copies any object (deeply) by pickly encoding/decoding it
    :type value: any
    :param value: the value you to be copied
    :rtype: any
    """
    return decode(encode(value, unpicklable=True))
