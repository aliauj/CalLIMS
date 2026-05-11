from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CalibrationJob


@receiver(post_save, sender=CalibrationJob)
def on_job_completed(sender, instance, created, **kwargs):
    if not created and instance.status == 'completed':
        from apps.certificates.models import Certificate
        from django.utils import timezone
        import random
        import string

        if not hasattr(instance, 'certificate'):
            cert_num = (
                f"CERT-{timezone.now().strftime('%Y%m')}-"
                f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
            )
            cert = Certificate.objects.create(
                certificate_number=cert_num,
                job=instance,
                status=Certificate.Status.PENDING_SIGN,
                issue_date=timezone.now().date(),
            )
            from apps.certificates.tasks import generate_certificate_pdf
            generate_certificate_pdf.delay(cert.pk)
