from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AuditLog
from .middleware import AuditMiddleware


def _get_request_context():
    request = AuditMiddleware.get_current_request()
    if request is None:
        return None, None, ''
    user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
    ip = request.META.get('REMOTE_ADDR')
    ua = request.META.get('HTTP_USER_AGENT', '')
    return user, ip, ua


def log_audit(instance, action, old_values=None, new_values=None):
    user, ip, ua = _get_request_context()
    AuditLog.objects.create(
        user=user,
        action=action,
        app_label=instance._meta.app_label,
        model_name=instance._meta.model_name,
        object_id=str(instance.pk),
        object_repr=str(instance),
        old_values=old_values,
        new_values=new_values,
        ip_address=ip,
        user_agent=ua,
    )
