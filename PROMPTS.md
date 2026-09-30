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
*Nota: Este archivo es puramente documental y no debe ser importado por ningún módulo de Python.*
