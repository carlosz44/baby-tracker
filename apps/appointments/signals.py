import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Appointment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Appointment)
def sync_calendar_on_save(sender, instance, **kwargs):
    if instance.google_calendar_event_id:
        return

    try:
        from apps.accounts.models import User

        from .calendar_service import create_event

        users = User.objects.all()[:2]
        event_id = create_event(instance, users)
        if event_id:
            Appointment.objects.filter(pk=instance.pk).update(
                google_calendar_event_id=event_id
            )
    except Exception:
        logger.exception("Failed to create Google Calendar event for appointment %s", instance.pk)


@receiver(post_delete, sender=Appointment)
def sync_calendar_on_delete(sender, instance, **kwargs):
    if not instance.google_calendar_event_id:
        return

    try:
        from apps.accounts.models import User

        from .calendar_service import delete_event

        user = User.objects.first()
        if user:
            delete_event(user, instance.google_calendar_event_id)
    except Exception:
        logger.exception("Failed to delete Google Calendar event %s", instance.google_calendar_event_id)
