from abc import ABCMeta, abstractmethod


class EqualizerTuning(object):
    def __init__(self, playback_function, result_extractor, comparator, comparison_data_extractor=None):
        """
        :param playback_function: A function that plays back the operation using the recording in the given id
        :type playback_function: function
        :param result_extractor: Extracts result from the recording and playback
        :type result_extractor: function
        :param comparison_data_extractor: Extracts optional data from the recording that will be passed to the
        comparator
        :type comparison_data_extractor: function
        :param comparator: A function use to create the equality status by comparing the expected vs actual result
        :type comparator: function
        """
        self.playback_function = playback_function
        self.result_extractor = result_extractor
        self.comparator = comparator
        self.comparison_data_extractor = comparison_data_extractor


class EqualizerTuner(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def create_category_tuning(self, category):
        """
        :param category: Category
        :type category: basestring
        :return: Tuning for category
        :rtype: EqualizerTuning
        """
        pass
