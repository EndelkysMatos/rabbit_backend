from datetime import timedelta

from django.db import migrations, models
import django.db.models.deletion


def seed_subscriptions_for_existing_lines(apps, schema_editor):
    from django.utils import timezone

    Line = apps.get_model('users', 'Line')
    LineSubscription = apps.get_model('users', 'LineSubscription')
    for line in Line.objects.all():
        if LineSubscription.objects.filter(line_id=line.id).exists():
            continue
        started = line.created_at or timezone.now()
        LineSubscription.objects.create(
            line_id=line.id,
            plan='piloto',
            status='activa',
            started_at=started,
            pilot_ends_at=started + timedelta(days=90),
            status_changed_at=started,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_seed_admin_linea_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='LineSubscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan', models.CharField(choices=[('piloto', 'piloto'), ('basico', 'basico'), ('pro', 'pro')], default='piloto', max_length=20)),
                ('status', models.CharField(choices=[('activa', 'activa'), ('morosa', 'morosa'), ('suspendida', 'suspendida')], default='activa', max_length=20)),
                ('started_at', models.DateTimeField()),
                ('pilot_ends_at', models.DateTimeField(blank=True, null=True)),
                ('next_billing_at', models.DateTimeField(blank=True, null=True)),
                ('last_payment_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('status_changed_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('line', models.OneToOneField(db_column='id_line', on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to='users.line')),
            ],
            options={
                'db_table': 'line_subscriptions',
            },
        ),
        migrations.RunPython(seed_subscriptions_for_existing_lines, migrations.RunPython.noop),
    ]
