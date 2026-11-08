from django.core.management.base import BaseCommand

from users.models import LineSubscription
from users.subscription_service import apply_subscription_lifecycle


class Command(BaseCommand):
    help = 'Aplica reglas automáticas de suscripción B2B2C (piloto vencido, mora, suspensión).'

    def handle(self, *args, **options):
        updated = 0
        for subscription in LineSubscription.objects.select_related('line').iterator():
            if apply_subscription_lifecycle(subscription):
                updated += 1
                self.stdout.write(
                    f"Línea {subscription.line_id} ({subscription.line.name}): "
                    f"plan={subscription.plan} status={subscription.status}"
                )
        self.stdout.write(self.style.SUCCESS(f'Procesadas {LineSubscription.objects.count()} suscripciones; actualizadas {updated}.'))
