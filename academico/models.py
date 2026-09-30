"""
Modelos de Datos - Plataforma EdTech
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError


# ==============================================================================
# BLOQUE 1: MODELO DE USUARIO PERSONALIZADO (CustomUser)
# ¿Por qué utilizamos AbstractUser aquí?:
# Django provee dos formas de personalizar usuarios: AbstractBaseUser y AbstractUser.
# Aquí utilicé AbstractUser porque hereda de forma lista y segura toda la lógica de
# autenticación nativa de Django (algoritmos de hashing PBKDF2 para contraseñas,
# campos username, email, is_staff, is_active y grupos de permisos), permitiéndonos
# añadir únicamente los campos de negocio requeridos (como 'rol' y 'telefono')
# sin tener que reinventar la rueda de la seguridad web.
# ==============================================================================
class CustomUser(AbstractUser):
    """
    Usuario personalizado con sistema de roles para la plataforma EdTech.
    """
    # Constantes de roles para evitar cadenas 'mágicas' dispersas en el código
    ROLE_ESTUDIANTE = 'ESTUDIANTE'
    ROLE_COORDINADOR = 'COORDINADOR'

    ROLES_CHOICES = [
        (ROLE_ESTUDIANTE, 'Estudiante'),
        (ROLE_COORDINADOR, 'Coordinador Académico'),
    ]

    # ¿Por qué un CharField con choices?:
    # Permite validación estricta tanto en formularios como en la API y el panel de Django,
    # manteniendo legibilidad directa en consultas SQL sin requerir un join adicional.
    rol = models.CharField(
        max_length=20,
        choices=ROLES_CHOICES,
        default=ROLE_ESTUDIANTE,
        verbose_name='Rol en la Plataforma',
        help_text='Define si el usuario es Estudiante o Coordinador Académico'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Teléfono de Contacto'
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()})"

    # ¿Por qué definimos este getter property .role?:
    # Permite compatibilidad transparente con plantillas o servicios que consulten
    # tanto 'user.rol' (en español) como 'user.role' (en inglés).
    @property
    def role(self):
        if self.rol == self.ROLE_COORDINADOR or self.is_staff or self.is_superuser:
            return self.ROLE_COORDINADOR
        return self.rol

    # ¿Por qué propiedades booleanas is_estudiante e is_coordinador?:
    # Facilitan la lectura de código en vistas y plantillas (ej: user.is_coordinador),
    # unificando además a superusuarios y staff como coordinadores autorizados.
    @property
    def is_estudiante(self):
        return self.rol == self.ROLE_ESTUDIANTE

    @property
    def is_coordinador(self):
        return self.rol == self.ROLE_COORDINADOR or self.is_staff or self.is_superuser


# ==============================================================================
# BLOQUE 2: ÁREA DE CONOCIMIENTO (AreaConocimiento)
# Clasificación temática de los cursos y bootcamps ofertados.
# ==============================================================================
class AreaConocimiento(models.Model):
    """
    Área temática a la que pertenecen los cursos (ej: Desarrollo Web, Ciberseguridad).
    """
    nombre = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Nombre del Área'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Descripción'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )

    class Meta:
        verbose_name = 'Área de Conocimiento'
        verbose_name_plural = 'Áreas de Conocimiento'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


# ==============================================================================
# BLOQUE 3: CATÁLOGO DE CURSOS Y BOOTCAMPS (Curso)
# ¿Por qué este modelo y sus campos?:
# 1. on_delete=models.PROTECT en 'area': Si un área temática contiene cursos activos,
#    la base de datos impide su eliminación accidental, protegiendo la integridad referencial.
# 2. DecimalField(max_digits=10, decimal_places=2) en 'costo_matricula':
#    ¡El dinero JAMÁS debe guardarse como FloatField! Los números de punto flotante
#    sufren imprecisiones binarias por redondeo (estándar IEEE 754). DecimalField almacena
#    los valores numéricos de forma exacta a nivel SQL (tipo NUMERIC en PostgreSQL).
# 3. PositiveIntegerField para cupos: La base de datos garantiza que no existan cupos negativos.
# ==============================================================================
class Curso(models.Model):
    """
    Entidad Curso/Bootcamp con cupos máximos y disponibles en tiempo real.
    """
    area = models.ForeignKey(
        AreaConocimiento,
        on_delete=models.PROTECT,
        related_name='cursos',
        verbose_name='Área de Conocimiento'
    )
    titulo = models.CharField(
        max_length=200,
        verbose_name='Título del Curso/Bootcamp'
    )
    descripcion = models.TextField(
        verbose_name='Descripción Detallada'
    )
    costo_matricula = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Costo de Matrícula (CLP)'
    )
    fecha_inicio = models.DateField(
        verbose_name='Fecha de Inicio'
    )
    fecha_termino = models.DateField(
        verbose_name='Fecha de Término'
    )
    cupos_maximos = models.PositiveIntegerField(
        verbose_name='Cupos Máximos'
    )
    cupos_disponibles = models.PositiveIntegerField(
        verbose_name='Cupos Disponibles'
    )
    laboratorio = models.CharField(
        max_length=100,
        default='Laboratorio TI-1',
        verbose_name="Laboratorio Asignado"
    )
    cantidad_computadores = models.PositiveIntegerField(
        default=20,
        verbose_name="Cantidad de Computadores"
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Curso Activo'
    )

    class Meta:
        verbose_name = 'Curso / Bootcamp'
        verbose_name_plural = 'Cursos y Bootcamps'
        ordering = ['fecha_inicio', 'titulo']

    def __str__(self):
        return f"{self.titulo} - Cupos: {self.cupos_disponibles}/{self.cupos_maximos} ({self.laboratorio} - {self.cantidad_computadores} PCs)"

    # ¿Por qué el método clean()?:
    # Permite validaciones cruzadas entre campos antes de persistir.
    # Aquí utilicé clean() para asegurar que la fecha de término sea posterior a la de inicio,
    # que los cupos disponibles no superen jamás el límite máximo del aula virtual,
    # y asegurar coherencia física entre los cupos ofertados y los computadores del laboratorio.
    def clean(self):
        super().clean()
        if self.fecha_inicio and self.fecha_termino and self.fecha_inicio > self.fecha_termino:
            raise ValidationError({'fecha_termino': 'La fecha de término no puede ser anterior a la fecha de inicio.'})
        if self.cupos_disponibles is not None and self.cupos_maximos is not None:
            if self.cupos_disponibles > self.cupos_maximos:
                raise ValidationError({'cupos_disponibles': 'Los cupos disponibles no pueden superar los cupos máximos.'})
        if self.cupos_maximos is not None and self.cantidad_computadores is not None:
            if self.cupos_maximos > self.cantidad_computadores:
                raise ValidationError({
                    'cupos_maximos': f"Los cupos ofrecidos ({self.cupos_maximos}) no pueden superar la capacidad física del laboratorio ({self.cantidad_computadores} PCs)."
                })

    # ¿Por qué la propiedad matriculas_actuales?:
    # Sirve para calcular al vuelo la cantidad de alumnos que ya ocupan una vacante (cupos_maximos - cupos_disponibles).
    # Este código se implementó como property para evitar un campo redundante en la base de datos que podría desincronizarse
    # ante cancelaciones o concurrencia, manteniendo consistencia inmediata en las tarjetas del catálogo.
    @property
    def matriculas_actuales(self):
        """Alumnos matriculados actualmente en el programa."""
        if self.cupos_maximos is not None and self.cupos_disponibles is not None:
            return max(0, self.cupos_maximos - self.cupos_disponibles)
        return 0

    @property
    def computadores_remanentes(self):
        """Cantidad de computadores que quedan libres como respaldo técnico en el laboratorio."""
        return max(0, self.cantidad_computadores - self.cupos_maximos)

    @property
    def porcentaje_ocupacion_computadores(self):
        """Porcentaje de uso de computadores del laboratorio respecto a cupos máximos."""
        if self.cantidad_computadores > 0:
            return round((self.cupos_maximos / self.cantidad_computadores) * 100)
        return 0

    @property
    def tiene_cupos(self):
        return self.cupos_disponibles > 0

    @property
    def cupos_ocupados(self):
        return max(0, self.cupos_maximos - self.cupos_disponibles)

    # ¿Por qué la propiedad porcentaje_ocupacion?:
    # Calcula dinámicamente el progreso para alimentar directamente la barra de progreso
    # de Bootstrap (progress-bar) y los badges de ocupación sin almacenar datos redundantes en BD.
    @property
    def porcentaje_ocupacion(self):
        if self.cupos_maximos > 0:
            return round(((self.cupos_maximos - self.cupos_disponibles) / self.cupos_maximos) * 100)
        return 0

    # ¿Por qué la propiedad style_width?:
    # Aquí utilicé esta propiedad con mark_safe para inyectar el atributo 'style="width: X%;"' directamente desde Python.
    # Este código sirve porque los analizadores estáticos de CSS en editores (VS Code / Antigravity) interpretan
    # las llaves de Django '{{' dentro de un atributo 'style' literal de HTML como CSS inválido (generando advertencias
    # 'css-propertyvalueexpected' y 'css-ruleorselectorexpected'). Al generarlo como propiedad segura, la barra de progreso
    # de Bootstrap renderiza su porcentaje nativo en el navegador y el editor queda completamente libre de errores.
    @property
    def style_width(self):
        from django.utils.safestring import mark_safe
        return mark_safe(f'style="width: {self.porcentaje_ocupacion}%;"')

    # ¿Por qué la propiedad costo_clp?:
    # Formatea el costo de matrícula según el estándar monetario chileno (CLP):
    # Sin decimales y con puntos separadores de miles ($450.000).
    @property
    def costo_clp(self):
        try:
            return f"${int(round(float(self.costo_matricula))):,}".replace(",", ".")
        except Exception:
            return f"${self.costo_matricula}"

    # ¿Por qué definir detallematricula_set e itemcarro_set?:
    # Al utilizar related_name explícitos ('detalles_matricula' y 'en_carros'), Django sobreescribe el reverse manager
    # estándar de la convención '<modelo>_set'. Definimos estas propiedades para permitir que vistas o scripts
    # que utilicen la sintaxis nativa de Django interactúen sin errores de AttributeError y con total compatibilidad.
    @property
    def detallematricula_set(self):
        """Compatibilidad con el accessor de relación inversa estándar a DetalleMatricula."""
        return self.detalles_matricula

    @property
    def itemcarro_set(self):
        """Compatibilidad con el accessor de relación inversa estándar a ItemCarro."""
        return self.en_carros


# ==============================================================================
# BLOQUE 4: CARRO DE MATRÍCULA (CarroMatricula)
# ¿Por qué OneToOneField con CustomUser?:
# Cada estudiante tiene exactamente un carro persistente activo en el sistema.
# Al usar OneToOneField, evitamos que un usuario tenga múltiples carros huérfanos
# y podemos acceder inmediatamente al carro de forma limpia con `request.user.carro`.
# ==============================================================================
class CarroMatricula(models.Model):
    """
    Carro de compras de cursos por estudiante antes del checkout formal.
    """
    estudiante = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='carro',
        verbose_name='Estudiante Titular'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )

    class Meta:
        verbose_name = 'Carro de Matrícula'
        verbose_name_plural = 'Carros de Matrícula'

    def __str__(self):
        return f"Carro de {self.estudiante.username}"

    @property
    def total(self):
        """Calcula el costo total sumando los cursos en el carro."""
        return sum(item.curso.costo_matricula for item in self.items.all())

    @property
    def total_items(self):
        """Retorna la cantidad de cursos agregados."""
        return self.items.count()

    @property
    def total_clp(self):
        """Formatea el total del carro al estándar chileno sin decimales: $XXX.XXX"""
        return f"${int(round(float(self.total))):,}".replace(",", ".")


# ==============================================================================
# BLOQUE 5: ÍTEMS DEL CARRO (ItemCarro)
# ¿Por qué unique_together = ('carro', 'curso')?:
# Aquí utilicé una restricción de unicidad compuesta (composite unique constraint)
# para que la base de datos PostgreSQL impida físicamente que un estudiante inserte
# dos veces el mismo curso en su carrito, evitando errores de duplicidad.
# ==============================================================================
class ItemCarro(models.Model):
    """
    Curso individual agregado al carro de un estudiante.
    """
    carro = models.ForeignKey(
        CarroMatricula,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Carro Asociado'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='en_carros',
        verbose_name='Curso Seleccionado'
    )
    fecha_agregado = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Agregado'
    )

    class Meta:
        verbose_name = 'Ítem de Carro'
        verbose_name_plural = 'Ítems de Carro'
        unique_together = ('carro', 'curso')
        ordering = ['-fecha_agregado']

    def __str__(self):
        return f"{self.curso.titulo} en carro de {self.carro.estudiante.username}"


# ==============================================================================
# BLOQUE 6: MATRÍCULA FORMALIZADA (Matricula)
# ¿Por qué separar Matricula de Carro?:
# El carro es un estado transitorio y volátil; la Matrícula es una orden formal,
# inmutable y auditable que registra la fecha exacta, monto pagado y estado del servicio.
# ==============================================================================
class Matricula(models.Model):
    """
    Orden de matrícula formal. Permite los estados PAGADO y ANULADA.
    """
    ESTADO_PAGADO = 'PAGADO'
    ESTADO_ANULADA = 'ANULADA'
    ESTADO_PENDIENTE = 'PENDIENTE'
    ESTADO_CANCELADO = 'CANCELADO'

    ESTADOS = [
        ('PAGADO', 'Pagado'),
        ('ANULADA', 'Anulada'),
    ]

    ESTADOS_CHOICES = ESTADOS + [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_CANCELADO, 'Cancelado'),
    ]

    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='matriculas',
        verbose_name='Estudiante Matriculado'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PAGADO,
        verbose_name='Estado de la Matrícula'
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        verbose_name='Monto Total (CLP)'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )

    # ¿Por qué campos de auditoría (motivo_anulacion, fecha_anulacion, anulado_por)?:
    # Toda anulación formal (sea por derecho legal de retracto del estudiante o cancelación administrativa
    # por parte de coordinación) debe ser plenamente trazable para efectos financieros y académicos.
    # Guardamos la marca temporal exacta, el motivo formal y la referencia al usuario responsable (SET_NULL
    # para que si un usuario directivo es eliminado, el registro histórico de la orden permanezca intacto).
    motivo_anulacion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Motivo de Anulación'
    )
    fecha_anulacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Anulación'
    )
    anulado_por = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matriculas_anuladas',
        verbose_name='Anulado por'
    )

    class Meta:
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Matrícula #{self.id:05d} - {self.estudiante.username} [{self.get_estado_display()}]"

    # ¿Por qué un código formateado?:
    # Permite entregar comprobantes profesionales con formato institucional: EDT-YYYYMM-XXXXX
    @property
    def codigo_comprobante(self):
        return f"EDT-{self.fecha_creacion.strftime('%Y%m')}-{self.id:05d}"

    @property
    def total_clp(self):
        """Formatea el total de la matrícula en pesos chilenos sin decimales: $XXX.XXX"""
        return f"${int(round(float(self.total))):,}".replace(",", ".")

    # ¿Por qué la propiedad permite_retracto?:
    # Implementa la regla de negocio y normativa de retracto educacional: el estudiante solo puede solicitar
    # la restitución voluntaria si las clases aún no han comenzado (hoy < fecha_inicio del curso más próximo).
    # Al exponerlo como propiedad de modelo, se centraliza la regla tanto para vistas como para templates.
    @property
    def permite_retracto(self):
        """
        Retorna True si la matrícula está en estado PAGADO y la fecha actual es anterior
        a la fecha de inicio del curso (o del curso más próximo en la orden).
        """
        if self.estado != self.ESTADO_PAGADO:
            return False
        from django.utils import timezone
        hoy = timezone.now().date()
        fechas = [det.curso.fecha_inicio for det in self.detalles.all() if det.curso and det.curso.fecha_inicio]
        if not fechas:
            return True
        return hoy < min(fechas)

    # ¿Por qué la propiedad fecha_inicio_proxima?:
    # Permite determinar dinámicamente cuál es el curso que comienza primero dentro de los programas
    # incluidos en la orden. Esto se utiliza tanto para informar con exactitud la fecha límite en el modal
    # de retracto del estudiante como para validar en el backend si el plazo de retracto sigue vigente.
    @property
    def fecha_inicio_proxima(self):
        """Retorna la fecha de inicio del curso más próximo en la orden de matrícula."""
        fechas = [det.curso.fecha_inicio for det in self.detalles.all() if det.curso and det.curso.fecha_inicio]
        return min(fechas) if fechas else None


# ==============================================================================
# BLOQUE 7: DETALLE DE LA MATRÍCULA (DetalleMatricula)
# ¿Por qué guardar 'precio_historico' en DetalleMatricula?:
# ¡Principio contable fundamental!: Si en 6 meses el curso sube o baja de precio,
# la matrícula histórica del estudiante NO debe cambiar su monto cobrado.
# Al guardar 'precio_historico' tomamos una captura (snapshot) del precio exacto al pagar.
# Además, on_delete=models.PROTECT en 'curso' impide borrar cursos que tienen historial.
# ==============================================================================
class DetalleMatricula(models.Model):
    """
    Línea de detalle de la matrícula que congela el precio histórico de venta del curso.
    """
    matricula = models.ForeignKey(
        Matricula,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Matrícula'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.PROTECT,
        related_name='detalles_matricula',
        verbose_name='Curso'
    )
    precio_historico = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Precio Histórico (CLP)'
    )

    class Meta:
        verbose_name = 'Detalle de Matrícula'
        verbose_name_plural = 'Detalles de Matrícula'

    def __str__(self):
        return f"Detalle #{self.id} (Matrícula #{self.matricula_id}) - {self.curso.titulo} (${self.precio_historico})"

    @property
    def precio_historico_clp(self):
        """Formatea el precio histórico unitario al estándar chileno: $XXX.XXX"""
        return f"${int(round(float(self.precio_historico))):,}".replace(",", ".")
