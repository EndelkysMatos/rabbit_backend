from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from users.models import Line, LineSubscription, User, UserHasRoles

PLAN_PILOTO = 'piloto'
PLAN_BASICO = 'basico'
PLAN_PRO = 'pro'

STATUS_ACTIVA = 'activa'
STATUS_MOROSA = 'morosa'
STATUS_SUSPENDIDA = 'suspendida'

DRIVER_ROLE_ID = 'DRIVER'
ADMIN_LINEA_ROLE_ID = 'ADMIN_LINEA'
RABBIT_SUPER_ROLE_ID = 'RABBIT_SUPER'

LINE_SUSPENDED_MESSAGE = 'Tu línea está suspendida. Contacte con Rabbit.'
LINE_SUSPENDED_BLOCK_MESSAGE = LINE_SUSPENDED_MESSAGE

PILOT_MAX_DRIVERS = getattr(settings, 'SUBSCRIPTION_PILOT_MAX_DRIVERS', 15)
PILOT_DURATION_DAYS = getattr(settings, 'SUBSCRIPTION_PILOT_DAYS', 90)
GRACE_DAYS = getattr(settings, 'SUBSCRIPTION_GRACE_DAYS', 7)
MOROSA_TO_SUSPEND_DAYS = getattr(settings, 'SUBSCRIPTION_MOROSA_TO_SUSPEND_DAYS', 15)


def count_active_drivers(line_id):
    return (
        User.objects.filter(
            line_id=line_id,
            is_active=True,
            userhasroles__id_rol_id=DRIVER_ROLE_ID,
        )
        .distinct()
        .count()
    )


def get_subscription_for_line(line_id, create_if_missing=True):
    try:
        return LineSubscription.objects.select_related('line').get(line_id=line_id)
    except LineSubscription.DoesNotExist:
        if not create_if_missing:
            return None
        line = Line.objects.filter(id=line_id).first()
        if not line:
            return None
        return create_pilot_subscription(line)


def create_pilot_subscription(line):
    now = timezone.now()
    return LineSubscription.objects.create(
        line=line,
        plan=PLAN_PILOTO,
        status=STATUS_ACTIVA,
        started_at=now,
        pilot_ends_at=now + timedelta(days=PILOT_DURATION_DAYS),
        next_billing_at=None,
        last_payment_at=None,
        status_changed_at=now,
    )


def _set_status(subscription, new_status):
    if subscription.status != new_status:
        subscription.status = new_status
        subscription.status_changed_at = timezone.now()


def apply_subscription_lifecycle(subscription):
    """Apply automatic morosa/suspendida transitions. Returns True if saved."""
    if not subscription:
        return False

    now = timezone.now()
    changed = False

    if subscription.plan == PLAN_PILOTO and subscription.status == STATUS_ACTIVA:
        if subscription.pilot_ends_at and now > subscription.pilot_ends_at:
            _set_status(subscription, STATUS_MOROSA)
            if not subscription.next_billing_at:
                subscription.next_billing_at = subscription.pilot_ends_at
            changed = True

    if subscription.plan in (PLAN_BASICO, PLAN_PRO) and subscription.status == STATUS_ACTIVA:
        if subscription.next_billing_at and now > subscription.next_billing_at + timedelta(days=GRACE_DAYS):
            _set_status(subscription, STATUS_MOROSA)
            changed = True

    if subscription.status == STATUS_MOROSA and subscription.status_changed_at:
        if now > subscription.status_changed_at + timedelta(days=MOROSA_TO_SUSPEND_DAYS):
            _set_status(subscription, STATUS_SUSPENDIDA)
            changed = True

    if changed:
        subscription.save()
    return changed


def ensure_subscription_fresh(line_id):
    subscription = get_subscription_for_line(line_id)
    if subscription:
        apply_subscription_lifecycle(subscription)
        subscription.refresh_from_db()
        normalize_subscription_plan_fields(subscription)
        subscription.refresh_from_db()
    return subscription


def max_drivers_for_plan(plan):
    if plan == PLAN_PILOTO:
        return PILOT_MAX_DRIVERS
    return None


def days_until_pilot_end(subscription):
    if not subscription or subscription.plan != PLAN_PILOTO or not subscription.pilot_ends_at:
        return None
    delta = (subscription.pilot_ends_at.date() - timezone.now().date()).days
    return max(delta, 0)


def days_until_next_billing(subscription):
    if not subscription or subscription.plan not in (PLAN_BASICO, PLAN_PRO) or not subscription.next_billing_at:
        return None
    delta = (subscription.next_billing_at.date() - timezone.now().date()).days
    return max(delta, 0)


def normalize_subscription_plan_fields(subscription):
    """Keep pilot-only fields aligned with the current plan (fixes stale DB rows)."""
    if not subscription:
        return subscription

    changed = False
    if subscription.plan in (PLAN_BASICO, PLAN_PRO) and subscription.pilot_ends_at is not None:
        subscription.pilot_ends_at = None
        changed = True

    if changed:
        subscription.save(update_fields=['pilot_ends_at', 'updated_at'])
    return subscription


def apply_plan_change(subscription, new_plan, payment_at=None):
    """Update subscription when plan changes; keeps pilot vs paid fields consistent."""
    if not subscription or new_plan not in (PLAN_PILOTO, PLAN_BASICO, PLAN_PRO):
        return subscription

    old_plan = subscription.plan
    if new_plan == old_plan:
        return normalize_subscription_plan_fields(subscription)

    now = payment_at or timezone.now()
    subscription.plan = new_plan

    if new_plan in (PLAN_BASICO, PLAN_PRO):
        subscription.pilot_ends_at = None
        if old_plan == PLAN_PILOTO or not subscription.next_billing_at:
            subscription.next_billing_at = now + timedelta(days=30)
        if old_plan == PLAN_PILOTO and not subscription.last_payment_at:
            subscription.last_payment_at = now
    elif new_plan == PLAN_PILOTO and not subscription.pilot_ends_at:
        base = subscription.started_at or now
        subscription.pilot_ends_at = base + timedelta(days=PILOT_DURATION_DAYS)

    subscription.save()
    return subscription


def build_subscription_payload(line_id):
    subscription = ensure_subscription_fresh(line_id)
    active_drivers_count = count_active_drivers(line_id)
    max_drivers = max_drivers_for_plan(subscription.plan)
    is_pilot = subscription.plan == PLAN_PILOTO
    is_paid = subscription.plan in (PLAN_BASICO, PLAN_PRO)

    return {
        'plan': subscription.plan,
        'status': subscription.status,
        'started_at': subscription.started_at,
        'pilot_ends_at': subscription.pilot_ends_at if is_pilot else None,
        'next_billing_at': subscription.next_billing_at,
        'last_payment_at': subscription.last_payment_at,
        'days_until_pilot_end': days_until_pilot_end(subscription) if is_pilot else None,
        'days_until_next_billing': days_until_next_billing(subscription) if is_paid else None,
        'max_drivers': max_drivers,
        'active_drivers_count': active_drivers_count,
    }


def line_suspended_block_message(user):
    """Block ADMIN_LINEA/DRIVER login and API use when their line is suspendida."""
    if not user or not user.line_id:
        return None
    if UserHasRoles.objects.filter(id_user=user, id_rol_id=RABBIT_SUPER_ROLE_ID).exists():
        return None
    subscription = ensure_subscription_fresh(user.line_id)
    if subscription.status != STATUS_SUSPENDIDA:
        return None
    is_line_operator = UserHasRoles.objects.filter(
        id_user=user,
        id_rol_id__in=[ADMIN_LINEA_ROLE_ID, DRIVER_ROLE_ID],
    ).exists()
    if not is_line_operator:
        return None
    return LINE_SUSPENDED_BLOCK_MESSAGE


def validate_can_create_driver(line_id):
    subscription = ensure_subscription_fresh(line_id)
    if subscription.status == STATUS_SUSPENDIDA:
        return False, LINE_SUSPENDED_MESSAGE

    if subscription.plan == PLAN_PILOTO:
        active = count_active_drivers(line_id)
        if active >= PILOT_MAX_DRIVERS:
            return False, f'Límite del plan Piloto ({PILOT_MAX_DRIVERS} conductores)'

    return True, None


def driver_line_can_receive_new_trips(driver):
    if not driver or not driver.line_id:
        return True
    subscription = ensure_subscription_fresh(driver.line_id)
    return subscription.status != STATUS_SUSPENDIDA


def record_manual_payment(subscription, plan=None, payment_at=None, notes=None):
    now = payment_at or timezone.now()
    subscription.last_payment_at = now
    subscription.next_billing_at = now + timedelta(days=30)

    if plan in (PLAN_BASICO, PLAN_PRO, PLAN_PILOTO):
        target_plan = plan
    elif subscription.plan == PLAN_PILOTO:
        target_plan = PLAN_BASICO
    else:
        target_plan = subscription.plan

    if target_plan in (PLAN_BASICO, PLAN_PRO):
        subscription.pilot_ends_at = None
    subscription.plan = target_plan

    _set_status(subscription, STATUS_ACTIVA)
    if notes is not None:
        subscription.notes = notes
    subscription.save()
    return subscription


def build_line_payload(line):
    return {
        'id': line.id,
        'name': line.name,
        'created_at': line.created_at,
        'updated_at': line.updated_at,
        'subscription': build_subscription_payload(line.id),
    }
