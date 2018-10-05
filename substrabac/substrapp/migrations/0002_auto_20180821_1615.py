# Generated by Django 2.0.5 on 2018-08-21 16:15

from django.db import migrations, models
import substrapp.models.algo
import substrapp.models.challenge
import substrapp.models.data
import substrapp.models.dataset
import substrapp.models.model


class Migration(migrations.Migration):

    dependencies = [
        ('substrapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='algo',
            name='description',
            field=models.FileField(max_length=500, upload_to=substrapp.models.algo.upload_to),
        ),
        migrations.AlterField(
            model_name='algo',
            name='file',
            field=models.FileField(max_length=500, upload_to=substrapp.models.algo.upload_to),
        ),
        migrations.AlterField(
            model_name='challenge',
            name='description',
            field=models.FileField(max_length=500, upload_to=substrapp.models.challenge.upload_to),
        ),
        migrations.AlterField(
            model_name='challenge',
            name='metrics',
            field=models.FileField(max_length=500, upload_to=substrapp.models.challenge.upload_to),
        ),
        migrations.AlterField(
            model_name='data',
            name='file',
            field=models.FileField(max_length=500, upload_to=substrapp.models.data.upload_to),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='data_opener',
            field=models.FileField(max_length=500, upload_to=substrapp.models.dataset.upload_to),
        ),
        migrations.AlterField(
            model_name='dataset',
            name='description',
            field=models.FileField(max_length=500, upload_to=substrapp.models.dataset.upload_to),
        ),
        migrations.AlterField(
            model_name='model',
            name='file',
            field=models.FileField(max_length=500, upload_to=substrapp.models.model.upload_to),
        ),
    ]