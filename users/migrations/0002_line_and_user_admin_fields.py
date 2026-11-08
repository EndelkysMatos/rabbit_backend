from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Line',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'lines',
            },
        ),
        migrations.AddField(
            model_name='user',
            name='created_by_admin_linea',
            field=models.ForeignKey(
                blank=True,
                db_column='created_by_admin_linea',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_drivers',
                to='users.user',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='deactivated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='deactivated_by_admin_linea',
            field=models.ForeignKey(
                blank=True,
                db_column='deactivated_by_admin_linea',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='deactivated_drivers',
                to='users.user',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='user',
            name='line',
            field=models.ForeignKey(
                blank=True,
                db_column='id_line',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='users',
                to='users.line',
            ),
        ),
    ]
