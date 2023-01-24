def is_iterable(thing):
    """
    Checks if the parameter is iterable.
    :param thing:
    :return:
    """
    try:
        iter(thing)
    except TypeError:
        return False

    return True
