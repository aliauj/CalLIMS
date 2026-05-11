from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import AuditLog


@login_required
def audit_log_list(request):
    qs = AuditLog.objects.select_related('user').order_by('-timestamp')[:200]
    return render(request, 'compliance/audit_log.html', {'logs': qs})
