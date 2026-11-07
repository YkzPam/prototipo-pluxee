from django.db import migrations


def habilitar_acceso_directo(apps, schema_editor):
    user = apps.get_model('identidad', 'User')
    user.objects.using(schema_editor.connection.alias).filter(
        username__in=('beneficiario', 'beneficiario2', 'sinmovimientos', 'administrador'),
        must_change_password=True,
    ).update(must_change_password=False)


class Migration(migrations.Migration):
    dependencies = [('identidad', '0001_initial')]
    operations = [migrations.RunPython(habilitar_acceso_directo, migrations.RunPython.noop, atomic=True)]
