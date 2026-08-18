from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from despesas import views

urlpatterns = [

    path('admin/imprimir-siops/<int:questionario_id>/', views.gerar_pdf_questionario, name='admin_gerar_pdf'),
    path("admin/", admin.site.urls),

    path("webpush/", include("webpush.urls")),

    path("", include("despesas.urls")),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

