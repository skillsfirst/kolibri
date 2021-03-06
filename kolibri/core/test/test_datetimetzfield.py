from __future__ import absolute_import, print_function, unicode_literals

import datetime
import pytz

from django.db import models
from django.test import TestCase
from django.utils import timezone
from kolibri.core.fields import DateTimeTzField
from kolibri.core.serializers import DateTimeTzField as DateTimeTzSerializerField

def aware_datetime():
    return timezone.get_current_timezone().localize(datetime.datetime(2000, 12, 11, 10, 9, 8))

class DateTimeTzModel(models.Model):
    timestamp = DateTimeTzField(null=True)
    default_timestamp = DateTimeTzField(default=aware_datetime)


class DateTimeTzFieldTestCase(TestCase):

    def test_timestamp_utc_create(self):
        timezone.activate(pytz.utc)
        obj = DateTimeTzModel.objects.create(timestamp=aware_datetime())
        self.assertEqual(obj.timestamp.tzinfo, aware_datetime().tzinfo)
        timezone.deactivate()

    def test_timestamp_arbitrary_create(self):
        tz = pytz.timezone('Africa/Nairobi')
        timezone.activate(tz)
        timestamp = aware_datetime()
        obj = DateTimeTzModel.objects.create(timestamp=timestamp)
        self.assertEqual(obj.timestamp.tzinfo, timestamp.tzinfo)
        timezone.deactivate()

    def test_default_utc_create(self):
        timezone.activate(pytz.utc)
        obj = DateTimeTzModel.objects.create()
        self.assertEqual(obj.default_timestamp.tzinfo, pytz.utc)
        timezone.deactivate()

    def test_default_arbitrary_create(self):
        tz = pytz.timezone('Africa/Nairobi')
        timezone.activate(tz)
        timestamp = aware_datetime()
        obj = DateTimeTzModel.objects.create()
        self.assertEqual(obj.default_timestamp.tzinfo, timestamp.tzinfo)
        timezone.deactivate()


class DateTimeTzSerializerFieldTestCase(TestCase):

    def test_timestamp_utc_parse(self):
        timezone.activate(pytz.utc)
        field = DateTimeTzSerializerField()
        timestamp = aware_datetime()
        self.assertEqual(field.to_internal_value(timestamp.isoformat()).tzinfo, aware_datetime().tzinfo)
        timezone.deactivate()

    def test_timestamp_arbitrary_parse(self):
        tz = pytz.timezone('Africa/Nairobi')
        timezone.activate(tz)
        field = DateTimeTzSerializerField()
        timestamp = aware_datetime()
        self.assertEqual(field.to_internal_value(timestamp.isoformat()).tzinfo, aware_datetime().tzinfo)
        timezone.deactivate()
