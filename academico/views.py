"""
Vistas API REST y Vistas Web HTML - Plataforma EdTech
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from decimal import Decimal
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST, require_http_methods
from django.core.exceptions import ValidationError
from django.utils import timezone
import django_filters

# DRF Imports
from rest_framework import status, viewsets, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

# Local Models, Serializers & Permissions
from .models import (
    AreaConocimiento,
    Curso,
    CarroMatricula,
    ItemCarro,
    Matricula,
    DetalleMatricula,
    CustomUser,
)
from .serializers import (
    CustomTokenObtainPairSerializer,
    AreaConocimientoSerializer,
    CursoSerializer,
    CarroMatriculaSerializer,
    AgregarItemCarroSerializer,
    MatriculaSerializer,
    CheckoutSerializer,
    CambiarEstadoMatriculaSerializer,
)
from .permissions import IsCoordinador, IsEstudiante


# ==============================================================================
# FILTRO DJANGO-FILTERS PARA CURSOS
# ==============================================================================
class CursoFilter(django_filters.FilterSet):
    """
    Filtro avanzado para cursos por área, costo exacto o rangos de costo.
    """
    min_costo = django_filters.NumberFilter(field_name='costo_matricula', lookup_expr='gte')
    max_costo = django_filters.NumberFilter(field_name='costo_matricula', lookup_expr='lte')

    class Meta:
        model = Curso
        fields = ['area', 'costo_matricula', 'activo']


# ==============================================================================
# SECCIÓN 1: VISTAS API REST (DJANGO REST FRAMEWORK + DRF SPECTACULAR)
# ==============================================================================

@extend_schema(tags=['Autenticación'])
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Autenticación JWT personalizada con claims: role, username, nombre_alumno, seccion, anio.
    """
    serializer_class = CustomTokenObtainPairSerializer


@extend_schema(tags=['Áreas de Conocimiento'])
class AreaConocimientoViewSet(viewsets.ModelViewSet):
    """
    CRUD de Áreas de Conocimiento para categorizar la oferta académica.
    """
    queryset = AreaConocimiento.objects.all().order_by('nombre')
    serializer_class = AreaConocimientoSerializer
    filterset_fields = ['nombre']
    search_fields = ['nombre', 'descripcion']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsCoordinador()]
        return [permissions.AllowAny()]


@extend_schema(tags=['Cursos y Bootcamps'])
class CursoViewSet(viewsets.ModelViewSet):
    """
    List / Retrieve público con django-filters por área y costo.
    CRUD completo para usuarios con rol Coordinador.
    """
    queryset = Curso.objects.select_related('area').filter(activo=True).order_by('fecha_inicio', 'titulo')
    serializer_class = CursoSerializer
    filterset_class = CursoFilter
    search_fields = ['titulo', 'descripcion', 'area__nombre']
    ordering_fields = ['costo_matricula', 'fecha_inicio', 'cupos_disponibles']

    def get_queryset(self):
        qs = super().get_queryset()
        # Si es coordinador o staff, permite visualizar todos los cursos
        if self.request.user.is_authenticated and (self.request.user.is_staff or getattr(self.request.user, 'rol', None) == 'COORDINADOR'):
            qs = Curso.objects.select_related('area').all().order_by('fecha_inicio', 'titulo')
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsCoordinador()]
        return [permissions.AllowAny()]


@extend_schema(tags=['Carro de Matrícula'])
class CarroMatriculaAPIView(APIView):
    """
    Gestión del carro: GET carro, POST agregar item sin duplicar, DELETE vaciar carro.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Obtener carro del estudiante autenticado",
        responses={200: CarroMatriculaSerializer}
    )
    def get(self, request):
        carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
        serializer = CarroMatriculaSerializer(carro)
        return Response(serializer.data)

    @extend_schema(
        summary="Agregar un curso al carro (sin duplicar y validando cupos > 0)",
        request=AgregarItemCarroSerializer,
        responses={201: CarroMatriculaSerializer, 400: OpenApiResponse(description="Error de validación")}
    )
    def post(self, request):
        serializer = AgregarItemCarroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        curso_id = serializer.validated_data['curso_id']

        curso = get_object_or_404(Curso, pk=curso_id, activo=True)
        carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)

        # 1. Validar que no se duplique en el carro
        if ItemCarro.objects.filter(carro=carro, curso=curso).exists():
            return Response(
                {'error': 'El curso ya se encuentra en su carro de matrícula.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Validar que no esté ya matriculado con estado PAGADO
        ya_matriculado = DetalleMatricula.objects.filter(
            matricula__estudiante=request.user,
            matricula__estado=Matricula.ESTADO_PAGADO,
            curso=curso
        ).exists()
        if ya_matriculado:
            return Response(
                {'error': 'Ya posees una matrícula activa y pagada en este curso.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Validar cupos disponibles > 0
        if curso.cupos_disponibles <= 0:
            return Response(
                {'error': 'No existen cupos disponibles para este curso.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ItemCarro.objects.create(carro=carro, curso=curso)
        response_serializer = CarroMatriculaSerializer(carro)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Vaciar carro de matrícula",
        responses={200: OpenApiResponse(description="Carro vaciado exitosamente")}
    )
    def delete(self, request):
        carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
        cantidad = carro.items.count()
        carro.items.all().delete()
        return Response(
            {'mensaje': f'Carro vaciado exitosamente. Se eliminaron {cantidad} cursos.', 'items_restantes': 0},
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Carro de Matrícula'])
class EliminarItemCarroAPIView(APIView):
    """
    DELETE: Elimina un ítem específico del carro de matrícula.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Eliminar un ítem individual del carro",
        responses={200: OpenApiResponse(description="Ítem eliminado")}
    )
    def delete(self, request, item_id):
        carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
        item = get_object_or_404(ItemCarro, pk=item_id, carro=carro)
        curso_titulo = item.curso.titulo
        item.delete()
        return Response(
            {'mensaje': f'El curso "{curso_titulo}" fue removido de tu carro.'},
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Matrículas'])
class ConfirmarMatriculaAPIView(APIView):
    """
    ConfirmarMatricula: POST checkout con transaction.atomic:
    Valida cupos > 0, crea Matricula PAGADO, descuenta 1 cupo por curso y limpia el carro.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Confirmar y procesar matrícula (Checkout Atómico)",
        request=CheckoutSerializer,
        responses={201: MatriculaSerializer, 400: OpenApiResponse(description="Falta de cupos o carro vacío")}
    )
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user

        try:
            # ¿Por qué utilizamos transaction.atomic() aquí?:
            # Garantiza las propiedades ACID en la compra. Si ocurre un fallo en el descuento
            # de cupos o creación de detalles, toda la transacción se revierte (rollback)
            # evitando que el carro se vacíe sin haber generado la matrícula.
            with transaction.atomic():
                # ¿Por qué select_for_update() en el carro?:
                # Aplica un bloqueo pesimista a nivel SQL (SELECT ... FOR UPDATE) en la fila
                # del carro del usuario para evitar compras dobles simultáneas.
                carro = CarroMatricula.objects.select_for_update().get(estudiante=user)
                items = list(carro.items.select_related('curso').all())

                if not items:
                    return Response(
                        {'error': 'Tu carro de matrícula se encuentra vacío.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # ¿Por qué bloqueamos los cursos con select_for_update()?:
                # Evita condiciones de carrera (Race Conditions): si a un curso le queda 1 cupo
                # y 10 alumnos intentan pagar en el mismo milisegundo, la base de datos atiende
                # a cada uno en serie. El primero descuenta el cupo y los siguientes reciben
                # el error de cupos agotados de forma segura e inmediata.
                cursos_ids = [item.curso.id for item in items]
                cursos_bloqueados = {
                    c.id: c for c in Curso.objects.select_for_update().filter(id__in=cursos_ids)
                }

                # 1. Validación de cupos > 0
                cursos_sin_cupo = []
                for item in items:
                    curso_obj = cursos_bloqueados.get(item.curso.id)
                    if not curso_obj or curso_obj.cupos_disponibles <= 0:
                        cursos_sin_cupo.append(item.curso.titulo)

                if cursos_sin_cupo:
                    return Response(
                        {
                            'error': 'No fue posible completar la matrícula: cupos agotados.',
                            'cursos_agotados': cursos_sin_cupo,
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # 2. Descontar 1 cupo por curso y calcular total
                total_matricula = Decimal('0.00')
                for item in items:
                    curso_obj = cursos_bloqueados[item.curso.id]
                    curso_obj.cupos_disponibles -= 1
                    curso_obj.save(update_fields=['cupos_disponibles'])
                    total_matricula += curso_obj.costo_matricula

                # 3. Crear Matricula con estado PAGADO
                matricula = Matricula.objects.create(
                    estudiante=user,
                    estado=Matricula.ESTADO_PAGADO,
                    total=total_matricula
                )

                # 4. Crear Detalles de Matrícula (Precio histórico)
                for item in items:
                    curso_obj = cursos_bloqueados[item.curso.id]
                    DetalleMatricula.objects.create(
                        matricula=matricula,
                        curso=curso_obj,
                        precio_historico=curso_obj.costo_matricula
                    )

                # 5. Limpiar el carro
                carro.items.all().delete()

            response_serializer = MatriculaSerializer(matricula)
            return Response(
                {
                    'mensaje': 'Matrícula formalizada y pagada con éxito.',
                    'matricula': response_serializer.data,
                    'nombre_alumno': 'Fernando Pailahueque',
                    'seccion': 'AP-N4-C2',
                    'anio': 2026,
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': f'Error interno al procesar la matrícula: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['Matrículas'])
class MisMatriculasAPIView(generics.ListAPIView):
    """
    MisMatriculas: GET historial del estudiante.
    """
    serializer_class = MatriculaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Matricula.objects.none()
        return Matricula.objects.filter(
            estudiante=self.request.user
        ).prefetch_related('detalles__curso', 'detalles__curso__area').order_by('-fecha_creacion')


@extend_schema(tags=['Matrículas'])
class CambiarEstadoMatriculaAPIView(APIView):
    """
    Coordinador: PATCH cambiar estado matricula reponiendo cupos si CANCELADO.
    """
    permission_classes = [permissions.IsAuthenticated, IsCoordinador]

    @extend_schema(
        summary="Cambiar estado de una matrícula (con reposición de cupos si CANCELADO)",
        request=CambiarEstadoMatriculaSerializer,
        responses={200: MatriculaSerializer, 400: OpenApiResponse(description="Error en el cambio de estado")}
    )
    def patch(self, request, pk):
        matricula = get_object_or_404(Matricula, pk=pk)
        serializer = CambiarEstadoMatriculaSerializer(matricula, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        nuevo_estado = serializer.validated_data['estado']
        estado_anterior = matricula.estado

        if nuevo_estado == estado_anterior:
            return Response(
                {'mensaje': f'La matrícula ya se encontraba en estado {nuevo_estado}.', 'matricula': MatriculaSerializer(matricula).data},
                status=status.HTTP_200_OK
            )

        with transaction.atomic():
            detalles = matricula.detalles.select_related('curso').all()

            # Caso 1: Se cancela o anula una matrícula previamente PAGADA o PENDIENTE -> REPOSICIÓN DE CUPOS
            if nuevo_estado in [Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA] and estado_anterior not in [Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA]:
                for detalle in detalles:
                    curso = Curso.objects.select_for_update().get(pk=detalle.curso_id)
                    if curso.cupos_disponibles < curso.cupos_maximos:
                        curso.cupos_disponibles += 1
                        curso.save(update_fields=['cupos_disponibles'])
                if nuevo_estado == Matricula.ESTADO_ANULADA:
                    matricula.fecha_anulacion = timezone.now()
                    matricula.anulado_por = request.user
                    matricula.motivo_anulacion = "Anulación administrativa vía API"

            # Caso 2: Se reactiva una matrícula CANCELADA o ANULADA a PAGADO -> VALIDAR Y DESCONTAR CUPOS
            elif estado_anterior in [Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA] and nuevo_estado == Matricula.ESTADO_PAGADO:
                for detalle in detalles:
                    curso = Curso.objects.select_for_update().get(pk=detalle.curso_id)
                    if curso.cupos_disponibles <= 0:
                        return Response(
                            {'error': f'No es posible reactivar la matrícula: El curso "{curso.titulo}" no posee cupos disponibles.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    curso.cupos_disponibles -= 1
                    curso.save(update_fields=['cupos_disponibles'])

            matricula.estado = nuevo_estado
            if nuevo_estado == Matricula.ESTADO_ANULADA:
                matricula.save(update_fields=['estado', 'fecha_anulacion', 'anulado_por', 'motivo_anulacion'])
            else:
                matricula.save(update_fields=['estado'])

        return Response(
            {
                'mensaje': f'Estado de matrícula #{matricula.id} actualizado a {nuevo_estado} con éxito.',
                'matricula': MatriculaSerializer(matricula).data
            },
            status=status.HTTP_200_OK
        )


# ==============================================================================
# SECCIÓN 2: VISTAS WEB HTML (FRONTEND ESCOLAR CON BOOTSTRAP 5)
# ==============================================================================

def login_view(request):
    """
    Vista de inicio de sesión visual.
    """
    if request.user.is_authenticated:
        return redirect('catalogo')

    if request.method == 'POST':
        usuario = request.POST.get('username', '').strip()
        clave = request.POST.get('password', '')

        user = authenticate(request, username=usuario, password=clave)
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido de vuelta, {user.first_name or user.username}!')
            next_url = request.GET.get('next') or 'catalogo'
            return redirect(next_url)
        else:
            messages.error(request, 'Credenciales inválidas. Por favor verifique su usuario y contraseña.')

    return render(request, 'academico/login.html')


def registro_estudiante_view(request):
    """
    Vista de registro público de nuevos Estudiantes.
    - Rol FIJO asignado por código: 'ESTUDIANTE' (sin selector de roles).
    - Hasheo seguro de contraseña: user.set_password(password).
    - Creación de su carro individual: CarroMatricula.objects.create(estudiante=user).
    - Mensaje flash al completar y redirección a 'login'.
    """
    if request.user.is_authenticated:
        return redirect('catalogo')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        nombre_completo = request.POST.get('nombre_completo', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        # Validaciones de campos obligatorios
        if not username or not password or not confirm_password:
            messages.error(request, 'Por favor complete todos los campos obligatorios.')
            return render(request, 'academico/registro.html', {
                'username': username,
                'nombre_completo': nombre_completo,
                'email': email,
            })

        if password != confirm_password:
            messages.error(request, 'Las contraseñas no coinciden. Por favor verifíquelas.')
            return render(request, 'academico/registro.html', {
                'username': username,
                'nombre_completo': nombre_completo,
                'email': email,
            })

        if len(password) < 4:
            messages.error(request, 'La contraseña debe contener al menos 4 caracteres.')
            return render(request, 'academico/registro.html', {
                'username': username,
                'nombre_completo': nombre_completo,
                'email': email,
            })

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, f'El nombre de usuario "{username}" ya está registrado. Por favor elija otro.')
            return render(request, 'academico/registro.html', {
                'nombre_completo': nombre_completo,
                'email': email,
            })

        if email and CustomUser.objects.filter(email=email).exists():
            messages.error(request, f'El correo electrónico "{email}" ya se encuentra registrado.')
            return render(request, 'academico/registro.html', {
                'username': username,
                'nombre_completo': nombre_completo,
            })

        # Descomponer nombre completo si viene compuesto
        first_name = nombre_completo
        last_name = ''
        if ' ' in nombre_completo:
            first_name, last_name = nombre_completo.split(' ', 1)

        # ¿Por qué asignamos rol = CustomUser.ROLE_ESTUDIANTE directamente en el backend?:
        # Principio de menor privilegio y seguridad contra inyección de parámetros (Mass Assignment).
        # Un usuario público jamás debe poder elegir su propio rol desde el frontend.
        user = CustomUser(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            rol=CustomUser.ROLE_ESTUDIANTE,
            is_staff=False,
            is_superuser=False
        )

        # ¿Por qué user.set_password() en lugar de asignación directa?:
        # Aplica el algoritmo criptográfico PBKDF2 con hash SHA-256 y salt aleatorio nativo de Django,
        # garantizando que la contraseña jamás se almacene en texto plano en la base de datos.
        user.set_password(password)
        user.save()

        # ¿Por qué inicializamos CarroMatricula inmediatamente?:
        # Garantiza la integridad de la relación OneToOneField para que el estudiante
        # pueda interactuar con el carrito apenas inicie sesión sin generar errores por registros inexistentes.
        CarroMatricula.objects.create(estudiante=user)

        messages.success(request, f'¡Cuenta de estudiante creada con éxito! Ya puedes iniciar sesión con tu usuario "{username}".')
        return redirect('login')

    return render(request, 'academico/registro.html')


def logout_view(request):
    """
    Cierre de sesión.
    """
    logout(request)
    messages.info(request, 'Has cerrado tu sesión académica exitosamente.')
    return redirect('login')


def catalogo_view(request):
    """
    Home '/': listado visual de cursos con botón para agregar al carro y badges de cupos disponibles.
    """
    query = request.GET.get('q', '').strip()
    area_id = request.GET.get('area', '').strip()

    # ¿Por qué el filtro estricto Curso.objects.filter(activo=True)?:
    # Garantiza que el catálogo público para visitantes y postulantes solo liste programas vigentes.
    # Los cursos archivados (activo=False) se ocultan totalmente para prevenir nuevas solicitudes de matrícula,
    # resguardando la integridad operativa sin afectar a quienes ya se matricularon históricamente.
    cursos = Curso.objects.select_related('area').filter(activo=True)

    if query:
        cursos = cursos.filter(
            Q(titulo__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(area__nombre__icontains=query)
        )

    if area_id and area_id.isdigit():
        cursos = cursos.filter(area_id=int(area_id))

    areas = AreaConocimiento.objects.all().order_by('nombre')

    cursos_en_carro_ids = set()
    cursos_matriculados_ids = set()

    if request.user.is_authenticated:
        carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
        cursos_en_carro_ids = set(carro.items.values_list('curso_id', flat=True))

        cursos_matriculados_ids = set(
            DetalleMatricula.objects.filter(
                matricula__estudiante=request.user,
                matricula__estado=Matricula.ESTADO_PAGADO
            ).values_list('curso_id', flat=True)
        )

    context = {
        'cursos': cursos,
        'areas': areas,
        'selected_area': int(area_id) if area_id.isdigit() else None,
        'search_query': query,
        'cursos_en_carro_ids': cursos_en_carro_ids,
        'cursos_matriculados_ids': cursos_matriculados_ids,
    }
    return render(request, 'academico/catalogo.html', context)

# Alias para compatibilidad de rutas
portal_cursos_view = catalogo_view
catalogo_cursos = catalogo_view


@login_required
def carro_view(request):
    """
    Vista '/carro/' y '/mi-carro/': tabla del carro con botón para confirmar matrícula.
    """
    carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
    items = carro.items.select_related('curso', 'curso__area').all()
    alguno_sin_cupo = any(item.curso.cupos_disponibles <= 0 for item in items)

    context = {
        'carro': carro,
        'items': items,
        'total': carro.total,
        'alguno_sin_cupo': alguno_sin_cupo,
    }
    return render(request, 'academico/carro.html', context)


@login_required
def agregar_al_carro_view(request, curso_id):
    """
    Agrega un curso al carro de matrícula del estudiante logueado.
    """
    # ¿Por qué colocamos esta validación de rol al inicio (Fail-Fast)?:
    # Si el usuario es COORDINADOR, se interrumpe la ejecución de inmediato sin realizar
    # lecturas pesadas a la base de datos ni consultar el carro. Se le informa con un
    # mensaje de tipo warning y se le redirige al catálogo.
    if request.user.is_authenticated and (getattr(request.user, 'role', None) == 'COORDINADOR' or getattr(request.user, 'rol', None) == 'COORDINADOR' or getattr(request.user, 'is_coordinador', False)):
        messages.warning(request, 'Acción no permitida: Los coordinadores académicos no pueden agregar cursos al carro')
        return redirect('catalogo')

    curso = get_object_or_404(Curso, pk=curso_id, activo=True)
    carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)

    ya_matriculado = DetalleMatricula.objects.filter(
        matricula__estudiante=request.user,
        matricula__estado=Matricula.ESTADO_PAGADO,
        curso=curso
    ).exists()
    if ya_matriculado:
        messages.warning(request, f'Ya te encuentras matriculado oficialmente en "{curso.titulo}".')
        return redirect('catalogo')

    if curso.cupos_disponibles <= 0:
        messages.error(request, f'Lo sentimos, el curso "{curso.titulo}" no cuenta con cupos disponibles.')
        return redirect('catalogo')

    item, creado = ItemCarro.objects.get_or_create(carro=carro, curso=curso)
    if creado:
        messages.success(request, f'¡Curso "{curso.titulo}" agregado al carro con éxito!')
    else:
        messages.info(request, f'El curso "{curso.titulo}" ya estaba en tu carro de matrícula.')

    return redirect('carro')


@login_required
def eliminar_del_carro_view(request, item_id):
    """
    Elimina un ítem específico del carro de matrícula.
    """
    carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
    item = get_object_or_404(ItemCarro, pk=item_id, carro=carro)
    titulo = item.curso.titulo
    item.delete()
    messages.info(request, f'Curso "{titulo}" eliminado de tu carro.')
    return redirect('carro')


@login_required
def vaciar_carro_view(request):
    """
    Vacía todos los cursos del carro de matrícula.
    """
    carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
    cantidad = carro.items.count()
    carro.items.all().delete()
    messages.info(request, f'Se han eliminado todos los cursos ({cantidad}) de tu carro.')
    return redirect('carro')


@login_required
@require_POST
def procesar_matricula_web_view(request):
    """
    Procesa la matrícula desde el frontend web utilizando transaction.atomic().
    """
    user = request.user

    try:
        with transaction.atomic():
            carro = CarroMatricula.objects.select_for_update().get(estudiante=user)
            items = list(carro.items.select_related('curso').all())

            if not items:
                messages.warning(request, 'Tu carro de matrícula está vacío.')
                return redirect('carro')

            cursos_ids = [item.curso.id for item in items]
            cursos_bloqueados = {
                c.id: c for c in Curso.objects.select_for_update().filter(id__in=cursos_ids)
            }

            sin_cupo = [item.curso.titulo for item in items if cursos_bloqueados[item.curso.id].cupos_disponibles <= 0]
            if sin_cupo:
                messages.error(request, f'No es posible formalizar la matrícula. Cursos sin cupo: {", ".join(sin_cupo)}')
                return redirect('carro')

            total = Decimal('0.00')
            for item in items:
                curso_obj = cursos_bloqueados[item.curso.id]
                curso_obj.cupos_disponibles -= 1
                curso_obj.save(update_fields=['cupos_disponibles'])
                total += curso_obj.costo_matricula

            matricula = Matricula.objects.create(
                estudiante=user,
                estado=Matricula.ESTADO_PAGADO,
                total=total
            )

            for item in items:
                curso_obj = cursos_bloqueados[item.curso.id]
                DetalleMatricula.objects.create(
                    matricula=matricula,
                    curso=curso_obj,
                    precio_historico=curso_obj.costo_matricula
                )

            carro.items.all().delete()

        messages.success(request, f'¡Felicitaciones! Tu matrícula #{matricula.id:05d} fue procesada con éxito.')
        return redirect('mis_matriculas')

    except Exception as e:
        messages.error(request, f'Ocurrió un error al procesar tu matrícula: {str(e)}')
        return redirect('carro')


@login_required
def mis_matriculas_view(request):
    """
    mis_matriculas_view ('/mis-matriculas/'): historial de cursos pagados.
    """
    matriculas = Matricula.objects.filter(
        estudiante=request.user
    ).prefetch_related('detalles__curso', 'detalles__curso__area').order_by('-fecha_creacion')

    total_invertido = matriculas.filter(estado=Matricula.ESTADO_PAGADO).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')
    total_cursos = DetalleMatricula.objects.filter(
        matricula__estudiante=request.user,
        matricula__estado=Matricula.ESTADO_PAGADO
    ).count()

    context = {
        'matriculas': matriculas,
        'total_invertido': total_invertido,
        'total_cursos': total_cursos,
    }
    return render(request, 'academico/mis_matriculas.html', context)


@login_required
def panel_coordinador_view(request):
    """
    Panel de Coordinación Académica.
    """
    if not (request.user.is_coordinador or request.user.is_staff):
        messages.error(request, 'Acceso restringido: Se requieren permisos de Coordinador Académico.')
        return redirect('catalogo')

    # ¿Por qué segmentar cursos_activos y cursos_archivados?:
    # Permite al directivo supervisar el catálogo activo en tiempo real sin perder de vista
    # los programas históricos retirados. Además, el cálculo de métricas de ocupación y cupos
    # se ejecuta estrictamente sobre 'cursos_activos' para no distorsionar la capacidad operativa actual del campus.
    cursos_activos = Curso.objects.select_related('area').filter(activo=True).order_by('area__nombre', 'titulo')
    cursos_archivados = Curso.objects.select_related('area').filter(activo=False).order_by('-fecha_desactivacion', 'titulo')
    matriculas = Matricula.objects.select_related('estudiante').prefetch_related('detalles__curso').all().order_by('-fecha_creacion')

    total_estudiantes = CustomUser.objects.filter(rol=CustomUser.ROLE_ESTUDIANTE).count()
    total_cupos_ofertados = cursos_activos.aggregate(Sum('cupos_maximos'))['cupos_maximos__sum'] or 0
    total_cupos_disponibles = cursos_activos.aggregate(Sum('cupos_disponibles'))['cupos_disponibles__sum'] or 0
    total_cupos_ocupados = max(0, total_cupos_ofertados - total_cupos_disponibles)
    total_recaudado = matriculas.filter(estado=Matricula.ESTADO_PAGADO).aggregate(Sum('total'))['total__sum'] or Decimal('0.00')

    context = {
        'cursos': cursos_activos,
        'cursos_activos': cursos_activos,
        'cursos_archivados': cursos_archivados,
        'matriculas': matriculas,
        'total_estudiantes': total_estudiantes,
        'total_cupos_ofertados': total_cupos_ofertados,
        'total_cupos_disponibles': total_cupos_disponibles,
        'total_cupos_ocupados': total_cupos_ocupados,
        'total_recaudado': total_recaudado,
        'areas': AreaConocimiento.objects.all().order_by('nombre'),
    }
    return render(request, 'academico/panel_coordinador.html', context)


# ¿Por qué esta vista y su control de acceso RBAC?:
# 1. @login_required: Garantiza que la sesión del usuario directivo exista y sea válida.
# 2. Verificación estricta de rol directivo (u.role == 'COORDINADOR' o u.is_staff): Previene
#    vulnerabilidades de escalamiento vertical de privilegios (Privilege Escalation), asegurando que
#    usuarios con rol ESTUDIANTE o anónimos no puedan aprovisionar cuentas de directivos.
# 3. Procesamiento exclusivo vía POST: Protege contra peticiones predecibles o prefetching de navegadores.
# 4. Hashing con set_password(): Aplica criptografía PBKDF2 con SHA-256 para almacenamiento seguro de credenciales.
# 5. Redirección institucional: Retorna siempre a 'panel_coordinador' con feedback mediante django.contrib.messages.
@login_required
def crear_coordinador(request):
    """
    Vista protegida para el alta exclusiva de nuevos Coordinadores Académicos bajo arquitectura RBAC.
    """
    # 1. Verificación estricta de rol COORDINADOR (u.role == 'COORDINADOR' o u.is_staff)
    if not (getattr(request.user, 'role', None) == 'COORDINADOR' or getattr(request.user, 'rol', None) == 'COORDINADOR' or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acceso restringido: Se requieren permisos de Coordinador Académico para realizar esta acción.')
        return redirect('panel_coordinador')

    # 2. Procesar exclusivamente vía POST
    if request.method != 'POST':
        return redirect('panel_coordinador')

    username = request.POST.get('username', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    nombre_completo = request.POST.get('nombre_completo', '').strip()
    email = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    confirm_password = request.POST.get('confirm_password', '')

    # Soporte unificado si el nombre se envía compuesto o separado
    if nombre_completo and not (first_name or last_name):
        if ' ' in nombre_completo:
            first_name, last_name = nombre_completo.split(' ', 1)
        else:
            first_name = nombre_completo
            last_name = ''
    elif not nombre_completo and (first_name or last_name):
        nombre_completo = f"{first_name} {last_name}".strip()

    # 3. Validar campos obligatorios
    if not username or not password or not confirm_password:
        messages.error(request, 'Por favor complete todos los campos obligatorios.')
        return redirect('panel_coordinador')

    # 4. Validar que las contraseñas coincidan
    if password != confirm_password:
        messages.error(request, 'Las contraseñas no coinciden. Por favor verifíquelas.')
        return redirect('panel_coordinador')

    # 5. Validar longitud mínima de contraseña (al menos 4 caracteres)
    if len(password) < 4:
        messages.error(request, 'La contraseña debe contener al menos 4 caracteres.')
        return redirect('panel_coordinador')

    # 6. Validar que el username no exista previamente
    if CustomUser.objects.filter(username=username).exists():
        messages.error(request, f'El nombre de usuario "{username}" ya está registrado. Por favor elija otro.')
        return redirect('panel_coordinador')

    # 7. Validar que el email no exista previamente
    if email and CustomUser.objects.filter(email=email).exists():
        messages.error(request, f'El correo electrónico "{email}" ya se encuentra registrado.')
        return redirect('panel_coordinador')

    # 8. Instanciar CustomUser con role='COORDINADOR', encriptar clave con set_password() y guardar
    nuevo_coordinador = CustomUser(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        rol=CustomUser.ROLE_COORDINADOR,
        role=CustomUser.ROLE_COORDINADOR,
    )
    nuevo_coordinador.set_password(password)
    nuevo_coordinador.save()

    messages.success(request, f'¡Coordinador "{username}" dado de alta exitosamente en la plataforma!')
    return redirect('panel_coordinador')



@login_required
@require_POST
def cambiar_estado_matricula_web_view(request, matricula_id):
    """
    Acción web para cambiar el estado de una matrícula reponiendo cupos si se cancela.
    """
    if not (request.user.is_coordinador or request.user.is_staff):
        messages.error(request, 'No tienes permisos de coordinador.')
        return redirect('catalogo')

    matricula = get_object_or_404(Matricula, pk=matricula_id)
    nuevo_estado = request.POST.get('nuevo_estado')
    estado_anterior = matricula.estado

    if nuevo_estado not in [Matricula.ESTADO_PENDIENTE, Matricula.ESTADO_PAGADO, Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA]:
        messages.error(request, 'Estado seleccionado no válido.')
        return redirect('panel_coordinador')

    if nuevo_estado == estado_anterior:
        messages.info(request, f'La matrícula #{matricula.id} ya se encontraba en estado {nuevo_estado}.')
        return redirect('panel_coordinador')

    with transaction.atomic():
        detalles = matricula.detalles.select_related('curso').all()

        if nuevo_estado in [Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA] and estado_anterior not in [Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA]:
            for detalle in detalles:
                c = Curso.objects.select_for_update().get(pk=detalle.curso_id)
                if c.cupos_disponibles < c.cupos_maximos:
                    c.cupos_disponibles += 1
                    c.save(update_fields=['cupos_disponibles'])
            messages.success(request, f'Matrícula #{matricula.id} {nuevo_estado}. Se repusieron los cupos a los cursos asociados.')
            if nuevo_estado == Matricula.ESTADO_ANULADA:
                matricula.fecha_anulacion = timezone.now()
                matricula.anulado_por = request.user
                matricula.motivo_anulacion = "Anulación administrativa vía selector"

        elif estado_anterior in [Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA] and nuevo_estado == Matricula.ESTADO_PAGADO:
            for detalle in detalles:
                c = Curso.objects.select_for_update().get(pk=detalle.curso_id)
                if c.cupos_disponibles <= 0:
                    messages.error(request, f'No se puede reactivar: el curso "{c.titulo}" no posee cupos disponibles.')
                    return redirect('panel_coordinador')
                c.cupos_disponibles -= 1
                c.save(update_fields=['cupos_disponibles'])
            messages.success(request, f'Matrícula #{matricula.id} reactivada como PAGADO. Cupos descontados.')
        else:
            messages.success(request, f'Estado de matrícula #{matricula.id} modificado a {nuevo_estado}.')

        matricula.estado = nuevo_estado
        if nuevo_estado == Matricula.ESTADO_ANULADA:
            matricula.save(update_fields=['estado', 'fecha_anulacion', 'anulado_por', 'motivo_anulacion'])
        else:
            matricula.save(update_fields=['estado'])

    return redirect('panel_coordinador')


# ¿Por qué usamos estos tres decoradores?:
# 1. @login_required: Garantiza que la sesión exista y sea válida.
# 2. @user_passes_test: Verifica que el usuario sea estrictamente COORDINADOR o Staff.
# 3. @require_POST: Protege contra ataques CSRF y prefetching de navegadores; una acción
#    administrativa destructiva (como agotar o abrir cupos) JAMÁS debe ser un método GET.
@login_required
@user_passes_test(lambda u: u.is_authenticated and (getattr(u, 'role', None) == 'COORDINADOR' or getattr(u, 'rol', None) == 'COORDINADOR' or u.is_staff or u.is_superuser), login_url='catalogo')
@require_POST
def cerrar_cupos_curso_view(request, curso_id):
    """
    Vista rápida para coordinadores: setea cupos_disponibles = 0 para cerrar matrícula.
    """
    curso = get_object_or_404(Curso, pk=curso_id)
    curso.cupos_disponibles = 0
    curso.save(update_fields=['cupos_disponibles'])
    messages.warning(request, f'Matrícula cerrada para {curso.titulo}.')
    # ¿Por qué request.POST.get('next')?:
    # Permite que si la acción se activó desde el catálogo o desde el panel de coordinación,
    # el usuario retorne automáticamente a la pantalla de donde proviene sin perder su flujo de trabajo.
    next_url = request.POST.get('next') or 'panel_coordinador'
    return redirect(next_url)


@login_required
@user_passes_test(lambda u: u.is_authenticated and (getattr(u, 'role', None) == 'COORDINADOR' or getattr(u, 'rol', None) == 'COORDINADOR' or u.is_staff or u.is_superuser), login_url='catalogo')
@require_POST
def restablecer_cupos_curso_view(request, curso_id):
    """
    Vista rápida para coordinadores: restaura cupos_disponibles = cupos_maximos.
    """
    curso = get_object_or_404(Curso, pk=curso_id)
    curso.cupos_disponibles = curso.cupos_maximos
    curso.save(update_fields=['cupos_disponibles'])
    messages.success(request, f'Cupos restablecidos exitosamente para {curso.titulo} ({curso.cupos_maximos} cupos disponibles).')
    next_url = request.POST.get('next') or 'panel_coordinador'
    return redirect(next_url)


@login_required
@user_passes_test(lambda u: u.is_authenticated and (getattr(u, 'role', None) == 'COORDINADOR' or getattr(u, 'rol', None) == 'COORDINADOR' or u.is_staff or u.is_superuser), login_url='catalogo')
@require_POST
def cancelar_matricula_coordinador_view(request, matricula_id):
    """
    Acción de cancelación rápida para coordinadores:
    Cambia estado a 'CANCELADO' y repone automáticamente +1 cupo a cada curso incluido.
    """
    matricula = get_object_or_404(Matricula, pk=matricula_id)
    estado_anterior = matricula.estado

    if estado_anterior == Matricula.ESTADO_CANCELADO:
        messages.info(request, f'La matrícula #{matricula.id:05d} ya se encontraba en estado CANCELADO.')
        return redirect('panel_coordinador')

    # ¿Por qué transacción atómica y select_for_update al cancelar?:
    # Si la matrícula contiene 3 cursos, debemos garantizar que los cupos se repongan
    # en los tres cursos y el estado se cambie a CANCELADO de forma atómica e indivisible.
    with transaction.atomic():
        detalles = matricula.detalles.select_related('curso').all()
        for detalle in detalles:
            c = Curso.objects.select_for_update().get(pk=detalle.curso_id)
            if c.cupos_disponibles < c.cupos_maximos:
                c.cupos_disponibles += 1
                c.save(update_fields=['cupos_disponibles'])

        matricula.estado = Matricula.ESTADO_CANCELADO
        matricula.save(update_fields=['estado'])

    messages.success(
        request,
        f'Matrícula #{matricula.id:05d} cancelada exitosamente. Se repusieron los cupos en el inventario.'
    )
    return redirect('panel_coordinador')


# ==============================================================================
# ANULACIÓN DE MATRÍCULAS (RETRACTO ESTUDIANTE Y GESTIÓN COORDINADOR)
# ==============================================================================
# ¿Por qué esta vista y su control de retracto?:
# 1. @login_required: Garantiza la identidad activa del estudiante solicitante.
# 2. Validación de propiedad y estado: Impide que usuarios malintencionados anulen órdenes ajenas
#    o que no estén en estado PAGADO (evitando inconsistencias de inventario).
# 3. Plazo legal de retracto: Comprueba que hoy < min(fechas_inicio); si el curso ya empezó,
#    se deniega el retracto protegiendo los compromisos docentes y de aula ya iniciados.
# 4. transaction.atomic() con select_for_update(): Si la orden agrupa múltiples cursos, garantiza
#    que el paso a ANULADA, la auditoría y la restitución (+1 cupo sin rebasar cupos_maximos)
#    se persistan de manera indivisible sin condiciones de carrera.
@login_required
def anular_matricula_estudiante(request, matricula_id):
    """
    Vista protegida para que un estudiante ejerza su derecho de retracto voluntario.
    Valida pertenencia, estado 'PAGADO' y que la fecha actual sea anterior al inicio del curso
    (o del curso más próximo en la orden). Ejecuta transacción atómica para anulación y reposición de cupos.
    """
    matricula = get_object_or_404(Matricula, pk=matricula_id)

    # 1. Validar pertenencia del usuario autenticado
    if matricula.estudiante != request.user:
        messages.error(request, 'No tienes autorización para anular esta matrícula.')
        return redirect('mis_matriculas')

    # 2. Validar que esté en estado PAGADO
    if matricula.estado != Matricula.ESTADO_PAGADO:
        messages.error(request, f'Solo se pueden anular matrículas en estado PAGADO. Estado actual: {matricula.get_estado_display()}.')
        return redirect('mis_matriculas')

    # 3. Validar plazo de retracto: solo permitir si la fecha actual es anterior a la fecha de inicio del curso más próximo
    hoy = timezone.now().date()
    fechas_inicio = [
        detalle.curso.fecha_inicio
        for detalle in matricula.detalles.select_related('curso').all()
        if detalle.curso and detalle.curso.fecha_inicio
    ]

    if fechas_inicio:
        fecha_proxima = min(fechas_inicio)
        if hoy >= fecha_proxima:
            messages.error(
                request,
                f'No es posible ejercer el retracto: el programa inició el {fecha_proxima.strftime("%d/%m/%Y")} o inicia hoy. El plazo de retracto ha expirado.'
            )
            return redirect('mis_matriculas')

    # 4. Transacción atómica: cambio a ANULADA, auditoría y reposición segura de cupos
    with transaction.atomic():
        matricula.estado = Matricula.ESTADO_ANULADA
        matricula.fecha_anulacion = timezone.now()
        matricula.motivo_anulacion = "Retracto voluntario ejercido por el estudiante"
        matricula.anulado_por = request.user
        matricula.save(update_fields=['estado', 'fecha_anulacion', 'motivo_anulacion', 'anulado_por'])

        # ¿Por qué select_for_update() y comprobación c.cupos_disponibles < c.cupos_maximos?:
        # El bloqueo pesimista en PostgreSQL evita condiciones de carrera durante la anulación,
        # mientras que el techo c.cupos_maximos garantiza que la reposición no sobrepase la capacidad física del aula.
        for detalle in matricula.detalles.select_related('curso').all():
            c = Curso.objects.select_for_update().get(pk=detalle.curso_id)
            if c.cupos_disponibles < c.cupos_maximos:
                c.cupos_disponibles += 1
                c.save(update_fields=['cupos_disponibles'])

    messages.success(
        request,
        f"Se ha ejercido el derecho a retracto. La matrícula #{matricula.id:05d} fue anulada y tus cupos han sido liberados."
    )
    return redirect('mis_matriculas')


# ¿Por qué esta vista para coordinadores?:
# 1. @require_POST y verificación RBAC: Asegura que la anulación administrativa sea una mutación
#    explícita invocada solo por coordinadores autorizados o staff.
# 2. Motivo obligatorio: Toda resolución académica directiva exige un fundamento explícito para trazabilidad de auditoría.
# 3. Transacción atómica: Restituye el inventario en los cursos involucrados y asocia 'anulado_por' al usuario directivo.
@login_required
@require_POST
def anular_matricula_coordinador(request, matricula_id):
    """
    Vista protegida para que un coordinador anule administrativamente una matrícula.
    Requiere obligatoriamente un motivo vía POST, ejecuta transacción atómica para pasar
    a 'ANULADA', registrar auditoría y reponer cupos.
    """
    if not (getattr(request.user, 'is_coordinador', False) or getattr(request.user, 'role', None) == 'COORDINADOR' or getattr(request.user, 'rol', None) == 'COORDINADOR' or request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Acceso restringido: Se requieren permisos de Coordinador Académico.')
        return redirect('catalogo')

    matricula = get_object_or_404(Matricula, pk=matricula_id)
    motivo = request.POST.get('motivo', '').strip()

    # Validar campo obligatorio 'motivo'
    if not motivo:
        messages.error(request, 'Debe especificar obligatoriamente un motivo para anular la matrícula.')
        return redirect('panel_coordinador')

    if matricula.estado == Matricula.ESTADO_ANULADA:
        messages.info(request, f'La matrícula #{matricula.id:05d} ya se encuentra en estado ANULADA.')
        return redirect('panel_coordinador')

    with transaction.atomic():
        # ¿Por qué verificar matricula.estado != Matricula.ESTADO_CANCELADO?:
        # Si la matrícula ya se encontraba previamente en CANCELADO, sus cupos ya habían sido
        # devueltos al inventario por una acción anterior. Esta comprobación previene sumar vacantes duplicadas.
        if matricula.estado != Matricula.ESTADO_CANCELADO:
            for detalle in matricula.detalles.select_related('curso').all():
                c = Curso.objects.select_for_update().get(pk=detalle.curso_id)
                if c.cupos_disponibles < c.cupos_maximos:
                    c.cupos_disponibles += 1
                    c.save(update_fields=['cupos_disponibles'])

        matricula.estado = Matricula.ESTADO_ANULADA
        matricula.fecha_anulacion = timezone.now()
        matricula.motivo_anulacion = motivo
        matricula.anulado_por = request.user
        matricula.save(update_fields=['estado', 'fecha_anulacion', 'motivo_anulacion', 'anulado_por'])

    messages.success(request, f"Matrícula #{matricula.id:05d} anulada correctamente y cupos restituidos.")
    return redirect('panel_coordinador')


# ==============================================================================
# GESTIÓN Y CREACIÓN DE CURSOS POR COORDINADOR (LABORATORIOS & COMPUTADORES)
# ==============================================================================
# ¿Por qué utilizamos estos decoradores en la creación de cursos?:
# 1. @login_required: Garantiza que la sesión exista y sea válida.
# 2. @user_passes_test: Verifica que el usuario tenga rol COORDINADOR o Staff, evitando escalamiento de privilegios.
# 3. @require_POST: Protege contra peticiones GET maliciosas o accidentales, pues modificar inventario es una acción de escritura.
@login_required
@user_passes_test(lambda u: u.is_authenticated and (getattr(u, 'role', None) == 'COORDINADOR' or getattr(u, 'rol', None) == 'COORDINADOR' or u.is_staff or u.is_superuser), login_url='catalogo')
@require_POST
def crear_curso_coordinador_view(request):
    """
    Crea un nuevo curso/bootcamp desde el formulario del Coordinador Académico.
    Asigna cupos_disponibles = cupos_maximos y gestiona la coherencia física de computadores.
    """
    titulo = request.POST.get('titulo', '').strip()
    area_id = request.POST.get('area') or request.POST.get('area_id')
    laboratorio = request.POST.get('laboratorio', 'Laboratorio TI-1').strip() or 'Laboratorio TI-1'
    descripcion = request.POST.get('descripcion', '').strip()
    fecha_inicio = request.POST.get('fecha_inicio')
    fecha_termino = request.POST.get('fecha_termino')

    if not (titulo and area_id and fecha_inicio and fecha_termino and descripcion):
        messages.error(request, 'Todos los campos requeridos deben ser completados para publicar el curso.')
        return redirect('catalogo')

    area = get_object_or_404(AreaConocimiento, pk=area_id)

    try:
        cantidad_computadores = int(request.POST.get('cantidad_computadores') or 20)
    except (ValueError, TypeError):
        cantidad_computadores = 20

    try:
        cupos_maximos = int(request.POST.get('cupos_maximos') or 20)
    except (ValueError, TypeError):
        cupos_maximos = 20

    # ¿Por qué sanitizar y parsear el costo con Decimal?:
    # El dinero jamás debe almacenarse como flotante (float) por imprecisiones binarias IEEE 754.
    # Convertimos a Decimal de coma fija para mantener exactitud contable a nivel de base de datos.
    try:
        raw_costo = str(request.POST.get('costo_matricula', 0)).replace('.', '').replace('$', '').strip()
        costo_matricula = Decimal(raw_costo or '0')
    except Exception:
        costo_matricula = Decimal('0.00')

    # ¿Por qué asignamos cupos_disponibles = cupos_maximos?:
    # Al aperturar una nueva oferta académica no existen inscripciones previas, por lo que el 100% de las vacantes
    # queda inmediatamente disponible para el catálogo sin requerir cálculos posteriores.
    cupos_disponibles = cupos_maximos

    curso = Curso(
        area=area,
        titulo=titulo,
        descripcion=descripcion,
        costo_matricula=costo_matricula,
        fecha_inicio=fecha_inicio,
        fecha_termino=fecha_termino,
        cupos_maximos=cupos_maximos,
        cupos_disponibles=cupos_disponibles,
        laboratorio=laboratorio,
        cantidad_computadores=cantidad_computadores,
        activo=True,
    )

    # ¿Por qué ejecutamos curso.full_clean() antes de save()?:
    # Django ORM por defecto NO ejecuta el método clean() del modelo al invocar .save().
    # Invocar curso.full_clean() es obligatorio para que las reglas de negocio (como no superar los PCs del laboratorio
    # y la coherencia cronológica de fechas) se validen antes de persistir los datos en PostgreSQL.
    try:
        curso.full_clean()
        curso.save()
    except ValidationError as e:
        errores = " ".join([f"{k}: {', '.join(v)}" for k, v in e.message_dict.items()]) if hasattr(e, 'message_dict') else str(e)
        messages.error(request, f'Error al validar el curso: {errores}')
        return redirect('catalogo')

    # Advertencia si cupos superan computadores (coherencia física de infraestructura)
    if cupos_maximos > cantidad_computadores:
        messages.warning(
            request,
            f"Advertencia de coherencia física: Los cupos ({cupos_maximos}) superan la cantidad de computadores ({cantidad_computadores}) del laboratorio {laboratorio}."
        )

    # Mensaje de confirmación obligatorio: "Curso '[Título]' publicado con éxito en el catálogo."
    messages.success(request, f"Curso '{curso.titulo}' publicado con éxito en el catálogo.")
    return redirect('catalogo')


# ¿Por qué utilizamos estos decoradores en la edición de cursos?:
# 1. @login_required: Garantiza que la sesión exista y sea válida.
# 2. @user_passes_test: Verifica que el usuario tenga rol COORDINADOR o Staff, evitando escalamiento de privilegios.
# 3. @require_POST: Protege contra peticiones GET maliciosas o accidentales, pues modificar inventario es una acción de escritura.
@login_required
@user_passes_test(lambda u: u.is_authenticated and (getattr(u, 'role', None) == 'COORDINADOR' or getattr(u, 'rol', None) == 'COORDINADOR' or u.is_staff or u.is_superuser), login_url='catalogo')
@require_POST
def editar_curso_coordinador_view(request, curso_id):
    """
    Edita un curso existente con control de salas/laboratorios, detección de conflictos
    por cruce de fechas y recálculo de cupos disponibles.
    """
    curso = get_object_or_404(Curso, id=curso_id)

    titulo = request.POST.get('titulo', curso.titulo).strip() or curso.titulo
    descripcion = request.POST.get('descripcion', curso.descripcion).strip() or curso.descripcion
    area_id = request.POST.get('area') or request.POST.get('area_id')
    nuevo_laboratorio = request.POST.get('laboratorio', curso.laboratorio).strip() or curso.laboratorio
    nueva_fecha_inicio = request.POST.get('fecha_inicio', str(curso.fecha_inicio))
    nueva_fecha_termino = request.POST.get('fecha_termino', str(curso.fecha_termino))

    # ¿Por qué sanitizar y parsear el costo con Decimal?:
    # El dinero jamás debe almacenarse como flotante (float) por imprecisiones binarias IEEE 754.
    # Convertimos a Decimal de coma fija para mantener exactitud contable a nivel de base de datos.
    try:
        raw_costo = str(request.POST.get('costo_matricula', curso.costo_matricula)).replace('.', '').replace('$', '').strip()
        costo_matricula = Decimal(raw_costo or '0')
    except Exception:
        costo_matricula = curso.costo_matricula

    try:
        nuevo_cupos_maximos = int(request.POST.get('cupos_maximos', curso.cupos_maximos))
    except (ValueError, TypeError):
        nuevo_cupos_maximos = curso.cupos_maximos

    try:
        cantidad_computadores = int(request.POST.get('cantidad_computadores', curso.cantidad_computadores))
    except (ValueError, TypeError):
        cantidad_computadores = curso.cantidad_computadores

    # ¿Por qué parseamos a objetos date nativos?:
    # Garantiza compatibilidad universal entre PostgreSQL y SQLite en el motor ORM de Django,
    # evitando errores de casteo de fechas según la configuración regional del servidor.
    try:
        if isinstance(nueva_fecha_inicio, str):
            inicio_date = datetime.strptime(nueva_fecha_inicio, '%Y-%m-%d').date()
        else:
            inicio_date = nueva_fecha_inicio
        if isinstance(nueva_fecha_termino, str):
            termino_date = datetime.strptime(nueva_fecha_termino, '%Y-%m-%d').date()
        else:
            termino_date = nueva_fecha_termino
    except (ValueError, TypeError):
        inicio_date = curso.fecha_inicio
        termino_date = curso.fecha_termino

    # ¿Por qué este algoritmo de conflicto de salas (fecha_inicio__lte y fecha_termino__gte)?:
    # Dos intervalos [A, B] y [C, D] se intersectan si y solo si A <= D y B >= C.
    # Excluimos el curso actual (exclude(id=curso.id)) para que no colisione consigo mismo y buscamos
    # si existe otro programa que use el mismo laboratorio en ese rango de fechas.
    conflicto = Curso.objects.exclude(id=curso.id).filter(
        laboratorio__iexact=nuevo_laboratorio,
        fecha_inicio__lte=termino_date,
        fecha_termino__gte=inicio_date
    ).first()
    if conflicto:
        messages.warning(
            request,
            f"Advertencia de Infraestructura: El {nuevo_laboratorio} ya está asignado al programa '{conflicto.titulo}' en ese período."
        )

    # ¿Por qué recalculamos cupos disponibles con max(0, nuevo_cupos_maximos - matriculas_activas)?:
    # Si ya existen alumnos matriculados y el coordinador ajusta los cupos máximos,
    # calculamos las vacantes reales remanentes. max(0, ...) evita números negativos ante sobrecupos.
    matriculas_activas = curso.cupos_maximos - curso.cupos_disponibles
    nuevo_disponibles = max(0, nuevo_cupos_maximos - matriculas_activas)
    curso.cupos_disponibles = nuevo_disponibles

    curso.titulo = titulo
    curso.descripcion = descripcion
    curso.costo_matricula = costo_matricula
    curso.cupos_maximos = nuevo_cupos_maximos
    curso.laboratorio = nuevo_laboratorio
    curso.cantidad_computadores = cantidad_computadores
    curso.fecha_inicio = inicio_date
    curso.fecha_termino = termino_date

    if area_id:
        try:
            area = AreaConocimiento.objects.get(pk=area_id)
            curso.area = area
        except AreaConocimiento.DoesNotExist:
            pass

    # ¿Por qué curso.full_clean() antes de save()?:
    # Ejecuta el método clean() del modelo Curso, asegurando que los cupos no superen la cantidad de PCs
    # y que las fechas sean coherentes antes de persistir los cambios en la base de datos.
    try:
        curso.full_clean()
        curso.save()
        messages.success(request, f"Curso '{curso.titulo}' actualizado exitosamente.")
    except ValidationError as e:
        errores = " ".join([f"{k}: {', '.join(v)}" for k, v in e.message_dict.items()]) if hasattr(e, 'message_dict') else str(e)
        messages.error(request, f"Error al validar los cambios del curso: {errores}")

    return redirect('catalogo')


# ¿Por qué patrón de Borrado Lógico (Soft Delete) en lugar de Hard Delete?:
# 1. Integridad referencial y trazabilidad contable: El registro de Curso permanece en PostgreSQL,
#    salvaguardando las matrículas históricas y comprobantes oficiales ya emitidos.
# 2. Reversibilidad y auditoría: Se registra la marca temporal exacta en 'fecha_desactivacion' y
#    se apaga la bandera 'activo = False', permitiendo al coordinador revertir la baja en cualquier momento.
# 3. Limpieza defensiva de carritos: Se purgan los ItemCarro activos para que ningún estudiante
#    pueda continuar al checkout con un programa retirado de oferta académica.
@login_required
@user_passes_test(lambda u: u.is_authenticated and (getattr(u, 'role', None) == 'COORDINADOR' or getattr(u, 'rol', None) == 'COORDINADOR' or u.is_staff or u.is_superuser), login_url='catalogo')
@require_POST
def eliminar_curso_coordinador_view(request, curso_id):
    """
    Baja lógica (Soft Delete) de cursos protegiendo la integridad referencial histórica.
    Archiva el curso seteando activo=False y registrando fecha_desactivacion sin destruir registros en PostgreSQL.
    """
    curso = get_object_or_404(Curso, id=curso_id)

    curso.activo = False
    curso.fecha_desactivacion = timezone.now()
    curso.save(update_fields=['activo', 'fecha_desactivacion'])

    # Limpieza de ítems en carros de compra antes de archivarlo
    curso.itemcarro_set.all().delete()

    messages.success(request, "El programa ha sido archivado y retirado del catálogo público sin alterar registros históricos.")
    return redirect('panel_coordinador')

eliminar_curso = eliminar_curso_coordinador_view
archivar_curso = eliminar_curso_coordinador_view


# ¿Por qué reactivar_curso(request, curso_id) y su control RBAC?:
# Proporciona una acción de reincorporación formal exclusiva para el rol COORDINADOR vía POST.
# Restaura 'activo = True' y reinicia 'fecha_desactivacion = None', reincorporando el curso
# a la oferta de admisiones del catálogo público de manera inmediata sin duplicar registros.
@login_required
@user_passes_test(lambda u: u.is_authenticated and (getattr(u, 'role', None) == 'COORDINADOR' or getattr(u, 'rol', None) == 'COORDINADOR' or u.is_staff or u.is_superuser), login_url='catalogo')
@require_POST
def reactivar_curso(request, curso_id):
    """
    Reactivación de programas académicos archivados (exclusivo para COORDINADOR).
    Restaura activo=True y limpia fecha_desactivacion.
    """
    curso = get_object_or_404(Curso, id=curso_id)

    curso.activo = True
    curso.fecha_desactivacion = None
    curso.save(update_fields=['activo', 'fecha_desactivacion'])

    messages.success(request, "El programa ha sido reactivado y vuelve a estar visible en el catálogo de admisiones.")
    return redirect('panel_coordinador')

reactivar_curso_view = reactivar_curso


# ==============================================================================
# SECCIÓN 3: MANEJADOR DE ERROR 404 (JSON O HTML CON DATOS DEL ALUMNO)
# ==============================================================================

def custom_404_view(request, exception=None):
    """
    Vista de error 404 global.
    Retorna respuesta JSON si la petición solicita API/JSON, o página HTML amigable
    con los datos de Fernando Pailahueque (AP-N4-C2, 2026).
    """
    accept = request.META.get('HTTP_ACCEPT', '')
    es_api = request.path.startswith('/api/') or 'application/json' in accept

    if es_api:
        return JsonResponse(
            {
                'error': 'Recurso no encontrado (HTTP 404)',
                'ruta': request.path,
                'metodo': request.method,
                'status': 404,
                'datos_evaluacion': {
                    'alumno': 'Fernando Pailahueque',
                    'nombre_alumno': 'Fernando Pailahueque',
                    'seccion': 'AP-N4-C2',
                    'anio': 2026,
                    'plataforma': 'EdTech - Caso 2'
                }
            },
            status=404
        )

    context = {
        'path': request.path,
        'alumno': 'Fernando Pailahueque',
        'alumno_nombre': 'Fernando Pailahueque',
        'seccion': 'AP-N4-C2',
        'alumno_seccion': 'AP-N4-C2',
        'anio': 2026,
        'alumno_anio': 2026,
    }
    return render(request, 'academico/404.html', context, status=404)
