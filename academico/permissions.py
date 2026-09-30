"""
Permisos personalizados DRF para EdTech
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from rest_framework import permissions


class IsCoordinador(permissions.BasePermission):
    """
    Permite el acceso únicamente a usuarios con rol COORDINADOR, staff o superusuarios.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.rol == 'COORDINADOR' or request.user.is_staff or request.user.is_superuser)
        )


class IsEstudiante(permissions.BasePermission):
    """
    Permite el acceso a usuarios autenticados que son estudiantes.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.rol == 'ESTUDIANTE'
        )
