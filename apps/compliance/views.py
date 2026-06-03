from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from apps.licensing.decorators import module_required
from .models import AuditLog


@login_required
@module_required('compliance')
def audit_log_list(request):
    if request.user.role not in ('ADMIN', 'MANAGER', 'AUDITOR'):
        return HttpResponseForbidden('Access restricted to Admin, Manager, or Auditor roles.')
    qs = AuditLog.objects.select_related('user').order_by('-timestamp')[:200]
    return render(request, 'compliance/audit_log.html', {'logs': qs})
