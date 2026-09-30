"""
Serializadores DRF - Plataforma EdTech
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from .models import (
    AreaConocimiento,
    Curso,
    CarroMatricula,
    ItemCarro,
    Matricula,
    DetalleMatricula,
)

User = get_user_model()


# ==============================================================================
# SERIALIZADOR DE AUTENTICACIÓN JWT CON CLAIMS PERSONALIZADOS
# ==============================================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Token JWT enriquecido con claims: role, username, nombre_alumno, seccion, anio.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Inyección de claims en el payload del JWT según pauta
        token['username'] = user.username
        token['role'] = user.rol
        token['rol'] = user.rol
        token['nombre_alumno'] = 'Fernando Pailahueque'
        token['alumno'] = 'Fernando Pailahueque'
        token['seccion'] = 'AP-N4-C2'
        token['anio'] = 2026
        token['email'] = user.email

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # Inyección de metadata en la respuesta HTTP
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'role': self.user.rol,
            'rol': self.user.rol,
            'nombre_completo': self.user.get_full_name() or self.user.username,
        }
        data['nombre_alumno'] = 'Fernando Pailahueque'
        data['seccion'] = 'AP-N4-C2'
        data['anio'] = 2026
        data['academico_info'] = {
            'alumno': 'Fernando Pailahueque',
            'nombre_alumno': 'Fernando Pailahueque',
            'seccion': 'AP-N4-C2',
            'anio': 2026,
            'proyecto': 'Plataforma de Reservas de Cursos y Bootcamps (EdTech)'
        }
        return data


# ==============================================================================
# SERIALIZADORES DE USUARIO Y ÁREA
# ==============================================================================
class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'rol',
            'telefono',
            'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']


class AreaConocimientoSerializer(serializers.ModelSerializer):
    total_cursos = serializers.IntegerField(source='cursos.count', read_only=True)

    class Meta:
        model = AreaConocimiento
        fields = ['id', 'nombre', 'descripcion', 'fecha_creacion', 'total_cursos']
        read_only_fields = ['id', 'fecha_creacion']


# ==============================================================================
# SERIALIZADOR DE CURSO
# ==============================================================================
class CursoSerializer(serializers.ModelSerializer):
    area_nombre = serializers.CharField(source='area.nombre', read_only=True)
    tiene_cupos = serializers.BooleanField(read_only=True)
    cupos_ocupados = serializers.IntegerField(read_only=True)
    porcentaje_ocupacion = serializers.IntegerField(read_only=True)

    class Meta:
        model = Curso
        fields = [
            'id',
            'area',
            'area_nombre',
            'titulo',
            'descripcion',
            'costo_matricula',
            'fecha_inicio',
            'fecha_termino',
            'cupos_maximos',
            'cupos_disponibles',
            'laboratorio',
            'cantidad_computadores',
            'activo',
            'tiene_cupos',
            'cupos_ocupados',
            'porcentaje_ocupacion',
        ]
        read_only_fields = ['id', 'tiene_cupos', 'cupos_ocupados', 'porcentaje_ocupacion']

    def validate(self, attrs):
        cupos_disponibles = attrs.get('cupos_disponibles', getattr(self.instance, 'cupos_disponibles', None))
        cupos_maximos = attrs.get('cupos_maximos', getattr(self.instance, 'cupos_maximos', None))
        if cupos_disponibles is not None and cupos_maximos is not None:
            if cupos_disponibles > cupos_maximos:
                raise serializers.ValidationError({
                    'cupos_disponibles': 'Los cupos disponibles no pueden superar los cupos máximos.'
                })

        fecha_inicio = attrs.get('fecha_inicio', getattr(self.instance, 'fecha_inicio', None))
        fecha_termino = attrs.get('fecha_termino', getattr(self.instance, 'fecha_termino', None))
        if fecha_inicio and fecha_termino and fecha_inicio > fecha_termino:
            raise serializers.ValidationError({
                'fecha_termino': 'La fecha de término no puede ser anterior a la fecha de inicio.'
            })
        return attrs


# ==============================================================================
# SERIALIZADORES DE CARRO DE MATRÍCULA
# ==============================================================================
class ItemCarroSerializer(serializers.ModelSerializer):
    curso_detalle = CursoSerializer(source='curso', read_only=True)
    curso_titulo = serializers.CharField(source='curso.titulo', read_only=True)
    costo_matricula = serializers.DecimalField(source='curso.costo_matricula', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ItemCarro
        fields = ['id', 'curso', 'curso_titulo', 'costo_matricula', 'curso_detalle', 'fecha_agregado']
        read_only_fields = ['id', 'fecha_agregado']


class CarroMatriculaSerializer(serializers.ModelSerializer):
    items = ItemCarroSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    estudiante_username = serializers.CharField(source='estudiante.username', read_only=True)

    class Meta:
        model = CarroMatricula
        fields = [
            'id',
            'estudiante',
            'estudiante_username',
            'items',
            'total',
            'total_items',
            'fecha_actualizacion',
        ]
        read_only_fields = ['id', 'estudiante', 'fecha_actualizacion']


class AgregarItemCarroSerializer(serializers.Serializer):
    curso_id = serializers.IntegerField(required=True)

    def validate_curso_id(self, value):
        try:
            curso = Curso.objects.get(pk=value, activo=True)
        except Curso.DoesNotExist:
            raise serializers.ValidationError("El curso seleccionado no existe o no está activo.")

        if curso.cupos_disponibles <= 0:
            raise serializers.ValidationError("El curso no cuenta con cupos disponibles actualmente.")
        return value


# ==============================================================================
# SERIALIZADORES DE DETALLE Y MATRÍCULA
# ==============================================================================
class DetalleMatriculaSerializer(serializers.ModelSerializer):
    curso_titulo = serializers.CharField(source='curso.titulo', read_only=True)
    area_nombre = serializers.CharField(source='curso.area.nombre', read_only=True)

    class Meta:
        model = DetalleMatricula
        fields = ['id', 'curso', 'curso_titulo', 'area_nombre', 'precio_historico']
        read_only_fields = ['id', 'precio_historico']


class MatriculaSerializer(serializers.ModelSerializer):
    detalles = DetalleMatriculaSerializer(many=True, read_only=True)
    estudiante_username = serializers.CharField(source='estudiante.username', read_only=True)
    estudiante_email = serializers.CharField(source='estudiante.email', read_only=True)
    codigo_comprobante = serializers.CharField(read_only=True)

    class Meta:
        model = Matricula
        fields = [
            'id',
            'codigo_comprobante',
            'estudiante',
            'estudiante_username',
            'estudiante_email',
            'estado',
            'total',
            'fecha_creacion',
            'detalles',
        ]
        read_only_fields = ['id', 'codigo_comprobante', 'estudiante', 'total', 'fecha_creacion']


# ==============================================================================
# SERIALIZADOR DE CHECKOUT / CONFIRMAR MATRÍCULA
# ==============================================================================
class CheckoutSerializer(serializers.Serializer):
    metodo_pago = serializers.CharField(required=False, default='ONLINE', max_length=50)

    def validate(self, attrs):
        user = self.context['request'].user
        carro, _ = CarroMatricula.objects.get_or_create(estudiante=user)
        items = carro.items.select_related('curso').all()

        if not items.exists():
            raise serializers.ValidationError("El carro de matrícula se encuentra vacío.")

        # Validar cupos para cada curso
        cursos_sin_cupo = []
        for item in items:
            if item.curso.cupos_disponibles <= 0:
                cursos_sin_cupo.append(item.curso.titulo)

        if cursos_sin_cupo:
            raise serializers.ValidationError({
                'cupos_insuficientes': f"Los siguientes cursos ya no tienen cupos disponibles: {', '.join(cursos_sin_cupo)}"
            })

        attrs['carro'] = carro
        attrs['items'] = items
        return attrs


# ==============================================================================
# SERIALIZADOR DE CAMBIO DE ESTADO (Para Coordinadores)
# ¿Por qué serializers.ChoiceField con estados extendidos?:
# Al definir 'estado' explícitamente en el serializador con las 4 constantes (PENDIENTE, PAGADO, CANCELADO, ANULADA),
# desacoplamos la validación de la API del choices del modelo, garantizando interoperabilidad
# retrocompatible con endpoints que administran estados históricos y la nueva opción ANULADA.
# ==============================================================================
class CambiarEstadoMatriculaSerializer(serializers.ModelSerializer):
    estado = serializers.ChoiceField(
        choices=[Matricula.ESTADO_PENDIENTE, Matricula.ESTADO_PAGADO, Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA]
    )

    class Meta:
        model = Matricula
        fields = ['estado']

    def validate_estado(self, value):
        if value not in [Matricula.ESTADO_PENDIENTE, Matricula.ESTADO_PAGADO, Matricula.ESTADO_CANCELADO, Matricula.ESTADO_ANULADA]:
            raise serializers.ValidationError("Estado no válido. Opciones: PENDIENTE, PAGADO, CANCELADO, ANULADA.")
        return value
