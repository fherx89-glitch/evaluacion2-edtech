"""
URL Configuration for EdTech Platform
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from academico.views import CustomTokenObtainPairView, custom_404_view

urlpatterns = [
    # Panel de administración de Django
    path('admin/', admin.site.urls),

    # Autenticación JWT con claims personalizados
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Documentación Swagger / OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Rutas de la aplicación Académico (Web y API)
    path('', include('academico.urls')),

    # Captura universal de rutas no encontradas (Error 404 estructurado con datos del alumno)
    re_path(r'^.*$', custom_404_view, name='custom_404'),
]

# Manejador global de 404
handler404 = 'academico.views.custom_404_view'
