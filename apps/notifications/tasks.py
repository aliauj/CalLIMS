from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def check_calibration_due_dates():
    """Check instruments due for calibration and create notifications."""
    from apps.assets.models import Instrument
    from apps.notifications.models import Notification

    today = timezone.now().date()
    thresholds = [30, 14, 7]

    for days in thresholds:
        target_date = today + timezone.timedelta(days=days)
        instrument_list = Instrument.objects.filter(
            next_calibration_date=target_date,
            status__in=['ACTIVE', 'CALIBRATED'],
        ).select_related('client', 'created_by')

        for instr in instrument_list:
            recipient = instr.created_by
            Notification.objects.get_or_create(
                recipient=recipient,
                notification_type='CAL_DUE',
                title=f'Calibration due in {days} days: {instr.asset_tag}',
                defaults={
                    'message': (
                        f'Instrument {instr.asset_tag} ({instr.description}) is due for calibration on '
                        f'{instr.next_calibration_date}. Please schedule a calibration job.'
                    ),
                    'link': f'/instruments/{instr.pk}/',
                },
            )


@shared_task
def check_overdue_calibrations():
    """Flag instruments past their calibration due date."""
    from apps.assets.models import Instrument
    from apps.notifications.models import Notification
    from apps.users.models import User

    today = timezone.now().date()
    overdue = Instrument.objects.filter(
        next_calibration_date__lt=today,
        status='ACTIVE',
    ).select_related('created_by')

    managers = User.objects.filter(role__in=['ADMIN', 'MANAGER'])
    for instr in overdue:
        for manager in managers:
            Notification.objects.get_or_create(
                recipient=manager,
                notification_type='CAL_OVERDUE',
                title=f'OVERDUE: {instr.asset_tag}',
                defaults={
                    'message': (
                        f'Instrument {instr.asset_tag} ({instr.description}) was due for calibration on '
                        f'{instr.next_calibration_date} and is now overdue.'
                    ),
                    'link': f'/instruments/{instr.pk}/',
                },
            )


@shared_task
def check_expiring_standards():
    """Notify about reference standards expiring within 30 days."""
    from apps.standards.models import ReferenceStandard
    from apps.notifications.models import Notification
    from apps.users.models import User

    today = timezone.now().date()
    threshold = today + timezone.timedelta(days=30)
    expiring = ReferenceStandard.objects.filter(
        calibration_due_date__lte=threshold,
        calibration_due_date__gte=today,
        status='ACTIVE',
    ).select_related('custodian')

    managers = User.objects.filter(role__in=['ADMIN', 'MANAGER'])
    for std in expiring:
        days_left = (std.calibration_due_date - today).days
        recipients = list(managers)
        if std.custodian:
            recipients.append(std.custodian)
        for recipient in recipients:
            Notification.objects.get_or_create(
                recipient=recipient,
                notification_type='STD_EXPIRING',
                title=f'Standard expiring in {days_left}d: {std.serial_number}',
                defaults={
                    'message': (
                        f'Reference standard {std.serial_number} ({std.name}) expires on '
                        f'{std.calibration_due_date} ({days_left} days remaining).'
                    ),
                    'link': f'/standards/{std.pk}/',
                },
            )


@shared_task
def send_certificate_email(certificate_id):
    """Send certificate notification email to client."""
    from apps.certificates.models import Certificate

    try:
        cert = Certificate.objects.select_related(
            'job__instrument__client', 'signed_by'
        ).get(pk=certificate_id)
        client = cert.job.instrument.client
        if client and client.email:
            send_mail(
                subject=f'Calibration Certificate {cert.certificate_number} Ready',
                message=(
                    f'Dear {client.contact_person or client.name},\n\n'
                    f'Your calibration certificate {cert.certificate_number} for '
                    f'{cert.job.instrument.description} (S/N: {cert.job.instrument.serial_number}) '
                    f'is now available.\n\n'
                    f'Please log in to your client portal to download the certificate.\n\n'
                    f'CalLIMS System'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[client.email],
                fail_silently=True,
            )
    except Certificate.DoesNotExist:
        pass
