from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from apps.licensing.decorators import module_required
from apps.users.permissions import lab_staff_required
from .models import Client


@login_required
@lab_staff_required
@module_required('clients')
def client_list(request):
    clients = Client.objects.all().order_by('name')
    return render(request, 'clients/client_list.html', {'clients': clients})


@login_required
@lab_staff_required
@module_required('clients')
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    instruments = client.instruments.all().order_by('asset_tag')
    return render(request, 'clients/client_detail.html', {'client': client, 'instruments': instruments})


@login_required
@lab_staff_required
@module_required('clients')
def client_create(request):
    if request.method == 'POST':
        Client.objects.create(
            name=request.POST['name'],
            client_type=request.POST.get('client_type', 'EXTERNAL'),
            contact_person=request.POST.get('contact_person', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            address=request.POST.get('address', ''),
        )
        messages.success(request, 'Client created successfully.')
        return redirect('clients:client_list')
    return render(request, 'clients/client_create.html', {'client_types': Client.ClientType.choices})
