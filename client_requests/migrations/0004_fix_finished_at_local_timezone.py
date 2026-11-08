from datetime import timezone as dt_tz
from zoneinfo import ZoneInfo

from django.db import migrations

CARACAS = ZoneInfo('America/Caracas')


def fix_misstored_finished_at(apps, schema_editor):
    """
    MySQL NOW() guardaba hora local (Caracas) en finished_at; Django la lee como UTC.
    Corrige filas donde la fecha Caracas derivada no coincide con la fecha en BD.
    """
    ClientRequest = apps.get_model('client_requests', 'ClientRequest')
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, finished_at
            FROM client_requests
            WHERE status = 'FINISHED' AND finished_at IS NOT NULL
            """
        )
        rows = cursor.fetchall()

    for trip_id, naive_dt in rows:
        if naive_dt is None:
            continue
        wrongly_utc = naive_dt.replace(tzinfo=dt_tz.utc)
        caracas_date_wrong = wrongly_utc.astimezone(CARACAS).date()
        mysql_date = naive_dt.date()
        if caracas_date_wrong == mysql_date:
            continue
        correct = naive_dt.replace(tzinfo=CARACAS).astimezone(dt_tz.utc)
        ClientRequest.objects.filter(pk=trip_id).update(finished_at=correct)


class Migration(migrations.Migration):

    dependencies = [
        ('client_requests', '0003_clientrequest_finished_at'),
    ]

    operations = [
        migrations.RunPython(fix_misstored_finished_at, migrations.RunPython.noop),
    ]
