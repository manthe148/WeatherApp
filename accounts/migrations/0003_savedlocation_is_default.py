# Generated by Django 5.2 on 2025-05-06 00:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_remove_profile_default_latitude_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='savedlocation',
            name='is_default',
            field=models.BooleanField(default=False),
        ),
    ]
