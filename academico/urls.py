"""
URLs para la aplicación Académico
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import anular_matricula_estudiante, anular_matricula_coordinador

# Router para ViewSets de DRF
router = DefaultRouter()
router.register(r'areas', views.AreaConocimientoViewSet, basename='api-areas')
router.register(r'cursos', views.CursoViewSet, basename='api-cursos')

urlpatterns = [
    # =========================================================================
    # RUTAS WEB (HTML FRONTEND)
    # =========================================================================
    path('', views.catalogo_view, name='catalogo'),
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_estudiante_view, name='registro_estudiante'),
    path('logout/', views.logout_view, name='logout'),
    path('carro/', views.carro_view, name='carro'),
    path('mi-carro/', views.carro_view, name='mi_carro'),
    path('carro/agregar/<int:curso_id>/', views.agregar_al_carro_view, name='agregar_carro'),
    path('carro/eliminar/<int:item_id>/', views.eliminar_del_carro_view, name='eliminar_carro'),
    path('carro/vaciar/', views.vaciar_carro_view, name='vaciar_carro'),
    path('carro/checkout/', views.procesar_matricula_web_view, name='checkout_web'),
    path('mis-matriculas/', views.mis_matriculas_view, name='mis_matriculas'),
    # ¿Por qué rutas separadas para anulación (estudiante vs coordinador)?:
    # Segrega los privilegios por rol (RBAC): 'anular_matricula_estudiante' permite retracto legal
    # pre-inicio validando propiedad, mientras que 'anular_matricula_coordinador' exige motivo institucional.
    path('matricula/<int:matricula_id>/anular/', anular_matricula_estudiante, name='anular_matricula_estudiante'),
    path('coordinador/', views.panel_coordinador_view, name='panel_coordinador'),
    path('coordinador/matricula/<int:matricula_id>/anular/', anular_matricula_coordinador, name='anular_matricula_coordinador'),
    path('coordinador/matricula/<int:matricula_id>/cambiar-estado/', views.cambiar_estado_matricula_web_view, name='cambiar_estado_web'),
    path('coordinador/curso/<int:curso_id>/cerrar-cupos/', views.cerrar_cupos_curso_view, name='cerrar_cupos_curso'),
    path('coordinador/curso/<int:curso_id>/restablecer-cupos/', views.restablecer_cupos_curso_view, name='restablecer_cupos_curso'),
    path('coordinador/matricula/<int:matricula_id>/cancelar/', views.cancelar_matricula_coordinador_view, name='cancelar_matricula_coordinador'),
    path('coordinador/curso/nuevo/', views.crear_curso_coordinador_view, name='crear_curso_coordinador'),
    path('coordinador/curso/<int:curso_id>/editar/', views.editar_curso_coordinador_view, name='editar_curso_coordinador'),
    path('coordinador/curso/<int:curso_id>/eliminar/', views.eliminar_curso_coordinador_view, name='eliminar_curso_coordinador'),

    # =========================================================================
    # RUTAS API REST ('api/...')
    # =========================================================================
    path('api/', include(router.urls)),
    path('api/carro/', views.CarroMatriculaAPIView.as_view(), name='api-carro'),
    path('api/carro/item/<int:item_id>/', views.EliminarItemCarroAPIView.as_view(), name='api-carro-eliminar-item'),
    path('api/matricula/confirmar/', views.ConfirmarMatriculaAPIView.as_view(), name='api-confirmar-matricula'),
    path('api/mis-matriculas/', views.MisMatriculasAPIView.as_view(), name='api-mis-matriculas'),
    path('api/matriculas/<int:pk>/cambiar-estado/', views.CambiarEstadoMatriculaAPIView.as_view(), name='api-cambiar-estado-matricula'),
]
