from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('apps.users.urls', namespace='users')),
    path('dashboard/', include('apps.workflows.urls', namespace='workflows')),
    path('instruments/', include('apps.assets.urls', namespace='instruments')),
    path('standards/', include('apps.standards.urls', namespace='standards')),
    path('certificates/', include('apps.certificates.urls', namespace='certificates')),
    path('clients/', include('apps.clients.urls', namespace='clients')),
    path('portal/', include('apps.portal.urls', namespace='portal')),
    path('compliance/', include('apps.compliance.urls', namespace='compliance')),
    path('manage/', include('apps.administration.urls', namespace='administration')),
    path('proficiency/', include('apps.proficiency.urls', namespace='proficiency')),
    path('nonconformance/', include('apps.nonconformance.urls', namespace='nonconformance')),
    path('sales/', include('apps.sales.urls', namespace='sales')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('license/', include('apps.licensing.urls', namespace='licensing')),
    path('', include('apps.workflows.urls_home')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
