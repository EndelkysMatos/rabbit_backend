from django.db import models


class Line(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lines'


class LineSubscription(models.Model):
    PLAN_CHOICES = [
        ('piloto', 'piloto'),
        ('basico', 'basico'),
        ('pro', 'pro'),
    ]
    STATUS_CHOICES = [
        ('activa', 'activa'),
        ('morosa', 'morosa'),
        ('suspendida', 'suspendida'),
    ]

    line = models.OneToOneField(
        Line,
        on_delete=models.CASCADE,
        db_column='id_line',
        related_name='subscription',
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='piloto')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='activa')
    started_at = models.DateTimeField()
    pilot_ends_at = models.DateTimeField(null=True, blank=True)
    next_billing_at = models.DateTimeField(null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'line_subscriptions'


class UserHasRoles(models.Model):
    id_user = models.ForeignKey('users.User', on_delete=models.CASCADE, db_column="id_user")
    id_rol = models.ForeignKey('roles.Role', on_delete=models.CASCADE, db_column="id_rol")

    class Meta:
        db_table = 'user_has_roles'
        unique_together = ('id_user', 'id_rol')


class User(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    lastname = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    image = models.CharField(max_length=255, null=True, blank=False)
    password = models.CharField(max_length=255)
    notification_token = models.CharField(max_length=255, null=True)
    line = models.ForeignKey(
        'users.Line',
        on_delete=models.SET_NULL,
        db_column='id_line',
        null=True,
        blank=True,
        related_name='users',
    )
    is_active = models.BooleanField(default=True)
    created_by_admin_linea = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        db_column='created_by_admin_linea',
        null=True,
        blank=True,
        related_name='created_drivers',
    )
    deactivated_by_admin_linea = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        db_column='deactivated_by_admin_linea',
        null=True,
        blank=True,
        related_name='deactivated_drivers',
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    roles = models.ManyToManyField('roles.Role', through='users.UserHasRoles', related_name='users')

    @property
    def is_authenticated(self):
        return True

    class Meta:
        db_table = 'users'