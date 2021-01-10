import logging
import boto3
from functools import reduce

from pytz import UTC as utc


class S3BasicFacade(object):
    def __init__(self, bucket, region=None):
        self.bucket = bucket
        self._bucket = boto3.resource('s3').Bucket(bucket)
        self.client = boto3.client('s3', region_name=region)
        logging.getLogger('botocore').setLevel(logging.CRITICAL)
        logging.getLogger('boto3').setLevel(logging.CRITICAL)
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('s3transfer').setLevel(logging.CRITICAL)
        logging.getLogger('requests').setLevel(logging.CRITICAL)

    def put_string(self, key, string, **kwargs):
        """
        Put a string in S3

        :param key: S3 key
        :type key: str
        :param string: string to store in S3
        :type string: str
        :param kwargs: kwargs
        :type kwargs: dict
        """

        params = dict(
            Bucket=self.bucket,
            Key=key,
            Body=string
        )
        if kwargs:
            params.update(kwargs)

        return self.client.put_object(**params)

    def get_string(self, key):
        """
        Get the string that associated with the given key from the S3 store.

        :param key: S3 key
        :type key: str
        :return: The string from S3
        :rtype: str
        """
        return self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read()

    def iter_keys(self, prefix=None, start_date=None, end_date=None, content_filter=None, limit=None):
        """
        yields the keys that exist in the S3 store.
        :param prefix: if not None, yields only objects with keys that start with the given prefix.
        :type prefix: str
        :param start_date: Optional last modified start date (need to be given in utc time)
        :type start_date: datetime.datetime
        :param end_date: Optional last modified end date (need to be given in utc time)
        :type end_date: datetime.datetime
        :param content_filter: Function that filters object according to their content
        :type content_filter: function
        :param limit: Optional limit on number of keys to fetch
        :type limit: int
        :rtype: Iterator[str]
        """

        predicates = []

        if start_date or end_date:
            start_date = utc.localize(start_date) if start_date else None
            end_date = utc.localize(end_date) if end_date else None

            predicates.append(lambda o: ((start_date is None or start_date <= o.last_modified) and
                                         (end_date is None or o.last_modified <= end_date)))

        if content_filter:
            predicates.append(lambda o: content_filter(o.get()["Body"].read()))

        count = 0
        for s3_object in self._bucket.objects.filter(Prefix=prefix):
            if count == limit:
                break
            is_relevant = reduce(lambda carry, current: carry and current(s3_object), predicates, True)
            if is_relevant:
                count += 1
                yield s3_object.key
        pass

    def delete_by_prefix(self, prefix):
        """
        Deletes all the keys that start with the given prefix in the S3 store.

        :type prefix: str
        """
        return self._bucket.objects.filter(Prefix=prefix).delete()
