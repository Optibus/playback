def extract_error_message(exception):
    """
    Extracting an error's message, if such exists (and converting it to unicode)
    :param exception: an error
    :type exception: Exception
    :return: the message, if such exists
    :rtype: basestring
    """
    exception_message = exception.message if hasattr(exception, 'message') else ''
    if not isinstance(exception_message, six.text_type) and isinstance(exception_message, six.string_types):
        try:
            exception_message = get_variable_as_unicode(exception_message)
        except UnicodeDecodeError:
            exception_message = six.text_type(exception_message, errors='ignore')
    return exception_message
