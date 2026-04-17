import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Appointment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Appointment)
def sync_calendar_on_save(sender, instance, **kwargs):
    try:
        from .calendar_service import sync_appointment

        sync_appointment(instance)
    except Exception:
        logger.exception("Failed to sync Google Calendar for appointment %s", instance.pk)


@receiver(post_delete, sender=Appointment)
def sync_calendar_on_delete(sender, instance, **kwargs):
    try:
        from .calendar_service import delete_appointment_events

        delete_appointment_events(instance)
    except Exception:
        logger.exception("Failed to delete Google Calendar events for appointment %s", instance.pk)
