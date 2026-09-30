# Bitácora de Prompts y Desarrollo - Plataforma EdTech
- **Alumno:** Fernando Pailahueque
- **Sección:** AP-N4-C2
- **Año Académico:** 2026
- **Tecnologías:** Django, PostgreSQL (edtech_db), Bootstrap 5, Django REST Framework (Swagger/OpenAPI).

---

## 1. Arquitectura Base y Modelado de Datos
*Registro de prompts para la definición de los 7 modelos relacionales (`CustomUser` con roles `ESTUDIANTE`/`COORDINADOR`, `AreaConocimiento`, `Curso`, `CarroMatricula`, `ItemCarro`, `Matricula`, `DetalleMatricula`) y configuración de base de datos en PostgreSQL.*

### Prompts de Instrucción y Modelado:
* **Prompt 1.1 (Configuración de Base de Datos PostgreSQL y Modelo de Usuario):**
  > "Configura el entorno de backend Django para conectarse a PostgreSQL en la base de datos `edtech_db`. Define un modelo de usuario personalizado `CustomUser` que herede de `AbstractUser`, con un campo de rol `rol` con opciones `ESTUDIANTE` y `COORDINADOR`. Asegura que los superusuarios y staff tengan acceso directo al rol de coordinador y provee propiedades de conveniencia `is_estudiante`, `is_coordinador` y `.role` para compatibilidad de nomenclatura."

* **Prompt 1.2 (Catálogo Académico y Áreas Temáticas):**
  > "Diseña el modelo `AreaConocimiento` con nombre único y descripción. Modela la entidad `Curso` vinculada a `AreaConocimiento` mediante `on_delete=models.PROTECT` para salvaguardar la integridad de las categorías temáticas. El costo de matrícula debe ser estrictamente `DecimalField(max_digits=10, decimal_places=2)` para evitar imprecisiones de punto flotante IEEE 754. Incluye cupos máximos, cupos disponibles, fechas de inicio y término, y el método `clean()` para validar que las fechas no se traslapen inversamente y que las vacantes disponibles no superen el aforo máximo."

* **Prompt 1.3 (Carro de Matrícula y Orden Formal):**
  > "Modela la persistencia del carrito de compras mediante `CarroMatricula` relacionado de forma unívoca (`OneToOneField`) con cada estudiante, evitando duplicidad de carritos activos. Define `ItemCarro` con clave compuesta única `unique_together = ('carro', 'curso')` para que la base de datos impida reservar dos veces el mismo curso. Modela la entidad `Matricula` con estados `PENDIENTE`, `PAGADO` y `CANCELADO`, y su desglose `DetalleMatricula` con `precio_historico` para congelar el valor pagado en el momento exacto del checkout respetando la trazabilidad contable."

---

## 2. Seguridad y Control de Acceso por Roles (RBAC)
*Prompts utilizados para la protección de vistas, segregación visual en la barra de navegación (Navbar), restricción de Swagger API solo para personal académico y manejo seguro de endpoints JWT.*

### Prompts de Instrucción y Seguridad:
* **Prompt 2.1 (Autenticación JWT con Claims Personalizados del Alumno):**
  > "Implementa la autenticación mediante tokens JWT usando `djangorestframework-simplejwt`. Personaliza el serializer de obtención de tokens para inyectar en la carga útil (payload) los metadatos institucionales de evaluación: `nombre_alumno: 'Fernando Pailahueque'`, `seccion: 'AP-N4-C2'`, `anio: 2026`, así como el rol y permisos del usuario autenticado."

* **Prompt 2.2 (Segregación Estricta de la Barra de Navegación):**
  > "En el Navbar institucional (`base.html`), implementa segregación de privilegios según rol (RBAC):
  > 1. 'Mi Carro' y 'Mis Matrículas' solo deben ser visibles si el usuario está autenticado Y su rol es estrictamente `ESTUDIANTE`.
  > 2. Si el usuario es anónimo (visitante no autenticado), solo debe ver el logotipo, el enlace al 'Catálogo de Cursos' y el botón 'Iniciar Sesión'. Oculta por completo el botón del carrito.
  > 3. Si el usuario es `COORDINADOR`, debe visualizar accesos directos al 'Panel Coordinador', selector de temas de campus y la documentación Swagger."

* **Prompt 2.3 (Protección de Documentación OpenAPI / Swagger y Vistas Administrativas):**
  > "Protege las rutas `/api/schema/` y `/api/docs/` (Swagger UI) para que solo usuarios autenticados con rol `COORDINADOR` o credenciales de staff puedan acceder. Protege las vistas de cierre de cupos, reactivación y cancelación mediante decoradores `@login_required`, `@user_passes_test` y `@require_POST` para impedir ataques de falsificación de peticiones en métodos destructivos."

* **Prompt 2.4 (Registro Público de Estudiantes Seguro contra Mass Assignment):**
  > "Crea la vista pública de registro de estudiantes en `registro_estudiante_view` y la plantilla `registro.html`. Asigna incondicionalmente en el backend `rol = ROLE_ESTUDIANTE` sin exponer ningún selector de roles en el formulario para evitar vulnerabilidades de elevación de privilegios (*Mass Assignment*). Hashea la contraseña con `user.set_password()` usando PBKDF2/SHA-256 e inicializa de inmediato la instancia `CarroMatricula` individual."

* **Prompt 2.5 (Inhabilitación del Panel de Administración por Defecto y Protección 404 Institucional):**
  > "Por requerimiento de seguridad institucional y buenas prácticas, inhabilita el acceso al panel administrativo por defecto de Django en `config/urls.py`: comenta o retira la ruta `path('admin/', admin.site.urls)`. Asegúrate de que cualquier intento de entrar a `/admin/` o rutas inexistentes sea interceptado por el manejador de error 404 institucional (`templates/academico/404.html`), garantizando la continuidad operativa de las vistas del coordinador (`panel_coordinador`, `catalogo`, modales de edición/eliminación) y los endpoints Swagger de la API sin dependencia de `admin.site`."

* **Prompt 2.6 (Aprovisionamiento Seguro de Nuevos Directivos y Prevención de Escalamiento RBAC):**
  > "Implementa el aprovisionamiento seguro de directivos académicos ('Alta de Coordinadores') exclusivo desde el panel administrativo privado bajo arquitectura Role-Based Access Control (RBAC):
  > 1. **Prevención de Escalamiento de Privilegios (Privilege Escalation):** El registro público de usuarios (`templates/academico/registro.html` y `registro_estudiante_view`) permanece estrictamente fijado al rol `ESTUDIANTE` en backend, neutralizando vectores de inyección por asignación masiva (*Mass Assignment*).
  > 2. **Segregación de Responsabilidades (SoD):** Solo los usuarios autenticados con rol directivo (`COORDINADOR` o credenciales de `is_staff`) tienen autorización para dar de alta a nuevos coordinadores mediante la vista protegida `crear_coordinador(request)`. Cualquier petición no autorizada emitida por estudiantes o usuarios anónimos es inmediatamente interceptada y rechazada.
  > 3. **Procesamiento Restringido por Método POST:** La vista procesa exclusivamente peticiones HTTP POST, bloqueando prefetching y peticiones GET predecibles.
  > 4. **Validación Integral de Credenciales:** Verifica la unicidad estricta de `username` y `email`, la correspondencia mutua de contraseñas (`password == confirm_password`) y una longitud mínima de seguridad.
  > 5. **Hashing Criptográfico y Persistencia:** Instancia `CustomUser` con `role='COORDINADOR'` aplicando el algoritmo seguro PBKDF2/SHA-256 (`set_password()`), retornando feedback institucional a través de `django.contrib.messages` y redirigiendo siempre al `panel_coordinador`.
  > 6. **Interfaz de Control Directivo:** En la cabecera de `panel_coordinador.html`, integra el botón institucional `<i class='bi bi-person-plus-fill'></i> Registrar Nuevo Coordinador` junto al modal in-situ `#modalCrearCoordinador` con validación defensiva del lado del cliente."

---

## 3. Lógica Transaccional y Control de Cupos
*Prompts para transacciones atómicas (`transaction.atomic` con `select_for_update`), prevención de sobreventa de cupos, confirmación de compras y reposición automática de vacantes ante cancelaciones.*

### Prompts de Lógica y Transacciones:
* **Prompt 3.1 (Checkout Atómico con Bloqueo Pesimista):**
  > "Implementa el endpoint y vista de checkout de matrícula utilizando `transaction.atomic()` y bloqueo pesimista `select_for_update()` a nivel de base de datos sobre los cursos seleccionados. Si 10 estudiantes intentan matricular el último cupo en el mismo milisegundo, la base de datos debe atender en serie, otorgar la vacante al primero y arrojar error de cupos agotados a los siguientes, evitando condiciones de carrera (Race Conditions). Si ocurre un fallo en cualquier ítem, toda la transacción debe revertirse mediante rollback."

* **Prompt 3.2 (Descuento de Cupos y Vaciado de Carrito):**
  > "Al confirmar el pago exitoso, descuenta automáticamente 1 unidad en `cupos_disponibles` por cada curso involucrado, genera el registro de `Matricula` con estado `PAGADO`, crea los registros correspondientes en `DetalleMatricula` guardando el `precio_historico`, y vacía los ítems del carro del estudiante de manera indivisible."

* **Prompt 3.3 (Reposición Automática de Inventario en Cancelaciones):**
  > "En las acciones de cancelación de matrículas por parte del Coordinador (`cancelar_matricula_coordinador_view` y `cambiar_estado_matricula_web_view`), cuando una matrícula pasa al estado `CANCELADO`, ejecuta una transacción atómica que reponga de inmediato +1 cupo disponible a cada uno de los cursos asociados, sin sobrepasar nunca el valor de `cupos_maximos`."

---

## 4. Gestión de Infraestructura Física y Aforo
*Prompts para la asignación de laboratorios, conteo de computadores por sala, validación de cruce de horarios/salas y modal in-situ de creación y edición rápida de programas.*

### Prompts de Infraestructura y Salas:
* **Prompt 4.1 (Coherencia Física de Equipamiento en Modelos):**
  > "Agrega a la entidad `Curso` los campos `laboratorio` (CharField) y `cantidad_computadores` (PositiveIntegerField con valor por defecto 20). En el método `clean()` del modelo, implementa la regla de coherencia física: los cupos máximos ofrecidos (`cupos_maximos`) no pueden superar la capacidad física del laboratorio (`cantidad_computadores` PCs). Asegura que `cupos_disponibles` no supere `cupos_maximos`."

* **Prompt 4.2 (Algoritmo de Detección de Colisiones de Salas por Fecha):**
  > "En la vista `editar_curso_coordinador_view`, implementa un algoritmo de detección de conflictos de laboratorio. Verifica si existe otro curso distinto al actual que comparta el mismo laboratorio en fechas cruzadas usando la fórmula de intersección de intervalos: `fecha_inicio__lte=termino_date` y `fecha_termino__gte=inicio_date`. Si existe conflicto, notifica al directivo mediante una advertencia flash preventiva (`messages.warning`) sin corromper la persistencia de datos."

* **Prompt 4.3 (Borrado Seguro con Integridad Referencial de Aforo):**
  > "En `eliminar_curso_coordinador_view`, implementa protección de registros académicos: si el curso posee inscripciones históricas (`curso.detallematricula_set.exists()`), bloquea la eliminación informando que deben pausarse las admisiones. Si el curso está libre de matrículas oficiales pero figura en carritos de compra, limpia primero los `ItemCarro` huérfanos antes de invocar `curso.delete()` para evitar errores 404 al alumnado."

* **Prompt 4.4 (Asistencia Reactiva en Formularios y Modales In-Situ):**
  > "En el catálogo, añade modales in-situ `modalEditarCurso{{ curso.id }}` y `modalNuevoCurso`. Desarrolla scripts JavaScript de asistencia defensiva en tiempo real (UX) que sincronicen la cantidad de computadores con los cupos sugeridos, ajusten dinámicamente el límite máximo `inputCupos.max = pcs` y desactiven el botón de envío si el usuario intenta exceder la capacidad de la sala."

* **Prompt 4.5 (Patrón de Borrado Lógico - Soft Delete, Reactivación y Preservación Histórica y Contable):**
  > "Implementa el patrón de Borrado Lógico (*Soft Delete*) y reactivación de programas académicos en el catálogo y panel directivo:
  > 1. **Integridad Referencial y Trazabilidad Histórica:** En lugar de ejecutar destrucción física (`curso.delete()` / *Hard Delete*) —lo cual corrompe llaves foráneas en `DetalleMatricula`, rompe la trazabilidad contable o exige cascadas destructivas—, el modelo `Curso` preserva su estado operativo mediante `activo = models.BooleanField(default=True)` y `fecha_desactivacion = models.DateTimeField(null=True, blank=True)`.
  > 2. **Refactorización a Borrado Lógico en `eliminar_curso_coordinador_view`:**
  >    - Vista protegida exclusivamente para directivos con rol `COORDINADOR`.
  >    - Si el curso tiene ítems activos en carritos de compra de estudiantes (`ItemCarro`), se purgan de forma defensiva para prevenir inconsistencias en checkout.
  >    - Se marca `curso.activo = False` y `curso.fecha_desactivacion = timezone.now()`, persistiendo con `curso.save(update_fields=['activo', 'fecha_desactivacion'])` sin eliminar la tupla en PostgreSQL.
  >    - Emite mensaje flash institucional: *'El programa ha sido archivado y retirado del catálogo público sin alterar registros históricos.'* y redirige a `panel_coordinador`.
  > 3. **Reactivación Operativa (`reactivar_curso`):**
  >    - Vista exclusiva para directivos (`COORDINADOR`) protegida por método POST.
  >    - Restituye `curso.activo = True` y `curso.fecha_desactivacion = None`, reincorporando de inmediato el programa a la oferta académica visible.
  >    - Emite mensaje flash: *'El programa ha sido reactivado y vuelve a estar visible en el catálogo de admisiones.'* y redirige a `panel_coordinador`.
  > 4. **Segregación de Consultas y Catálogo Público:**
  >    - La vista pública del catálogo (`catalogo_cursos` / `catalogo_view`) aplica un filtro base estricto `Curso.objects.filter(activo=True)`, garantizando que postulantes y estudiantes jamás visualicen programas archivados.
  >    - En `panel_coordinador_view`, se segmenta explícitamente `cursos_activos` de `cursos_archivados`, recalculando aforos y cupos únicamente sobre los programas en operación activa.
  > 5. **Interfaz de Gestión y Auditoría en `panel_coordinador.html`:**
  >    - Reemplaza en el catálogo la acción destructiva por 'Archivar / Dar de Baja'.
  >    - Incorpora la sección y pestaña dedicada *'Historial de Programas Archivados ({{ cursos_archivados|length }})'*, mostrando nombre, área, fecha/hora de retiro y el botón transaccional seguro *'<i class=\"bi bi-arrow-counterclockwise\"></i> Reactivar Programa'*.
  > 6. **Trazabilidad Informativa y Feedback Visual de Programas Archivados:**
  >    - En `panel_coordinador.html`, el modal de confirmación `#modalArchivarCurso-{{ c.id }}` incorpora la advertencia preventiva obligatoria: *\"Si este curso cuenta con estudiantes matriculados, se mantendrán sus comprobantes históricos intactos y solo se suspenderá la admisión a nuevos postulantes.\"*
  >    - En `mis_matriculas.html`, si un programa formalizado en una matrícula activa (`PAGADO`) es archivado posteriormente por el coordinador, se despliega la insignia sutil `<span class=\"badge bg-secondary text-white\"><i class=\"bi bi-archive-fill\"></i> Convocatoria Cerrada en Catálogo</span>` junto al título del curso, y se exhibe en el comprobante la alerta institucional: *\"Aviso Académico: La oferta pública de este programa se encuentra cerrada en el catálogo general. Tu reserva oficial y comprobante siguen vigentes para el periodo académico asignado. Si no deseas cursarlo, mantienes habilitada la opción de 'Solicitar Retracto / Anular'.\"*

---

## 5. UI/UX Institucional y Manejo de Errores
*Prompts para la directriz de fondo blanco (`#ffffff`), formateo de moneda chilena (`CLP $XXX.XXX` sin decimales), selector de identidades visuales para el coordinador y blindaje de la plantilla de error 404 personalizada.*

### Prompts de Experiencia Visual y Normalización:
* **Prompt 5.1 (Directriz de Fondo Blanco Institucional y Contraste):**
  > "Aplica una directriz de diseño sobrio y profesional basada en tarjetas (`card-custom`) con fondo blanco puro (`#ffffff`), contorno slate definido (`1.5px solid #cbd5e1`) y zócalo inferior diferenciado (`card-footer-action`). Esto resuelve la saturación visual, proporciona estructura tridimensional y garantiza contraste sobre el canvas global `#e5ebf3`."

* **Prompt 5.2 (Filtro de Formato de Moneda Chilena CLP):**
  > "Desarrolla el template tag personalizado `formato_clp` en `academico/templatetags/moneda_tags.py`. Formatea las cifras al estándar de Chile: sin decimales y con puntos separadores de miles (ejemplo: `$450.000 (CLP)`). Reemplaza cualquier referencia textual a 'pesos chilenos' por la denominación oficial `(CLP)`."

* **Prompt 5.3 (Módulo de Identidad Visual Institucional - Selector de Campus):**
  > "Diseña un Selector de Temas de Campus exclusivo para el rol COORDINADOR ubicado en el Navbar:
  > - Define 4 paletas cromáticas con variables CSS (`:root` y atributos `[data-theme]`):
  >   1. **Esmeralda Tech** (`#059669` / verde esmeralda institucional recomendado).
  >   2. **Púrpura Cyber** (`#7c3aed`).
  >   3. **Azul Medianoche** (`#2563eb`).
  >   4. **Carmesí Vulcano** (`#e11d48`).
  > - Conecta el navbar, botones principales, insignias y ribetes superiores de las tarjetas a las variables dinámicas del tema.
  > - Ejecuta el script de carga de tema en el `<head>` y persiste la elección en `localStorage` para evitar parpadeos de estilo (FOUC) entre navegaciones."

* **Prompt 5.4 (Manejador Global de Error HTTP 404 Institucional):**
  > "Implementa la vista personalizada `custom_404_view` y su plantilla `404.html`. Si la petición entrante solicita una ruta de API (`/api/`) o encabezado `application/json`, retorna una respuesta JSON estructurada con código 404; si proviene del navegador web, renderiza una interfaz amigable que preserve la barra de navegación, el fondo institucional y el footer obligatorio con los datos del alumno: `Fernando Pailahueque | AP-N4-C2 | 2026`."

---

## 6. Ciclo de Vida, Retracto Legal y Auditoría Completa de Matrículas
*Prompts para la anulación formal de matrículas, derecho de retracto voluntario del estudiante, anulación administrativa por coordinación, reposición atómica de cupos y auditoría de cambios.*

### Prompts de Instrucción y Ciclo de Vida:
* **Prompt 6.1 (Modelado de Estados de Matrícula y Campos de Auditoría):**
  > "En el modelo `Matricula`, define las opciones de estado: `ESTADOS = [('PAGADO', 'Pagado'), ('ANULADA', 'Anulada')]`. Incorpora los campos de auditoría: `motivo_anulacion` (TextField opcional), `fecha_anulacion` (DateTimeField opcional) y `anulado_por` (`ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='matriculas_anuladas')`). Añade propiedades de conveniencia `permite_retracto` y `fecha_inicio_proxima` para validar si la fecha actual es anterior a la fecha de inicio del curso más próximo en la orden."

* **Prompt 6.2 (Control Transaccional y Reposición Atómica de Cupos):**
  > "1. Desarrolla la vista `anular_matricula_estudiante(request, matricula_id)` protegida con `@login_required`: valida que la matrícula pertenezca a `request.user` y se encuentre en estado `PAGADO`. Valida el plazo legal de retracto: solo permite la anulación si la fecha actual es anterior a la fecha de inicio del programa (o del curso más próximo en la orden); si ya inició, deniega con un mensaje de error informativo. Ejecuta dentro de un bloque `with transaction.atomic():` el cambio de estado a `ANULADA`, `fecha_anulacion = timezone.now()`, `motivo_anulacion = 'Retracto voluntario ejercido por el estudiante'`, `anulado_por = request.user`, y la reposición segura de +1 cupo disponible por cada curso involucrado (cuidando no exceder `cupos_maximos`).
  > 2. Desarrolla la vista `anular_matricula_coordinador(request, matricula_id)` protegida para usuarios con rol `COORDINADOR` o staff: recibe vía POST el campo obligatorio `motivo`. Ejecuta en `with transaction.atomic():` el cambio a `ANULADA`, la restitución atómica de cupos y el registro de fecha, motivo y `anulado_por = request.user`."

* **Prompt 6.3 (Mapeo de Rutas Web):**
  > "En `academico/urls.py`, registra las rutas:
  > - `path('matricula/<int:matricula_id>/anular/', anular_matricula_estudiante, name='anular_matricula_estudiante')`
  > - `path('coordinador/matricula/<int:matricula_id>/anular/', anular_matricula_coordinador, name='anular_matricula_coordinador')`"

* **Prompt 6.4 (Interfaz de Estudiante y Aviso Institucional de Anulación):**
  > "En `mis_matriculas.html`:
  > - Para órdenes con estado `PAGADO` con plazo de retracto vigente, despliega el botón secundario 'Solicitar Retracto / Anular' con un modal de confirmación claro y detallado.
  > - Para matrículas en estado `ANULADA`, muestra la insignia `ANULADA` y renderiza el recuadro de aviso institucional indicando textualmente:
  >   `'Matrícula Anulada el {{ matricula.fecha_anulacion|date:'d/m/Y H:i' }} hrs. Motivo: {{ matricula.motivo_anulacion }}'`.
  > - Excluye los montos de matrículas anuladas del cálculo del resumen superior 'Inversión Total (Pagado)'."

* **Prompt 6.5 (Interfaz del Panel de Coordinación):**
  > "En `panel_coordinador.html`, añade en la tabla de órdenes de matrícula la opción 'Anular Matrícula', la cual abre un modal interactivo que solicita obligatoriamente el motivo de la anulación antes de enviar la petición POST a `anular_matricula_coordinador`."

* **Prompt 6.6 (Resolución de Conflicto de Superposición y Backdrop en Modal de Retracto del Estudiante):**
  > "Corrige el modal de retracto en `academico/templates/academico/mis_matriculas.html` y su envío transaccional:
  > 1. Problema detectado: Se visualizaban dos modales superpuestos simultáneamente (título y textos montados/duplicados) y al pulsar 'Confirmar Retracto / Anulación' no se enviaba la petición ni se ejecutaba la acción.
  > 2. Solución en `mis_matriculas.html`:
  >    - Asignar identificadores dinámicos y únicos para cada modal por matrícula: botón con `data-bs-toggle="modal" data-bs-target="#modalRetracto-{{ m.id }}"` y contenedor `<div class="modal fade" id="modalRetracto-{{ m.id }}" ...>`.
  >    - Asegurar que no existan modales duplicados en el HTML (un solo modal por matrícula dentro o fuera del ciclo).
  >    - Verificar la estructura limpia del formulario dentro del modal: `<form method="POST" action="{% url 'anular_matricula_estudiante' m.id %}">` con `{% csrf_token %}` y botón de envío `<button type="submit" class="btn btn-danger">Confirmar Retracto / Anulación</button>`.
  >    - Aislar el modal fuera de los contenedores `.card` para evitar que estilos con `overflow: hidden` o `z-index` conflictivo provoquen que el fondo oscuro de Bootstrap (`.modal-backdrop`) bloquee o intercepte los clics del usuario."

* **Prompt 6.7 (Corrección de Foster-Parenting del DOM y Desbloqueo de Modal de Anulación Administrativa del Coordinador):**
  > "Corrige de inmediato el modal de anulación administrativa en `academico/templates/academico/panel_coordinador.html` y `coordinador.html`:
  > 1. Diagnóstico del fallo: El modal de anulación se encontraba duplicado en el DOM (se apreciaban dos modales superpuestos simultáneamente con textos y botones montados). Los clics en el textarea y en 'Confirmar Anulación' quedaban interceptados por la superposición de elementos.
  > 2. Causa raíz técnica: Cuando se declaran estructuras complejas `<div class="modal">` dentro de celdas `<td>` o dentro de `<div class="table-responsive">`, el algoritmo de parseo HTML de los navegadores ejecuta *foster-parenting* (expulsión y duplicación de nodos inválidos fuera de la tabla), generando dos instancias idénticas del diálogo en el DOM. Además, el contenedor con scroll horizontal crea un nuevo contexto de apilamiento (*stacking context*) que hace que el backdrop `z-index: 1050` quede por encima del contenido interactivo, interceptando todos los eventos de puntero (*pointer-events*).
  > 3. Corrección requerida:
  >    - En la tabla de órdenes de matrícula, mantener exclusivamente el botón disparador: `data-bs-toggle="modal" data-bs-target="#modalAnularCoord-{{ m.id }}"`.
  >    - Extraer la totalidad de los modales fuera de `<table>` y fuera de `<div class="table-responsive">`, ubicándolos en un ciclo dedicado al pie del contenedor principal.
  >    - Asegurar identificadores únicos `modalAnularCoord-{{ m.id }}` con formulario POST a `{% url 'anular_matricula_coordinador' m.id %}`, token `{% csrf_token %}`, `<textarea name="motivo" class="form-control" rows="3" required placeholder="..."></textarea>` y botones funcionales."

* **Prompt 6.8 (Estandarización de Comentarios Pedagógicos en Código Nuevo):**
  > "Incorpora comentarios explicativos siguiendo el estándar pedagógico institucional del proyecto (`# ¿Por qué <técnica/decisión>?: <fundamento>`) en todos los nuevos componentes del ciclo de vida y anulación de matrículas:
  > - En `models.py`: justificación de los campos de auditoría (`motivo_anulacion`, `fecha_anulacion`, `anulado_por`), y de las propiedades `permite_retracto` y `fecha_inicio_proxima`.
  > - En `views.py`: justificación de la protección RBAC, validación de plazo legal pre-inicio y uso de `select_for_update()` con verificación de techo `cupos_maximos` para reposición atómica sin inconsistencias de sobrecupo.
  > - En `serializers.py`: justificación del uso explícito de `serializers.ChoiceField` con opciones extendidas (`PENDIENTE`, `PAGADO`, `CANCELADO`, `ANULADA`) para mantener retrocompatibilidad sin acoplamiento rígido al modelo.
  > - En `urls.py`: justificación de la segregación de endpoints dedicados por rol.
  > - En plantillas HTML: comentarios `{# ¿Por qué ...?: #}` documentando la solución a los conflictos de apilamiento (*stacking context*), *foster-parenting* y aislamiento de modales de Bootstrap fuera de tablas y tarjetas."

* **Prompt 6.9 (Estandarización de Comentarios Pedagógicos en Soft Delete, Reactivación y Feedback de Programas Archivados):**
  > "Incorpora y estandariza los comentarios explicativos con el patrón pedagógico institucional (`# ¿Por qué <técnica/decisión>?: <fundamento>` en Python y `{# ¿Por qué ...?: <fundamento> #}` en plantillas Django) en todos los módulos de Borrado Lógico y Reactivación de Programas:
  > - En `academico/models.py`: justificación de los campos `activo` y `fecha_desactivacion` en `Curso`, y de la propiedad `tiene_cursos_archivados` en `Matricula`.
  > - En `academico/views.py`: justificación del filtrado estricto `Curso.objects.filter(activo=True)` en `catalogo_view`, la segregación de `cursos_activos` y `cursos_archivados` en `panel_coordinador_view`, el resguardo de integridad referencial histórica en `eliminar_curso_coordinador_view` (Soft Delete) y la restauración limpia de oferta en `reactivar_curso`.
  > - En `academico/urls.py`: justificación de los endpoints segregados `coordinador/curso/<int:curso_id>/archivar/` y `coordinador/curso/<int:curso_id>/reactivar/`.
  > - En `mis_matriculas.html`: justificación de la insignia 'Convocatoria Cerrada en Catálogo' y de la alerta informativa preventiva en comprobantes pagados.
  > - En `panel_coordinador.html`: justificación del modal `#modalArchivarCurso-{{ c.id }}` con advertencia preventiva sobre la preservación de órdenes históricas y de la sección 'Historial de Programas Archivados'."

---
*Nota: Este archivo es puramente documental y no debe ser importado por ningún módulo de Python.*

