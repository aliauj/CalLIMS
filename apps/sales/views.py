from functools import wraps
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from apps.licensing.decorators import module_required
from .models import RFQ, RFQItem
from apps.clients.models import Client
from apps.assets.models import Instrument, InstrumentCategory


SALES_ROLES = ('SALES', 'MANAGER', 'ADMIN')
REVIEW_ROLES = ('MANAGER', 'ADMIN')


def sales_required(view_func):
    """Allow SALES, MANAGER, or ADMIN, and require the sales module license."""
    @wraps(view_func)
    @module_required('sales')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        if request.user.role not in SALES_ROLES:
            messages.error(request, 'Access denied. Sales, Manager, or Admin role required.')
            return redirect('workflows:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def review_required(view_func):
    """Allow MANAGER or ADMIN only, and require the sales module license."""
    @wraps(view_func)
    @module_required('sales')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        if request.user.role not in REVIEW_ROLES:
            messages.error(request, 'Access denied. Manager or Admin role required.')
            return redirect('sales:rfq_list')
        return view_func(request, *args, **kwargs)
    return wrapper


@sales_required
def rfq_list(request):
    qs = RFQ.objects.select_related('client', 'created_by', 'reviewed_by').order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if request.user.role == 'SALES':
        qs = qs.filter(created_by=request.user)
    return render(request, 'sales/rfq_list.html', {
        'rfqs': qs,
        'status_filter': status_filter,
        'status_choices': RFQ.Status.choices,
    })


@sales_required
def rfq_create(request):
    clients = Client.objects.filter(is_active=True).order_by('name')
    if request.method == 'POST':
        client_id = request.POST.get('client')
        client = get_object_or_404(Client, pk=client_id)
        rfq = RFQ.objects.create(
            client=client,
            priority=int(request.POST.get('priority', 2)),
            received_date=request.POST.get('received_date') or timezone.now().date(),
            required_by=request.POST.get('required_by') or None,
            contact_person=request.POST.get('contact_person', '').strip(),
            contact_email=request.POST.get('contact_email', '').strip(),
            contact_phone=request.POST.get('contact_phone', '').strip(),
            scope_description=request.POST.get('scope_description', '').strip(),
            notes=request.POST.get('notes', '').strip(),
            created_by=request.user,
        )
        _notify_managers_new_rfq(rfq)
        messages.success(request, f'RFQ {rfq.rfq_number} created. Add line items, then submit for review.')
        return redirect('sales:rfq_detail', pk=rfq.pk)
    return render(request, 'sales/rfq_create.html', {'clients': clients})


@sales_required
def rfq_detail(request, pk):
    rfq = get_object_or_404(
        RFQ.objects.select_related('client', 'created_by', 'reviewed_by'),
        pk=pk,
    )
    if request.user.role == 'SALES' and rfq.created_by_id != request.user.pk:
        messages.error(request, 'You can only view RFQs you created.')
        return redirect('sales:rfq_list')

    items = rfq.items.select_related('registered_instrument').order_by('sequence', 'pk')
    linked_instruments = rfq.instruments.select_related('category').order_by('asset_tag')
    available_instruments = Instrument.objects.filter(
        client=rfq.client,
    ).exclude(
        pk__in=linked_instruments.values_list('pk', flat=True),
    ).order_by('asset_tag')
    categories = InstrumentCategory.objects.all().order_by('name')

    return render(request, 'sales/rfq_detail.html', {
        'rfq': rfq,
        'items': items,
        'linked_instruments': linked_instruments,
        'available_instruments': available_instruments,
        'categories': categories,
        'can_review': request.user.role in REVIEW_ROLES,
    })


@sales_required
def rfq_add_item(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.status != RFQ.Status.PENDING:
        messages.error(request, 'Items can only be added to pending RFQs.')
        return redirect('sales:rfq_detail', pk=pk)
    if request.method == 'POST':
        next_seq = (rfq.items.order_by('-sequence').values_list('sequence', flat=True).first() or 0) + 1
        RFQItem.objects.create(
            rfq=rfq,
            sequence=next_seq,
            description=request.POST.get('description', '').strip(),
            manufacturer=request.POST.get('manufacturer', '').strip(),
            model_number=request.POST.get('model_number', '').strip(),
            serial_number=request.POST.get('serial_number', '').strip(),
            quantity=int(request.POST.get('quantity', 1) or 1),
            notes=request.POST.get('notes', '').strip(),
        )
        messages.success(request, 'Item added.')
    return redirect('sales:rfq_detail', pk=pk)


@sales_required
def rfq_delete_item(request, pk, item_pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == 'POST':
        rfq.items.filter(pk=item_pk).delete()
        messages.success(request, 'Item removed.')
    return redirect('sales:rfq_detail', pk=pk)


@review_required
def rfq_accept(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == 'POST':
        if rfq.status != RFQ.Status.PENDING:
            messages.error(request, f'Cannot accept: RFQ is {rfq.get_status_display()}.')
            return redirect('sales:rfq_detail', pk=pk)
        rfq.status = RFQ.Status.ACCEPTED
        rfq.reviewed_by = request.user
        rfq.reviewed_at = timezone.now()
        rfq.rejection_reason = ''
        rfq.save()
        _notify_sales_accepted(rfq)
        messages.success(request, f'RFQ {rfq.rfq_number} accepted. Sales can now register instruments.')
    return redirect('sales:rfq_detail', pk=pk)


@review_required
def rfq_reject(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == 'POST':
        if rfq.status != RFQ.Status.PENDING:
            messages.error(request, f'Cannot reject: RFQ is {rfq.get_status_display()}.')
            return redirect('sales:rfq_detail', pk=pk)
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'A rejection reason is required.')
            return redirect('sales:rfq_detail', pk=pk)
        rfq.status = RFQ.Status.REJECTED
        rfq.reviewed_by = request.user
        rfq.reviewed_at = timezone.now()
        rfq.rejection_reason = reason
        rfq.save()
        _notify_sales_rejected(rfq)
        messages.warning(request, f'RFQ {rfq.rfq_number} rejected.')
    return redirect('sales:rfq_detail', pk=pk)


@sales_required
def rfq_link_instrument(request, pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.status not in (RFQ.Status.ACCEPTED, RFQ.Status.READY_FOR_JOBS):
        messages.error(request, 'Instruments can only be linked to accepted RFQs.')
        return redirect('sales:rfq_detail', pk=pk)
    if request.method == 'POST':
        instrument_id = request.POST.get('instrument')
        if not instrument_id:
            messages.error(request, 'Pick an instrument.')
            return redirect('sales:rfq_detail', pk=pk)
        instrument = get_object_or_404(Instrument, pk=instrument_id, client=rfq.client)
        rfq.instruments.add(instrument)
        messages.success(request, f'{instrument.asset_tag} linked to this RFQ.')
    return redirect('sales:rfq_detail', pk=pk)


@sales_required
def rfq_unlink_instrument(request, pk, instrument_pk):
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == 'POST':
        if rfq.status not in (RFQ.Status.ACCEPTED, RFQ.Status.READY_FOR_JOBS):
            messages.error(request, 'Cannot modify instruments at this stage.')
            return redirect('sales:rfq_detail', pk=pk)
        instrument = get_object_or_404(Instrument, pk=instrument_pk)
        rfq.instruments.remove(instrument)
        messages.success(request, 'Instrument unlinked from RFQ.')
    return redirect('sales:rfq_detail', pk=pk)


@sales_required
def rfq_create_instrument(request, pk):
    """Register a brand-new instrument for the RFQ's client and link it."""
    rfq = get_object_or_404(RFQ, pk=pk)
    if rfq.status not in (RFQ.Status.ACCEPTED, RFQ.Status.READY_FOR_JOBS):
        messages.error(request, 'Instruments can only be registered against accepted RFQs.')
        return redirect('sales:rfq_detail', pk=pk)
    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        serial_number = request.POST.get('serial_number', '').strip()
        if not description or not serial_number:
            messages.error(request, 'Description and serial number are required.')
            return redirect('sales:rfq_detail', pk=pk)

        category_id = request.POST.get('category') or None
        category = None
        asset_tag = request.POST.get('asset_tag', '').strip()
        if category_id:
            category = get_object_or_404(InstrumentCategory, pk=category_id)
            if not asset_tag and category.code:
                asset_tag = category.next_tag()
        if not asset_tag:
            messages.error(request, 'Provide an asset tag, or pick a category that has a code so one can be auto-generated.')
            return redirect('sales:rfq_detail', pk=pk)

        if Instrument.objects.filter(asset_tag=asset_tag).exists():
            messages.error(request, f'Asset tag "{asset_tag}" already exists.')
            return redirect('sales:rfq_detail', pk=pk)

        instrument = Instrument.objects.create(
            asset_tag=asset_tag,
            serial_number=serial_number,
            description=description,
            manufacturer=request.POST.get('manufacturer', '').strip(),
            model_number=request.POST.get('model_number', '').strip(),
            category=category,
            client=rfq.client,
            status=Instrument.Status.DRAFT,
            created_by=request.user,
        )
        rfq.instruments.add(instrument)

        item_pk = request.POST.get('item_pk')
        if item_pk:
            RFQItem.objects.filter(pk=item_pk, rfq=rfq).update(registered_instrument=instrument)

        messages.success(request, f'Instrument {instrument.asset_tag} registered and linked to this RFQ.')
    return redirect('sales:rfq_detail', pk=pk)


@sales_required
def rfq_send_to_lab(request, pk):
    """Move RFQ to READY_FOR_JOBS and notify the lab manager(s) to create jobs."""
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.method == 'POST':
        if rfq.status != RFQ.Status.ACCEPTED:
            messages.error(request, 'Send to lab is only available for accepted RFQs.')
            return redirect('sales:rfq_detail', pk=pk)
        if not rfq.instruments.exists():
            messages.error(request, 'Register at least one instrument before sending to the lab.')
            return redirect('sales:rfq_detail', pk=pk)
        rfq.status = RFQ.Status.READY_FOR_JOBS
        rfq.sent_to_lab_at = timezone.now()
        rfq.save()
        _notify_managers_ready_for_jobs(rfq)
        messages.success(request, 'Lab manager has been notified to create jobs.')
    return redirect('sales:rfq_detail', pk=pk)


@sales_required
def rfq_delete(request, pk):
    """Delete an RFQ. Sales can delete their own pending/rejected; managers/admins any."""
    rfq = get_object_or_404(RFQ, pk=pk)
    if request.user.role == 'SALES':
        if rfq.created_by_id != request.user.pk:
            messages.error(request, 'You can only delete your own RFQs.')
            return redirect('sales:rfq_detail', pk=pk)
        if rfq.status not in (RFQ.Status.PENDING, RFQ.Status.REJECTED):
            messages.error(request, 'You can only delete pending or rejected RFQs.')
            return redirect('sales:rfq_detail', pk=pk)
    if request.method == 'POST':
        rfq_number = rfq.rfq_number
        rfq.delete()
        messages.success(request, f'RFQ {rfq_number} deleted.')
        return redirect('sales:rfq_list')
    return redirect('sales:rfq_detail', pk=pk)


# ── NOTIFICATION HELPERS ──────────────────────────────────────────

def _managers_and_admins():
    from apps.users.models import User
    return User.objects.filter(is_active=True, role__in=['MANAGER', 'ADMIN'])


def _notify_managers_new_rfq(rfq):
    from apps.notifications.models import Notification
    for mgr in _managers_and_admins():
        Notification.objects.create(
            recipient=mgr,
            notification_type=Notification.NotificationType.RFQ_NEW,
            title=f'New RFQ {rfq.rfq_number}',
            message=f'{rfq.created_by.get_full_name()} submitted an RFQ from {rfq.client.name} for review.',
            link=f'/sales/{rfq.pk}/',
        )


def _notify_sales_accepted(rfq):
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=rfq.created_by,
        notification_type=Notification.NotificationType.RFQ_ACCEPTED,
        title=f'RFQ {rfq.rfq_number} accepted',
        message=f'Your RFQ for {rfq.client.name} was accepted. You can now register the instruments.',
        link=f'/sales/{rfq.pk}/',
    )


def _notify_sales_rejected(rfq):
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=rfq.created_by,
        notification_type=Notification.NotificationType.RFQ_REJECTED,
        title=f'RFQ {rfq.rfq_number} rejected',
        message=f'Your RFQ for {rfq.client.name} was rejected. Reason: {rfq.rejection_reason[:200]}',
        link=f'/sales/{rfq.pk}/',
    )


def _notify_managers_ready_for_jobs(rfq):
    from apps.notifications.models import Notification
    count = rfq.instruments.count()
    for mgr in _managers_and_admins():
        Notification.objects.create(
            recipient=mgr,
            notification_type=Notification.NotificationType.RFQ_READY_FOR_JOBS,
            title=f'RFQ {rfq.rfq_number} — create jobs',
            message=f'{rfq.created_by.get_full_name()} registered {count} instrument(s) for {rfq.client.name}. Please create calibration jobs.',
            link=f'/sales/{rfq.pk}/',
        )
