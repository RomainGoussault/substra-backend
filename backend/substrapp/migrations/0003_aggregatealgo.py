# Generated by Django 2.1.2 on 2019-11-08 15:02

from django.db import migrations, models
import substrapp.models.aggregatealgo


class Migration(migrations.Migration):

    dependencies = [
        ('substrapp', '0002_compositealgo'),
    ]

    operations = [
        migrations.CreateModel(
            name='AggregateAlgo',
            fields=[
                ('pkhash', models.CharField(blank=True, max_length=64, primary_key=True, serialize=False)),
                ('file', models.FileField(max_length=500, upload_to=substrapp.models.aggregatealgo.upload_to)),
                ('description', models.FileField(max_length=500, upload_to=substrapp.models.aggregatealgo.upload_to)),
                ('validated', models.BooleanField(default=False)),
            ],
        ),
    ]
