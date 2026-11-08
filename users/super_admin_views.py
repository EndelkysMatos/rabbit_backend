from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import bcrypt

from roles.models import Role
from users.models import Line, LineSubscription, User, UserHasRoles
from users.subscription_service import (
    PLAN_BASICO,
    PLAN_PILOTO,
    PLAN_PRO,
    STATUS_ACTIVA,
    STATUS_MOROSA,
    STATUS_SUSPENDIDA,
    _set_status,
    apply_plan_change,
    build_subscription_payload,
    record_manual_payment,
)

ADMIN_LINEA_ROLE_ID = 'ADMIN_LINEA'
RABBIT_SUPER_ROLE_ID = 'RABBIT_SUPER'
VALID_PLANS = {PLAN_PILOTO, PLAN_BASICO, PLAN_PRO}
VALID_STATUSES = {STATUS_ACTIVA, STATUS_MOROSA, STATUS_SUSPENDIDA}


def _rabbit_super_or_403(request):
    user = User.objects.filter(id=request.user.id).first()
    if not user:
        return None, Response({'message': 'Usuario no encontrado'}, status=status.HTTP_401_UNAUTHORIZED)
    if not UserHasRoles.objects.filter(
        id_user_id=user.id,
        id_rol_id=RABBIT_SUPER_ROLE_ID,
    ).exists():
        roles = list(
            UserHasRoles.objects.filter(id_user_id=user.id).values_list('id_rol_id', flat=True)
        )
        return None, Response(
            {
                'message': 'No tienes permisos de super-admin Rabbit',
                'email': user.email,
                'roles': roles,
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    if not user.is_active:
        return None, Response({'message': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
    return user, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def super_admin_me(request):
    user, err = _rabbit_super_or_403(request)
    if err:
        return err
    roles = list(
        UserHasRoles.objects.filter(id_user_id=user.id).values_list('id_rol_id', flat=True)
    )
    return Response(
        {
            'id': user.id,
            'email': user.email,
            'roles': roles,
            'is_super_admin': True,
        },
        status=status.HTTP_200_OK,
    )


def _parse_optional_datetime(value):
    if value is None or value == '':
        return None, None
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None, Response(
            {'message': 'Fecha inválida; use ISO-8601'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed, None


def _get_line_subscription_or_404(line_id):
    line = Line.objects.filter(id=line_id).first()
    if not line:
        return None, None, Response({'message': 'Línea no encontrada'}, status=status.HTTP_404_NOT_FOUND)
    subscription = LineSubscription.objects.filter(line_id=line.id).first()
    if not subscription:
        from users.subscription_service import create_pilot_subscription

        subscription = create_pilot_subscription(line)
    return line, subscription, None


def _line_payload(line):
    return {
        'id': line.id,
        'name': line.name,
        'created_at': line.created_at,
        'updated_at': line.updated_at,
        'subscription': build_subscription_payload(line.id),
    }


def _create_admin_for_line(line, data):
    name = (data.get('name') or '').strip()
    lastname = (data.get('lastname') or '').strip()
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    password = data.get('password')

    if not all([name, lastname, email, phone, password]):
        return None, Response(
            {'message': 'name, lastname, email, phone y password son obligatorios para el admin'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email=email).exists():
        return None, Response(
            {'message': 'El email ya está registrado'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    role = Role.objects.filter(id=ADMIN_LINEA_ROLE_ID).first()
    if role is None:
        return None, Response(
            {'message': 'Rol ADMIN_LINEA no configurado'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    hashed_password = bcrypt.hashpw(
        str(password).encode('utf-8'), bcrypt.gensalt()
    ).decode('utf-8')
    admin_user = User.objects.create(
        name=name,
        lastname=lastname,
        email=email,
        phone=phone,
        password=hashed_password,
        line_id=line.id,
        is_active=True,
    )
    UserHasRoles.objects.create(id_user=admin_user, id_rol=role)
    return admin_user, None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_lines_for_super_admin(request):
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    if request.method == 'GET':
        results = [_line_payload(line) for line in Line.objects.order_by('name')]
        return Response(results, status=status.HTTP_200_OK)

    name = (request.data.get('name') or '').strip()
    if not name:
        return Response({'message': 'name es obligatorio'}, status=status.HTTP_400_BAD_REQUEST)
    if Line.objects.filter(name__iexact=name).exists():
        return Response(
            {'message': 'Ya existe una línea con ese nombre'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    line = Line.objects.create(name=name)

    admin_data = request.data.get('admin')
    created_admin = None
    if isinstance(admin_data, dict) and admin_data:
        admin_user, admin_err = _create_admin_for_line(line, admin_data)
        if admin_err:
            line.delete()
            return admin_err
        created_admin = _line_admin_payload(admin_user)

    response = {
        'success': True,
        'line': _line_payload(line),
        'message': f'Línea "{line.name}" creada con plan Piloto (1 mes).',
    }
    if created_admin:
        response['admin'] = created_admin

    return Response(response, status=status.HTTP_201_CREATED)


def _line_admin_payload(user):
    return {
        'id': user.id,
        'name': user.name,
        'lastname': user.lastname,
        'email': user.email,
        'phone': user.phone,
        'is_active': user.is_active,
        'created_at': user.created_at,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def line_admins(request, id_line):
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    line = Line.objects.filter(id=id_line).first()
    if not line:
        return Response({'message': 'Línea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        admins = (
            User.objects.filter(
                line_id=line.id,
                userhasroles__id_rol_id=ADMIN_LINEA_ROLE_ID,
            )
            .distinct()
            .order_by('name', 'lastname')
        )
        return Response(
            [_line_admin_payload(admin) for admin in admins],
            status=status.HTTP_200_OK,
        )

    name = (request.data.get('name') or '').strip()
    lastname = (request.data.get('lastname') or '').strip()
    email = (request.data.get('email') or '').strip().lower()
    phone = (request.data.get('phone') or '').strip()
    password = request.data.get('password')

    admin_user, admin_err = _create_admin_for_line(
        line,
        {
            'name': name,
            'lastname': lastname,
            'email': email,
            'phone': phone,
            'password': password,
        },
    )
    if admin_err:
        return admin_err

    return Response(
        {
            'success': True,
            'admin': _line_admin_payload(admin_user),
            'line': {'id': line.id, 'name': line.name},
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def patch_line_subscription(request, id_line):
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    line, subscription, line_err = _get_line_subscription_or_404(id_line)
    if line_err:
        return line_err

    plan = request.data.get('plan')
    new_status = request.data.get('status')
    notes = request.data.get('notes')
    next_billing_at_raw = request.data.get('next_billing_at')
    last_payment_at_raw = request.data.get('last_payment_at')

    if (
        plan is None
        and new_status is None
        and notes is None
        and next_billing_at_raw is None
        and last_payment_at_raw is None
    ):
        return Response({'message': 'No se enviaron datos para actualizar'}, status=status.HTTP_400_BAD_REQUEST)

    if plan is not None:
        if plan not in VALID_PLANS:
            return Response({'message': 'plan debe ser piloto, basico o pro'}, status=status.HTTP_400_BAD_REQUEST)
        apply_plan_change(subscription, plan)

    if new_status is not None:
        if new_status not in VALID_STATUSES:
            return Response(
                {'message': 'status debe ser activa, morosa o suspendida'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _set_status(subscription, new_status)

    if notes is not None:
        subscription.notes = notes

    if next_billing_at_raw is not None:
        next_billing_at, dt_err = _parse_optional_datetime(next_billing_at_raw)
        if dt_err:
            return dt_err
        subscription.next_billing_at = next_billing_at

    if last_payment_at_raw is not None:
        last_payment_at, dt_err = _parse_optional_datetime(last_payment_at_raw)
        if dt_err:
            return dt_err
        subscription.last_payment_at = last_payment_at

    subscription.save()
    return Response(
        {'line_id': line.id, 'subscription': build_subscription_payload(line.id)},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_line_subscription(request, id_line):
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    line, subscription, line_err = _get_line_subscription_or_404(id_line)
    if line_err:
        return line_err

    _set_status(subscription, STATUS_ACTIVA)
    subscription.save()
    return Response({'success': True, 'subscription': build_subscription_payload(line.id)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suspend_line_subscription(request, id_line):
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    line, subscription, line_err = _get_line_subscription_or_404(id_line)
    if line_err:
        return line_err

    _set_status(subscription, STATUS_SUSPENDIDA)
    subscription.save()
    return Response({'success': True, 'subscription': build_subscription_payload(line.id)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_line_payment(request, id_line):
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    line, subscription, line_err = _get_line_subscription_or_404(id_line)
    if line_err:
        return line_err

    plan = request.data.get('plan')
    notes = request.data.get('notes')
    payment_at_raw = request.data.get('last_payment_at')
    payment_at, dt_err = _parse_optional_datetime(payment_at_raw) if payment_at_raw else (timezone.now(), None)
    if dt_err:
        return dt_err

    if plan is not None and plan not in VALID_PLANS:
        return Response({'message': 'plan debe ser piloto, basico o pro'}, status=status.HTTP_400_BAD_REQUEST)

    record_manual_payment(subscription, plan=plan, payment_at=payment_at, notes=notes)
    return Response({'success': True, 'subscription': build_subscription_payload(line.id)}, status=status.HTTP_200_OK)


def _perform_delete_line(line):
    from driver_position.models import DriverPosition

    driver_ids = list(
        User.objects.filter(line_id=line.id).values_list('id', flat=True)
    )
    if driver_ids:
        DriverPosition.objects.filter(id_driver_id__in=driver_ids).delete()

    admin_users = User.objects.filter(
        line_id=line.id,
        userhasroles__id_rol_id=ADMIN_LINEA_ROLE_ID,
    ).distinct()
    deactivated_admins = admin_users.count()
    for admin in admin_users:
        admin.line_id = None
        admin.is_active = False
        admin.save(update_fields=['line_id', 'is_active'])

    User.objects.filter(line_id=line.id).update(line_id=None)

    line_name = line.name
    line.delete()

    return Response(
        {
            'success': True,
            'message': (
                f'Línea "{line_name}" eliminada. '
                f'{deactivated_admins} admin(es) de línea desactivado(s). '
                'Conductores y demás usuarios quedaron sin línea asignada.'
            ),
            'deactivated_admins': deactivated_admins,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_line_by_id(request):
    """Eliminar línea por JSON body: {"line_id": 5}. Ruta fija para evitar conflictos."""
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    line_id = request.data.get('line_id')
    if line_id is None:
        return Response({'message': 'line_id es requerido'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        line_id = int(line_id)
    except (TypeError, ValueError):
        return Response({'message': 'line_id inválido'}, status=status.HTTP_400_BAD_REQUEST)

    line = Line.objects.filter(id=line_id).first()
    if not line:
        return Response({'message': 'Línea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    try:
        return _perform_delete_line(line)
    except Exception as exc:
        return Response(
            {'message': f'No se pudo eliminar la línea: {exc}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['DELETE', 'POST'])
@permission_classes([IsAuthenticated])
def delete_line(request, id_line):
    _, err = _rabbit_super_or_403(request)
    if err:
        return err

    line = Line.objects.filter(id=id_line).first()
    if not line:
        return Response({'message': 'Línea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    try:
        return _perform_delete_line(line)
    except Exception as exc:
        return Response(
            {'message': f'No se pudo eliminar la línea: {exc}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
