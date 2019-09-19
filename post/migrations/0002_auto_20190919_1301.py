# Generated by Django 2.2.3 on 2019-09-19 07:31

import datetime
from django.conf import settings
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('post', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='post_on_date',
            field=models.DateField(default=datetime.datetime(2019, 9, 19, 7, 31, 4, 343059, tzinfo=utc)),
        ),
        migrations.AlterField(
            model_name='post',
            name='tags',
            field=models.ManyToManyField(blank=True, default=None, to='post.Tags', verbose_name='Post Tags'),
        ),
        migrations.AlterField(
            model_name='tags',
            name='subscribed_by',
            field=models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL, verbose_name='Subscribed By'),
        ),
    ]
