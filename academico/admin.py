"""
Configuración de Django Admin para EdTech
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser,
    AreaConocimiento,
    Curso,
    CarroMatricula,
    ItemCarro,
    Matricula,
    DetalleMatricula,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'rol', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Información Académica', {'fields': ('rol', 'telefono')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Académica', {'fields': ('rol', 'telefono')}),
    )


@admin.register(AreaConocimiento)
class AreaConocimientoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'titulo',
        'area',
        'costo_matricula',
        'fecha_inicio',
        'fecha_termino',
        'cupos_disponibles',
        'cupos_maximos',
        'laboratorio',
        'cantidad_computadores',
        'activo',
    )
    list_filter = ('area', 'activo', 'laboratorio', 'fecha_inicio')
    search_fields = ('titulo', 'descripcion')


class ItemCarroInline(admin.TabularInline):
    model = ItemCarro
    extra = 0


@admin.register(CarroMatricula)
class CarroMatriculaAdmin(admin.ModelAdmin):
    list_display = ('id', 'estudiante', 'fecha_actualizacion')
    inlines = [ItemCarroInline]


class DetalleMatriculaInline(admin.TabularInline):
    model = DetalleMatricula
    extra = 0
    readonly_fields = ('precio_historico',)


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo_comprobante', 'estudiante', 'estado', 'total', 'fecha_creacion')
    list_filter = ('estado', 'fecha_creacion')
    search_fields = ('estudiante__username', 'estudiante__email')
    inlines = [DetalleMatriculaInline]
