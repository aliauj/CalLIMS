from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        CALIBRATION_DUE = 'CAL_DUE', 'Calibration Due'
        CALIBRATION_OVERDUE = 'CAL_OVERDUE', 'Calibration Overdue'
        JOB_ASSIGNED = 'JOB_ASSIGNED', 'Job Assigned'
        JOB_REVIEW_REQUESTED = 'JOB_REVIEW', 'Review Requested'
        JOB_REJECTED = 'JOB_REJECTED', 'Job Rejected'
        JOB_APPROVED = 'JOB_APPROVED', 'Job Approved'
        JOB_COMPLETED = 'JOB_COMPLETED', 'Job Completed'
        CERT_ISSUED = 'CERT_ISSUED', 'Certificate Issued'
        STD_EXPIRING = 'STD_EXPIRING', 'Standard Expiring'
        RFQ_NEW = 'RFQ_NEW', 'New RFQ Submitted'
        RFQ_ACCEPTED = 'RFQ_ACCEPTED', 'RFQ Accepted'
        RFQ_REJECTED = 'RFQ_REJECTED', 'RFQ Rejected'
        RFQ_READY_FOR_JOBS = 'RFQ_READY', 'RFQ Ready for Job Creation'
        SYSTEM = 'SYSTEM', 'System'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.notification_type} → {self.recipient}'
