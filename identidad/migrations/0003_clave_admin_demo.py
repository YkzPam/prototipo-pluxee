from django.contrib.auth.hashers import check_password, make_password
from django.db import migrations


def separar_clave_administrador(apps, schema_editor):
    users = apps.get_model('identidad', 'User').objects.using(schema_editor.connection.alias)
    admin = users.select_for_update().filter(username='administrador', is_staff=True).first()
    if admin and check_password('Prototipo2026!', admin.password):
        admin.password = make_password('AdminPluxee2026!')
        admin.save(using=schema_editor.connection.alias, update_fields=['password'])


class Migration(migrations.Migration):
    dependencies = [('identidad', '0002_demo_login_directo')]
    operations = [migrations.RunPython(separar_clave_administrador, migrations.RunPython.noop, atomic=True)]
