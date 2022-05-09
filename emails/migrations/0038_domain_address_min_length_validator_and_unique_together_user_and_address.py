# Generated by Django 2.2.24 on 2021-12-20 21:11

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0037_reply_add_index_on_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='domainaddress',
            name='address',
            field=models.CharField(
                max_length=64,
                validators=[django.core.validators.MinLengthValidator(limit_value=1)],
            ),
        ),
        migrations.AlterUniqueTogether(
            name='domainaddress',
            unique_together={('user', 'address')},
        ),
    ]
