from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import Line, LineSubscription
from users.subscription_service import create_pilot_subscription


@receiver(post_save, sender=Line)
def ensure_line_subscription(sender, instance, created, **kwargs):
    if not created:
        return
    if LineSubscription.objects.filter(line_id=instance.id).exists():
        return
    create_pilot_subscription(instance)
