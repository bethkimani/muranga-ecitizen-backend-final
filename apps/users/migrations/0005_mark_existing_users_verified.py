from django.db import migrations


def mark_existing_users_verified(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.using(schema_editor.connection.alias).all().update(is_phone_verified=True)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0004_onetimecode'),
    ]

    operations = [
        migrations.RunPython(
            mark_existing_users_verified,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
