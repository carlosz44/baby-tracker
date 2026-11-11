from django.db import migrations


def remove_weeklylog_content_type(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="baby", model="weeklylog").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("baby", "0004_delete_weeklylog"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(remove_weeklylog_content_type, migrations.RunPython.noop),
    ]
