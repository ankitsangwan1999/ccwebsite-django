# Generated by Django 2.2.3 on 2019-09-19 21:56

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0004_auto_20190919_1532'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='post_on_date',
            field=models.DateField(default=datetime.datetime(2019, 9, 19, 21, 56, 36, 204003, tzinfo=utc)),
        ),
        migrations.AlterField(
            model_name='postview',
            name='created',
            field=models.DateTimeField(default=datetime.datetime(2019, 9, 19, 21, 56, 36, 205998, tzinfo=utc)),
        ),
    ]
