"""
Batería de Pruebas Automatizadas - Plataforma EdTech
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .models import (
    AreaConocimiento,
    Curso,
    CarroMatricula,
    ItemCarro,
    Matricula,
    DetalleMatricula,
)
from .templatetags.moneda_tags import formato_clp

User = get_user_model()


class EdTechTestSuite(TestCase):
    def setUp(self):
        # 1. Crear usuarios de prueba
        self.coordinador = User.objects.create_user(
            username='coordinador_admin',
            password='Coord2026!',
            email='coord@edtech.cl',
            rol=User.ROLE_COORDINADOR,
            is_staff=True,
            is_superuser=True
        )

        self.estudiante = User.objects.create_user(
            username='estudiante_1',
            password='Est2026!',
            email='estudiante@edtech.cl',
            rol=User.ROLE_ESTUDIANTE
        )

        # 2. Crear Área y Cursos
        self.area_web = AreaConocimiento.objects.create(
            nombre='Desarrollo Web',
            descripcion='Área de Desarrollo Web'
        )

        self.curso_django = Curso.objects.create(
            area=self.area_web,
            titulo='Bootcamp Full Stack Django',
            descripcion='Curso avanzado de Django y DRF',
            costo_matricula=Decimal('450000.00'),
            fecha_inicio=date(2026, 10, 15),
            fecha_termino=date(2026, 12, 20),
            cupos_maximos=2,
            cupos_disponibles=2,
            activo=True
        )

        self.curso_agotado = Curso.objects.create(
            area=self.area_web,
            titulo='Taller Sin Cupos',
            descripcion='Curso sin cupos de prueba',
            costo_matricula=Decimal('100000.00'),
            fecha_inicio=date(2026, 10, 1),
            fecha_termino=date(2026, 10, 10),
            cupos_maximos=5,
            cupos_disponibles=0,
            activo=True
        )

        # Clientes HTTP
        self.client = Client()
        self.api_client = APIClient()

    # =========================================================================
    # TEST 1: AUTENTICACIÓN JWT CON CLAIMS PERSONALIZADOS DEL ALUMNO
    # =========================================================================
    def test_custom_jwt_claims(self):
        url = reverse('token_obtain_pair')
        response = self.api_client.post(url, {
            'username': 'estudiante_1',
            'password': 'Est2026!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertIn('academico_info', data)
        self.assertEqual(data['nombre_alumno'], 'Fernando Pailahueque')
        self.assertEqual(data['seccion'], 'AP-N4-C2')
        self.assertEqual(data['anio'], 2026)
        self.assertEqual(data['user']['role'], 'ESTUDIANTE')

    # =========================================================================
    # TEST 2: DOCUMENTACIÓN SWAGGER / OPENAPI
    # =========================================================================
    def test_swagger_and_schema_endpoints(self):
        schema_url = reverse('schema')
        schema_resp = self.client.get(schema_url)
        self.assertEqual(schema_resp.status_code, 200)

        swagger_url = reverse('swagger-ui')
        swagger_resp = self.client.get(swagger_url)
        self.assertEqual(swagger_resp.status_code, 200)
        self.assertContains(swagger_resp, 'swagger-ui')

    # =========================================================================
    # TEST 3: GESTIÓN DE CARRO Y CONTROL DE CUPOS VÍA API
    # =========================================================================
    def test_carro_api_flow(self):
        self.api_client.force_authenticate(user=self.estudiante)

        carro_url = reverse('api-carro')
        resp = self.api_client.get(carro_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()['items']), 0)

        add_resp = self.api_client.post(carro_url, {'curso_id': self.curso_django.id})
        self.assertEqual(add_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(add_resp.json()['items']), 1)

        dup_resp = self.api_client.post(carro_url, {'curso_id': self.curso_django.id})
        self.assertEqual(dup_resp.status_code, status.HTTP_400_BAD_REQUEST)

        sin_cupo_resp = self.api_client.post(carro_url, {'curso_id': self.curso_agotado.id})
        self.assertEqual(sin_cupo_resp.status_code, status.HTTP_400_BAD_REQUEST)

    # =========================================================================
    # TEST 4: CHECKOUT ATÓMICO (DESCUENTO DE CUPOS Y CREACIÓN DE MATRÍCULA)
    # =========================================================================
    def test_checkout_atomico_api(self):
        self.api_client.force_authenticate(user=self.estudiante)
        carro_url = reverse('api-carro')
        self.api_client.post(carro_url, {'curso_id': self.curso_django.id})

        cupos_antes = Curso.objects.get(pk=self.curso_django.id).cupos_disponibles
        self.assertEqual(cupos_antes, 2)

        checkout_url = reverse('api-confirmar-matricula')
        checkout_resp = self.api_client.post(checkout_url, {})
        self.assertEqual(checkout_resp.status_code, status.HTTP_201_CREATED)

        curso_actualizado = Curso.objects.get(pk=self.curso_django.id)
        self.assertEqual(curso_actualizado.cupos_disponibles, 1)

        matricula_data = checkout_resp.json()['matricula']
        self.assertEqual(matricula_data['estado'], 'PAGADO')
        self.assertEqual(Decimal(str(matricula_data['total'])), Decimal('450000.00'))

        carro = CarroMatricula.objects.get(estudiante=self.estudiante)
        self.assertEqual(carro.items.count(), 0)

    # =========================================================================
    # TEST 5: CAMBIO DE ESTADO Y REPOSICIÓN DE CUPOS AL CANCELAR
    # =========================================================================
    def test_cambio_estado_reposicion_cupos(self):
        self.api_client.force_authenticate(user=self.estudiante)
        self.api_client.post(reverse('api-carro'), {'curso_id': self.curso_django.id})
        checkout_resp = self.api_client.post(reverse('api-confirmar-matricula'), {})
        matricula_id = checkout_resp.json()['matricula']['id']

        self.assertEqual(Curso.objects.get(pk=self.curso_django.id).cupos_disponibles, 1)

        self.api_client.force_authenticate(user=self.coordinador)
        cambiar_url = reverse('api-cambiar-estado-matricula', kwargs={'pk': matricula_id})
        patch_resp = self.api_client.patch(cambiar_url, {'estado': 'CANCELADO'})
        self.assertEqual(patch_resp.status_code, status.HTTP_200_OK)

        self.assertEqual(Curso.objects.get(pk=self.curso_django.id).cupos_disponibles, 2)

    # =========================================================================
    # TEST 6: VISTAS WEB HTML & ERROR 404 CON DATOS DEL ALUMNO
    # =========================================================================
    def test_web_views_and_footer(self):
        home_resp = self.client.get(reverse('catalogo'))
        self.assertEqual(home_resp.status_code, 200)
        self.assertContains(home_resp, 'Fernando Pailahueque')
        self.assertContains(home_resp, 'AP-N4-C2')
        self.assertContains(home_resp, '2026')

        not_found_resp = self.client.get('/ruta-inexistente-para-prueba-404/')
        self.assertEqual(not_found_resp.status_code, 404)
        self.assertContains(not_found_resp, 'Fernando Pailahueque', status_code=404)
        self.assertContains(not_found_resp, 'AP-N4-C2', status_code=404)

        api_404_resp = self.client.get('/api/ruta-inexistente-404/')
        self.assertEqual(api_404_resp.status_code, 404)
        json_data = api_404_resp.json()
        self.assertEqual(json_data['status'], 404)
        self.assertEqual(json_data['datos_evaluacion']['alumno'], 'Fernando Pailahueque')

        # ¿Por qué verificamos la inhabilitación del panel /admin/?:
        # Aquí utilicé self.client.get('/admin/') para validar que por requerimiento de seguridad
        # institucional y buenas prácticas, el acceso al panel administrativo por defecto de Django
        # esté inhabilitado en config/urls.py y sea interceptado por el manejador de error 404 institucional
        # (templates/academico/404.html), mostrando la información del alumno Fernando Pailahueque (AP-N4-C2, 2026).
        admin_resp = self.client.get('/admin/')
        self.assertEqual(admin_resp.status_code, 404)
        self.assertContains(admin_resp, 'Fernando Pailahueque', status_code=404)
        self.assertContains(admin_resp, 'AP-N4-C2', status_code=404)
        self.assertContains(admin_resp, '2026', status_code=404)
        self.assertTemplateUsed(admin_resp, 'academico/404.html')

    # =========================================================================
    # TEST 7: PERMISOS VISUALES EN EL NAVBAR POR ROL
    # =========================================================================
    def test_navbar_permissions_by_role(self):
        # 1. Sesión Anónima (Visitante)
        resp_anon = self.client.get(reverse('catalogo'))
        self.assertNotContains(resp_anon, 'id="themeDropdown"')
        self.assertNotContains(resp_anon, 'id="nav-cart-btn"')
        self.assertNotContains(resp_anon, 'Mis Matrículas')

        # 2. Sesión como Estudiante
        self.client.force_login(self.estudiante)
        resp_estudiante = self.client.get(reverse('catalogo'))
        self.assertContains(resp_estudiante, 'Mi Carro')
        self.assertContains(resp_estudiante, 'Mis Matrículas')
        self.assertNotContains(resp_estudiante, 'Panel Coordinador')
        self.assertNotContains(resp_estudiante, 'API Swagger')
        self.assertNotContains(resp_estudiante, 'id="themeDropdown"')

        # 3. Sesión como Coordinador
        self.client.force_login(self.coordinador)
        resp_coord = self.client.get(reverse('catalogo'))
        self.assertContains(resp_coord, 'Panel Coordinador')
        self.assertContains(resp_coord, 'API Swagger')
        self.assertNotContains(resp_coord, 'id="nav-cart-btn"')
        self.assertContains(resp_coord, 'id="themeDropdown"')
        self.assertContains(resp_coord, 'Tema Campus')
        self.assertContains(resp_coord, 'Carmesí Vulcano')

    # =========================================================================
    # TEST 8: ACCIONES WEB EXCLUSIVAS DE COORDINADOR (CERRAR/RESTABLECER Y CANCELAR)
    # =========================================================================
    def test_acciones_web_coordinador(self):
        # 1. Cerrar cupos (setea cupos_disponibles = 0)
        self.client.force_login(self.coordinador)
        cerrar_url = reverse('cerrar_cupos_curso', kwargs={'curso_id': self.curso_django.id})
        resp_cerrar = self.client.post(cerrar_url)
        self.assertEqual(resp_cerrar.status_code, 302)
        self.assertEqual(Curso.objects.get(pk=self.curso_django.id).cupos_disponibles, 0)

        # 2. Restablecer cupos (cupos_disponibles = cupos_maximos = 2)
        restablecer_url = reverse('restablecer_cupos_curso', kwargs={'curso_id': self.curso_django.id})
        resp_rest = self.client.post(restablecer_url)
        self.assertEqual(resp_rest.status_code, 302)
        self.assertEqual(Curso.objects.get(pk=self.curso_django.id).cupos_disponibles, 2)

        # 3. Matricular y Cancelar Matrícula con reposición automática
        self.client.force_login(self.estudiante)
        self.client.get(reverse('agregar_carro', kwargs={'curso_id': self.curso_django.id}))
        self.client.post(reverse('checkout_web'))
        self.assertEqual(Curso.objects.get(pk=self.curso_django.id).cupos_disponibles, 1)

        matricula = Matricula.objects.filter(estudiante=self.estudiante).first()
        self.assertIsNotNone(matricula)

        # Coordinador cancela la matrícula
        self.client.force_login(self.coordinador)
        cancelar_url = reverse('cancelar_matricula_coordinador', kwargs={'matricula_id': matricula.id})
        resp_cancel = self.client.post(cancelar_url)
        self.assertEqual(resp_cancel.status_code, 302)

        matricula.refresh_from_db()
        self.assertEqual(matricula.estado, 'CANCELADO')
        # Cupos repuestos a 2
        self.assertEqual(Curso.objects.get(pk=self.curso_django.id).cupos_disponibles, 2)

        # 4. Estudiante no tiene permiso para ejecutar estas acciones
        self.client.force_login(self.estudiante)
        resp_unauth = self.client.post(cerrar_url)
        self.assertEqual(resp_unauth.status_code, 302)
        self.assertIn(reverse('catalogo'), resp_unauth.url)

    # =========================================================================
    # TEST 9: COHERENCIA DE ROLES EN CATÁLOGO Y BLOQUEO DE CARRO A COORDINADOR
    # =========================================================================
    def test_coordinador_catalogo_controls_and_cart_security(self):
        # 1. Vista de catálogo como Coordinador
        self.client.force_login(self.coordinador)
        resp_coord = self.client.get(reverse('catalogo'))
        self.assertContains(resp_coord, 'Control Administrativo')
        self.assertContains(resp_coord, 'Gestionar en Panel')
        self.assertContains(resp_coord, 'Pausar Admisión')
        self.assertNotContains(resp_coord, f'id="btn-add-cart-{self.curso_django.id}"')

        # 2. Acción rápida desde catálogo con next='catalogo'
        cerrar_url = reverse('cerrar_cupos_curso', kwargs={'curso_id': self.curso_django.id})
        resp_pausar = self.client.post(cerrar_url, {'next': 'catalogo'}, follow=True)
        self.assertContains(resp_pausar, f'Matrícula cerrada para {self.curso_django.titulo}')
        self.assertContains(resp_pausar, 'Reabrir Cupos')
        self.assertEqual(Curso.objects.get(pk=self.curso_django.id).cupos_disponibles, 0)

        # 3. Coordinador intenta agregar al carro directamente vía URL -> Debe ser rechazado
        curso_con_cupos = Curso.objects.create(
            area=self.area_web,
            titulo='Curso Extra Con Cupos',
            descripcion='Curso disponible para matrícula',
            costo_matricula=Decimal('200000.00'),
            fecha_inicio=date(2026, 11, 1),
            fecha_termino=date(2026, 12, 1),
            cupos_maximos=5,
            cupos_disponibles=5,
            activo=True
        )
        add_url = reverse('agregar_carro', kwargs={'curso_id': curso_con_cupos.id})
        resp_add = self.client.get(add_url, follow=True)
        self.assertRedirects(resp_add, reverse('catalogo'))
        self.assertContains(resp_add, 'Acción no permitida: Los coordinadores académicos no pueden agregar cursos al carro')

        carro_coord = CarroMatricula.objects.filter(estudiante=self.coordinador).first()
        if carro_coord:
            self.assertEqual(carro_coord.items.count(), 0)

        # 4. Vista de catálogo como Estudiante
        self.client.force_login(self.estudiante)
        resp_estudiante = self.client.get(reverse('catalogo'))
        self.assertNotContains(resp_estudiante, 'Control Administrativo')
        self.assertNotContains(resp_estudiante, 'Gestionar en Panel')
        # Para el curso con 0 cupos (curso_django) muestra "Sin Cupos Disponibles"
        self.assertContains(resp_estudiante, 'Sin Cupos Disponibles')
        # Para el curso con cupos muestra "Agregar al Carro"
        self.assertContains(resp_estudiante, 'Agregar al Carro')

    # =========================================================================
    # TEST 10: FORMATEO VISUAL DE MONEDA ESTÁNDAR CHILENO (CLP)
    # =========================================================================
    def test_formato_moneda_clp_estandar_chileno(self):
        # 1. Validación de Template Filter `formato_clp`
        self.assertEqual(formato_clp(450000), '$450.000')
        self.assertEqual(formato_clp(Decimal('450000.00')), '$450.000')
        self.assertEqual(formato_clp(1250000), '$1.250.000')
        self.assertEqual(formato_clp(0), '$0')
        self.assertEqual(formato_clp(None), '$0')

        # 2. Validación de Properties auxiliares en modelos
        # Curso.costo_clp
        self.assertEqual(self.curso_django.costo_clp, '$450.000')

        # CarroMatricula.total_clp
        carro = CarroMatricula.objects.create(estudiante=self.estudiante)
        ItemCarro.objects.create(carro=carro, curso=self.curso_django)
        self.assertEqual(carro.total_clp, '$450.000')

        # Matricula.total_clp y DetalleMatricula.precio_historico_clp
        matricula = Matricula.objects.create(
            estudiante=self.estudiante,
            total=Decimal('450000.00'),
            estado='PAGADO'
        )
        detalle = DetalleMatricula.objects.create(
            matricula=matricula,
            curso=self.curso_django,
            precio_historico=Decimal('450000.00')
        )
        self.assertEqual(matricula.total_clp, '$450.000')
        self.assertEqual(detalle.precio_historico_clp, '$450.000')

        # 3. Validación de renderizado en plantillas HTML

        # A) Catálogo: curso.costo_clp visible sin decimales
        resp_cat = self.client.get(reverse('catalogo'))
        self.assertContains(resp_cat, '$450.000')
        self.assertNotContains(resp_cat, '$450 000,00')
        self.assertNotContains(resp_cat, '$450.000,00')

        # B) Carro de compra: item.curso.costo_clp y carro.total_clp
        self.client.force_login(self.estudiante)
        resp_carro = self.client.get(reverse('carro'))
        self.assertContains(resp_carro, '$450.000 CLP')
        self.assertContains(resp_carro, 'id="total-pago-text">$450.000</span>')
        self.assertNotContains(resp_carro, '$450 000,00')

        # C) Mis Matrículas: total_clp y precio_historico_clp
        resp_mis_mat = self.client.get(reverse('mis_matriculas'))
        self.assertContains(resp_mis_mat, '$450.000 CLP')
        self.assertNotContains(resp_mis_mat, '$450 000,00')

        # D) Panel Coordinador: costo_clp y total_clp en tablas y KPIs
        self.client.force_login(self.coordinador)
        resp_panel = self.client.get(reverse('panel_coordinador'))
        self.assertContains(resp_panel, '$450.000 CLP')
        self.assertNotContains(resp_panel, '$450 000,00')

    # =========================================================================
    # TEST 11: LABORATORIOS, COMPUTADORES Y CREACIÓN DE CURSOS POR COORDINADOR
    # =========================================================================
    def test_laboratorios_y_creacion_curso_coordinador(self):
        # ¿Por qué verificamos estos campos en el modelo Curso?:
        # Aquí utilicé estas aserciones para validar que el modelo Curso persista correctamente
        # el laboratorio asignado y la cantidad de computadores para coherencia física de salas.
        self.assertEqual(self.curso_django.laboratorio, 'Laboratorio TI-1')
        self.assertEqual(self.curso_django.cantidad_computadores, 20)

        # ¿Por qué probamos la visibilidad del botón según rol?:
        # Aquí utilicé assertContains y assertNotContains para comprobar el principio de menor privilegio (RBAC).
        # Este código sirve para comprobar que visitantes anónimos y estudiantes no puedan ver los controles
        # ni el modal de apertura de cursos, reservándolo exclusivamente para el rol COORDINADOR.
        resp_cat_anon = self.client.get(reverse('catalogo'))
        self.assertContains(resp_cat_anon, 'bi-pc-display')
        self.assertContains(resp_cat_anon, 'Laboratorio TI-1 · Aforo: 20 alumnos')
        self.assertContains(resp_cat_anon, 'Estaciones ocupadas:')
        self.assertNotContains(resp_cat_anon, '+ Abrir Nuevo Bootcamp / Curso')

        # Estudiante no ve botón de nuevo curso
        self.client.force_login(self.estudiante)
        resp_cat_est = self.client.get(reverse('catalogo'))
        self.assertNotContains(resp_cat_est, '+ Abrir Nuevo Bootcamp / Curso')

        # Coordinador sí ve botón de nuevo curso y modal de creación
        self.client.force_login(self.coordinador)
        resp_cat_coord = self.client.get(reverse('catalogo'))
        self.assertContains(resp_cat_coord, '+ Abrir Nuevo Bootcamp / Curso')
        self.assertContains(resp_cat_coord, 'modalNuevoCurso')

        # ¿Por qué probamos la creación de curso vía POST con parámetros completos?:
        # Aquí utilicé este posteo para validar el ciclo de publicación: creación del registro,
        # asignación automática de cupos disponibles y emisión del mensaje flash de confirmación.
        post_data = {
            'titulo': 'Bootcamp Ciberseguridad Defensiva',
            'area': self.area_web.id,
            'laboratorio': 'Laboratorio SOC-1',
            'cantidad_computadores': 25,
            'cupos_maximos': 15,
            'costo_matricula': '360000',
            'fecha_inicio': '2026-11-01',
            'fecha_termino': '2026-12-30',
            'descripcion': 'Hacking ético, SOC y defensa contra amenazas avanzadas.',
        }
        resp_create = self.client.post(reverse('crear_curso_coordinador'), data=post_data, follow=True)
        self.assertEqual(resp_create.status_code, 200)

        # ¿Por qué validar cupos_disponibles == cupos_maximos y matriculas_actuales == 0?:
        # Este código sirve para verificar que al aperturar una oferta académica, el 100% de las vacantes
        # quede disponible de inmediato y el cálculo dinámico de alumnos matriculados inicie en cero.
        nuevo = Curso.objects.get(titulo='Bootcamp Ciberseguridad Defensiva')
        self.assertEqual(nuevo.cupos_disponibles, 15)
        self.assertEqual(nuevo.cupos_maximos, 15)
        self.assertEqual(nuevo.laboratorio, 'Laboratorio SOC-1')
        self.assertEqual(nuevo.cantidad_computadores, 25)
        self.assertEqual(nuevo.matriculas_actuales, 0)
        self.assertContains(resp_create, 'Bootcamp Ciberseguridad Defensiva')
        from django.contrib.messages import get_messages
        msg_list = [m.message for m in get_messages(resp_create.wsgi_request)]
        self.assertTrue(any("Curso 'Bootcamp Ciberseguridad Defensiva' publicado con éxito en el catálogo." in m for m in msg_list))

        # ¿Por qué invocamos curso_invalido.full_clean() con assertRaises?:
        # Aquí utilicé self.assertRaises(ValidationError) porque Django ORM no ejecuta clean() automáticamente al llamar save().
        # Este código sirve para certificar que la validación en Curso.clean() impida que los cupos ofrecidos superen
        # la capacidad física de los computadores del laboratorio asignado.
        from django.core.exceptions import ValidationError
        curso_invalido = Curso(
            area=self.area_web,
            titulo='Curso Exceso Cupos',
            descripcion='Test de coherencia física',
            costo_matricula=Decimal('100000'),
            fecha_inicio=date(2026, 5, 1),
            fecha_termino=date(2026, 6, 1),
            cupos_maximos=30,
            cupos_disponibles=30,
            laboratorio='Lab 1',
            cantidad_computadores=20,
        )
        with self.assertRaises(ValidationError) as ctx:
            curso_invalido.full_clean()
        self.assertIn('cupos_maximos', ctx.exception.message_dict)
        self.assertIn("Los cupos ofrecidos (30) no pueden superar la capacidad física del laboratorio (20 PCs).", ctx.exception.message_dict['cupos_maximos'][0])

    # =========================================================================
    # TEST 12: REGISTRO PÚBLICO DE NUEVOS ESTUDIANTES Y CREACIÓN DE CARRO
    # =========================================================================
    def test_registro_estudiante_flow(self):
        # ¿Por qué verificamos el login y las credenciales de prueba?:
        # Aquí utilicé assertContains para garantizar que la pantalla de autenticación incluya el enlace
        # al registro de estudiantes sin romper el bloque de credenciales sembradas para evaluación.
        resp_login = self.client.get(reverse('login'))
        self.assertEqual(resp_login.status_code, 200)
        self.assertContains(resp_login, 'Registrarse como Nuevo Estudiante')
        self.assertContains(resp_login, 'Credenciales de Prueba')
        self.assertContains(resp_login, 'estudiante_1')
        self.assertContains(resp_login, 'coordinador_admin')

        # ¿Por qué probamos el GET de registro?:
        # Verifica que la plantilla renderice los campos requeridos y el enlace de retorno al login.
        resp_reg = self.client.get(reverse('registro_estudiante'))
        self.assertEqual(resp_reg.status_code, 200)
        self.assertContains(resp_reg, 'Registro de Estudiante')
        self.assertContains(resp_reg, 'Iniciar Sesión')

        # ¿Por qué probamos el registro vía POST con contraseña y confirmación?:
        # Aquí utilicé esta prueba para simular el registro completo de un nuevo alumno,
        # validando que redirija con éxito hacia el login y entregue retroalimentación positiva.
        post_data = {
            'username': 'nuevo_estudiante_2026',
            'nombre_completo': 'Camila Soto',
            'email': 'camila@edtech.cl',
            'password': 'Password2026!',
            'confirm_password': 'Password2026!',
        }
        resp_post = self.client.post(reverse('registro_estudiante'), data=post_data, follow=True)
        self.assertEqual(resp_post.status_code, 200)
        self.assertRedirects(resp_post, reverse('login'))
        self.assertContains(resp_post, 'Cuenta de estudiante creada con éxito')

        # ¿Por qué validamos el rol ESTUDIANTE y el cifrado de contraseña con check_password()?:
        # 1. Asegura que el usuario no pueda elevar privilegios a COORDINADOR (prevención de Mass Assignment).
        # 2. check_password() comprueba que la contraseña fue hasheada criptográficamente con PBKDF2/SHA-256
        #    en lugar de haberse almacenado en texto plano en la base de datos.
        nuevo_user = User.objects.get(username='nuevo_estudiante_2026')
        self.assertEqual(nuevo_user.rol, User.ROLE_ESTUDIANTE)
        self.assertEqual(nuevo_user.first_name, 'Camila')
        self.assertEqual(nuevo_user.last_name, 'Soto')
        self.assertTrue(nuevo_user.check_password('Password2026!'))
        self.assertFalse(nuevo_user.is_staff)

        # ¿Por qué verificamos que se cree CarroMatricula automáticamente?:
        # Cada estudiante nuevo debe tener inmediatamente su carro individual OneToOneField listo,
        # evitando excepciones 404 o inconsistencias cuando el usuario comience a agregar cursos.
        self.assertTrue(CarroMatricula.objects.filter(estudiante=nuevo_user).exists())

    # =========================================================================
    # TEST 13: GESTIÓN CRUD DE CURSOS, EDICIÓN IN-SITU Y BORRADO SEGURO
    # =========================================================================
    def test_crud_cursos_coordinador(self):
        # ¿Por qué verificamos visibilidad de botones y modales por rol?:
        # Aquí utilicé assertNotContains para anónimos/estudiantes y assertContains para el coordinador.
        # Este código sirve para comprobar que las herramientas de edición y eliminación estén estrictamente
        # aisladas en la interfaz según el rol del usuario autenticado.
        resp_anon = self.client.get(reverse('catalogo'))
        self.assertNotContains(resp_anon, f'modalEditarCurso{self.curso_django.id}')
        self.assertNotContains(resp_anon, f'btn-editar-curso-{self.curso_django.id}')
        self.assertNotContains(resp_anon, f'btn-eliminar-curso-{self.curso_django.id}')

        self.client.force_login(self.estudiante)
        resp_est = self.client.get(reverse('catalogo'))
        self.assertNotContains(resp_est, f'modalEditarCurso{self.curso_django.id}')
        self.assertNotContains(resp_est, f'btn-editar-curso-{self.curso_django.id}')
        self.assertNotContains(resp_est, f'btn-eliminar-curso-{self.curso_django.id}')

        self.client.force_login(self.coordinador)
        resp_coord = self.client.get(reverse('catalogo'))
        self.assertContains(resp_coord, f'modalEditarCurso{self.curso_django.id}')
        self.assertContains(resp_coord, f'btn-editar-curso-{self.curso_django.id}')
        self.assertContains(resp_coord, f'btn-eliminar-curso-{self.curso_django.id}')

        # ¿Por qué probamos edición con colisión de laboratorio en fechas cruzadas?:
        # Creamos un curso secundario ('curso_conflicto') que usa el mismo laboratorio en el mismo rango de fechas.
        # Este código sirve para validar que el algoritmo de conflicto en la vista detecte la intersección
        # de intervalos temporales y emita un mensaje de advertencia de infraestructura.
        curso_conflicto = Curso.objects.create(
            area=self.area_web,
            titulo='Bootcamp Python Avanzado',
            descripcion='Programación avanzada',
            costo_matricula=Decimal('300000.00'),
            fecha_inicio=date(2026, 3, 1),
            fecha_termino=date(2026, 4, 30),
            cupos_maximos=20,
            cupos_disponibles=20,
            laboratorio='Lab Innovación 5',
            cantidad_computadores=20,
        )

        edit_data = {
            'titulo': 'Bootcamp Django Web Pro - Edición Especial',
            'area': self.area_web.id,
            'costo_matricula': '480000',
            'cupos_maximos': '18',
            'laboratorio': 'Lab Innovación 5',  # Mismo laboratorio que curso_conflicto en fechas cruzadas
            'cantidad_computadores': '20',
            'fecha_inicio': '2026-03-10',
            'fecha_termino': '2026-04-10',
            'descripcion': 'Descripción actualizada del bootcamp Django.',
        }
        edit_url = reverse('editar_curso_coordinador', kwargs={'curso_id': self.curso_django.id})
        resp_edit = self.client.post(edit_url, data=edit_data, follow=True)
        self.assertEqual(resp_edit.status_code, 200)

        # ¿Por qué verificamos el mensaje flash de advertencia?:
        # Confirma que el coordinador fue informado del conflicto de infraestructura sin bloquear
        # la actualización autorizada por el personal directivo.
        from django.contrib.messages import get_messages
        msg_list = [m.message for m in get_messages(resp_edit.wsgi_request)]
        self.assertTrue(any("Advertencia de Infraestructura: El Lab Innovación 5 ya está asignado al programa 'Bootcamp Python Avanzado'" in m for m in msg_list))
        self.assertTrue(any("actualizado exitosamente" in m for m in msg_list))

        self.curso_django.refresh_from_db()
        self.assertEqual(self.curso_django.titulo, 'Bootcamp Django Web Pro - Edición Especial')
        self.assertEqual(self.curso_django.cupos_maximos, 18)
        self.assertEqual(self.curso_django.laboratorio, 'Lab Innovación 5')

        # =========================================================================
        # PATRÓN DE BORRADO LÓGICO (SOFT DELETE) Y REACTIVACIÓN DE PROGRAMAS
        # =========================================================================
        # ¿Por qué borrado lógico (Soft Delete)?:
        # Garantiza la integridad referencial y trazabilidad histórica en PostgreSQL sin destruir
        # registros académicos. Al archivar, activo pasa a False y se registra fecha_desactivacion.
        # El programa desaparece del catálogo público para estudiantes pero permanece en la base de datos
        # y puede ser reactivado en cualquier momento por el coordinador desde su panel.

        # 1. Limpieza de carritos pendientes al archivar
        carro, _ = CarroMatricula.objects.get_or_create(estudiante=self.estudiante)
        ItemCarro.objects.create(carro=carro, curso=curso_conflicto)
        self.assertTrue(ItemCarro.objects.filter(curso=curso_conflicto).exists())

        # 2. El coordinador archiva el curso (Soft Delete)
        del_conflicto_url = reverse('eliminar_curso_coordinador', kwargs={'curso_id': curso_conflicto.id})
        resp_del_ok = self.client.post(del_conflicto_url, follow=True)
        self.assertEqual(resp_del_ok.status_code, 200)
        self.assertRedirects(resp_del_ok, reverse('panel_coordinador'))

        # Verificar que el curso NO se eliminó de PostgreSQL (Soft Delete)
        self.assertTrue(Curso.objects.filter(id=curso_conflicto.id).exists())
        curso_conflicto.refresh_from_db()
        self.assertFalse(curso_conflicto.activo)
        self.assertIsNotNone(curso_conflicto.fecha_desactivacion)
        # Verificar que se purgaron los ítems en carros pendientes
        self.assertFalse(ItemCarro.objects.filter(curso=curso_conflicto).exists())

        msg_list_ok = [m.message for m in get_messages(resp_del_ok.wsgi_request)]
        self.assertTrue(any("archivado y retirado del catálogo público" in m for m in msg_list_ok))

        # 3. Verificar que el curso archivado desaparezca del catálogo del estudiante
        self.client.force_login(self.estudiante)
        resp_cat_est = self.client.get(reverse('catalogo'))
        self.assertNotContains(resp_cat_est, curso_conflicto.titulo)

        # 4. Verificar advertencia visual preventiva en el modal de archivado del panel del coordinador
        self.client.force_login(self.coordinador)
        resp_panel_coord = self.client.get(reverse('panel_coordinador'))
        self.assertContains(resp_panel_coord, "Si este curso cuenta con estudiantes matriculados, se mantendrán sus comprobantes históricos intactos y solo se suspenderá la admisión a nuevos postulantes.")

        # 5. Verificar feedback visual en comprobante del estudiante cuando el curso matriculado fue archivado
        matr_archivada = Matricula.objects.create(
            estudiante=self.estudiante,
            estado=Matricula.ESTADO_PAGADO,
            total=Decimal('300000.00')
        )
        DetalleMatricula.objects.create(
            matricula=matr_archivada,
            curso=curso_conflicto,
            precio_historico=Decimal('300000.00')
        )
        self.client.force_login(self.estudiante)
        resp_mis_matr = self.client.get(reverse('mis_matriculas'))
        self.assertContains(resp_mis_matr, "Convocatoria Cerrada en Catálogo")
        self.assertContains(resp_mis_matr, "Aviso Académico:</strong> La oferta pública de este programa se encuentra cerrada en el catálogo general.")

        # 6. El coordinador reactiva el curso archivado
        self.client.force_login(self.coordinador)
        reactivar_url = reverse('reactivar_curso', kwargs={'curso_id': curso_conflicto.id})
        resp_reactivar = self.client.post(reactivar_url, follow=True)
        self.assertEqual(resp_reactivar.status_code, 200)
        self.assertRedirects(resp_reactivar, reverse('panel_coordinador'))

        # Verificar que el curso vuelve a estar activo y sin fecha_desactivacion
        curso_conflicto.refresh_from_db()
        self.assertTrue(curso_conflicto.activo)
        self.assertIsNone(curso_conflicto.fecha_desactivacion)

        # Verificar que vuelve a aparecer en el catálogo público
        resp_cat_reactivado = self.client.get(reverse('catalogo'))
        self.assertContains(resp_cat_reactivado, curso_conflicto.titulo)

    # =========================================================================
    # TEST 14: CICLO DE VIDA Y ANULACIÓN DE MATRÍCULA POR EL ESTUDIANTE (RETRACTO)
    # =========================================================================
    # ¿Por qué este test?:
    # Verifica de punta a punta el derecho a retracto: cambio a ANULADA, auditoría (fecha, motivo,
    # anulado_por), restitución atómica de cupo y bloqueo cuando el curso ya inició.
    def test_anulacion_matricula_estudiante_y_restitucion_cupos(self):
        """
        Valida que el estudiante pueda anular su matrícula ejerciendo derecho de retracto
        antes del inicio de clases, reponiendo de forma atómica y segura el cupo al curso
        y registrando la auditoría completa (fecha, motivo y anulado_por).
        Asimismo, comprueba que si el curso ya inició, se deniegue el retracto.
        """
        # Preparar curso y matrícula en estado PAGADO con 1 cupo ocupado
        self.curso_django.cupos_disponibles = 1
        self.curso_django.save()

        matricula = Matricula.objects.create(
            estudiante=self.estudiante,
            estado=Matricula.ESTADO_PAGADO,
            total=Decimal('450000.00')
        )
        DetalleMatricula.objects.create(
            matricula=matricula,
            curso=self.curso_django,
            precio_historico=Decimal('450000.00')
        )

        # Autenticar estudiante
        self.client.login(username='estudiante_1', password='Est2026!')
        anular_url = reverse('anular_matricula_estudiante', kwargs={'matricula_id': matricula.id})
        resp = self.client.post(anular_url, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Verificar actualización del modelo y auditoría
        matricula.refresh_from_db()
        self.assertEqual(matricula.estado, 'ANULADA')
        self.assertEqual(matricula.motivo_anulacion, "Retracto voluntario ejercido por el estudiante")
        self.assertEqual(matricula.anulado_por, self.estudiante)
        self.assertIsNotNone(matricula.fecha_anulacion)

        # Verificar restitución atómica de cupo sin exceder cupos_maximos (2)
        self.curso_django.refresh_from_db()
        self.assertEqual(self.curso_django.cupos_disponibles, 2)

        # Probar denegación de retracto cuando el curso ya inició
        curso_pasado = Curso.objects.create(
            area=self.area_web,
            titulo='Curso Antiguo Iniciado',
            descripcion='Curso con fecha de inicio en el pasado',
            costo_matricula=Decimal('200000.00'),
            fecha_inicio=date(2025, 1, 1),
            fecha_termino=date(2025, 3, 1),
            cupos_maximos=5,
            cupos_disponibles=4,
            activo=True
        )
        matr_iniciada = Matricula.objects.create(
            estudiante=self.estudiante,
            estado=Matricula.ESTADO_PAGADO,
            total=Decimal('200000.00')
        )
        DetalleMatricula.objects.create(
            matricula=matr_iniciada,
            curso=curso_pasado,
            precio_historico=Decimal('200000.00')
        )

        resp_pasado = self.client.post(
            reverse('anular_matricula_estudiante', kwargs={'matricula_id': matr_iniciada.id}),
            follow=True
        )
        self.assertEqual(resp_pasado.status_code, 200)
        matr_iniciada.refresh_from_db()
        self.assertEqual(matr_iniciada.estado, 'PAGADO')  # No debe anularse
        curso_pasado.refresh_from_db()
        self.assertEqual(curso_pasado.cupos_disponibles, 4)  # Cupos no cambian

    # =========================================================================
    # TEST 15: ANULACIÓN ADMINISTRATIVA POR EL COORDINADOR CON MOTIVO
    # =========================================================================
    # ¿Por qué este test?:
    # Garantiza que la anulación administrativa exija rol directivo, motivo obligatorio,
    # restituya atómicamente los cupos sin sobrecupo y audite al coordinador responsable.
    def test_anulacion_administrativa_coordinador_con_motivo(self):
        """
        Valida que el coordinador pueda anular administrativamente una matrícula ingresando
        obligatoriamente el motivo, restituyendo de forma atómica los cupos del curso y
        registrando fecha, motivo y anulado_por = coordinador.
        """
        self.curso_django.cupos_disponibles = 1
        self.curso_django.save()

        matricula = Matricula.objects.create(
            estudiante=self.estudiante,
            estado=Matricula.ESTADO_PAGADO,
            total=Decimal('450000.00')
        )
        DetalleMatricula.objects.create(
            matricula=matricula,
            curso=self.curso_django,
            precio_historico=Decimal('450000.00')
        )

        anular_coord_url = reverse('anular_matricula_coordinador', kwargs={'matricula_id': matricula.id})

        # 1. Acceso no autorizado (estudiante) debe ser bloqueado
        self.client.login(username='estudiante_1', password='Est2026!')
        resp_bloqueado = self.client.post(anular_coord_url, {'motivo': 'Intento no autorizado'}, follow=True)
        matricula.refresh_from_db()
        self.assertEqual(matricula.estado, 'PAGADO')

        # 2. Coordinador sin motivo obligatorio debe recibir error
        self.client.login(username='coordinador_admin', password='Coord2026!')
        resp_sin_motivo = self.client.post(anular_coord_url, {'motivo': '   '}, follow=True)
        matricula.refresh_from_db()
        self.assertEqual(matricula.estado, 'PAGADO')

        # 3. Coordinador con motivo válido anula correctamente
        motivo_admin = "Anulación administrativa por duplicidad de orden formal y solicitud del alumno"
        resp_coord = self.client.post(anular_coord_url, {'motivo': motivo_admin}, follow=True)
        self.assertEqual(resp_coord.status_code, 200)

        matricula.refresh_from_db()
        self.assertEqual(matricula.estado, 'ANULADA')
        self.assertEqual(matricula.motivo_anulacion, motivo_admin)
        self.assertEqual(matricula.anulado_por, self.coordinador)
        self.assertIsNotNone(matricula.fecha_anulacion)

        # Verificar reposición atómica de cupos
        self.curso_django.refresh_from_db()
        self.assertEqual(self.curso_django.cupos_disponibles, 2)

    # =========================================================================
    # TEST 16: VISTA MIS MATRÍCULAS EXCLUYE ANULADAS DE INVERSIÓN TOTAL
    # =========================================================================
    # ¿Por qué este test?:
    # Comprueba la consistencia contable y visual: las matrículas anuladas no suman a la inversión total
    # del estudiante y muestran claramente la fecha y el motivo institucional de la resolución.
    def test_mis_matriculas_excluye_anuladas_de_inversion_total(self):
        """
        Valida que en la vista 'mis_matriculas', las matrículas con estado 'ANULADA'
        se excluyan del total invertido, se muestre la insignia correspondiente
        y se renderice el recuadro de aviso institucional con fecha y motivo.
        """
        from django.utils import timezone
        fecha_anul = timezone.now()

        matr_activa = Matricula.objects.create(
            estudiante=self.estudiante,
            estado=Matricula.ESTADO_PAGADO,
            total=Decimal('450000.00')
        )
        DetalleMatricula.objects.create(
            matricula=matr_activa,
            curso=self.curso_django,
            precio_historico=Decimal('450000.00')
        )

        matr_anulada = Matricula.objects.create(
            estudiante=self.estudiante,
            estado=Matricula.ESTADO_ANULADA,
            total=Decimal('300000.00'),
            fecha_anulacion=fecha_anul,
            motivo_anulacion='Retracto voluntario formal',
            anulado_por=self.estudiante
        )
        DetalleMatricula.objects.create(
            matricula=matr_anulada,
            curso=self.curso_django,
            precio_historico=Decimal('300000.00')
        )

        self.client.login(username='estudiante_1', password='Est2026!')
        resp = self.client.get(reverse('mis_matriculas'))
        self.assertEqual(resp.status_code, 200)

        # Inversión total debe ser solo los $450.000 de la matrícula PAGADA (excluyendo los $300.000 anulados)
        self.assertEqual(resp.context['total_invertido'], Decimal('450000.00'))

        # Validar contenido visual institucional
        content = resp.content.decode('utf-8')
        self.assertIn('ANULADA', content)
        self.assertIn('Matrícula Anulada el', content)
        self.assertIn('Retracto voluntario formal', content)

    # =========================================================================
    # TEST 17: ALTA SEGURA DE COORDINADORES BAJO ARQUITECTURA RBAC
    # =========================================================================
    # ¿Por qué este test?:
    # Valida el aprovisionamiento seguro de directivos garantizando:
    # 1. Que un estudiante NO pueda enviar peticiones a esta vista (HTTP 403 o redirección 302).
    # 2. Que un coordinador sí pueda registrar exitosamente a otro directivo con rol 'COORDINADOR',
    #    contraseña encriptada mediante PBKDF2/SHA-256 (set_password) y persistencia íntegra.
    # 3. Que el panel del coordinador renderice el botón institucional y modal correspondiente.
    def test_alta_coordinador_rbac(self):
        """
        Prueba de seguridad RBAC para la creación exclusiva de nuevos Coordinadores:
        - Acceso restringido para estudiantes (redirección / 403).
        - Alta exitosa por parte de un usuario Coordinador.
        - Validación de hashing seguro de contraseñas y asignación del rol 'COORDINADOR'.
        """
        # 1. Comprobar que en el panel del coordinador se renderiza el botón del modal
        self.client.force_login(self.coordinador)
        resp_panel = self.client.get(reverse('panel_coordinador'))
        self.assertEqual(resp_panel.status_code, 200)
        self.assertContains(resp_panel, 'Registrar Nuevo Coordinador')
        self.assertContains(resp_panel, 'modalCrearCoordinador')

        post_data = {
            'username': 'nuevo_coordinador_2026',
            'first_name': 'Claudia',
            'last_name': 'González',
            'nombre_completo': 'Claudia González',
            'email': 'claudia.coord@edtech.cl',
            'password': 'CoordPassword2026!',
            'confirm_password': 'CoordPassword2026!',
        }

        # 2. Un estudiante autenticado intenta registrar un nuevo coordinador -> Rechazado (HTTP 403 o redirección 302)
        self.client.force_login(self.estudiante)
        resp_estudiante = self.client.post(reverse('crear_coordinador'), data=post_data)
        self.assertIn(resp_estudiante.status_code, [302, 403])
        # Aseguramos que NO se haya creado el usuario
        self.assertFalse(User.objects.filter(username='nuevo_coordinador_2026').exists())

        # 3. Un usuario anónimo (sin sesión) intenta registrar un coordinador -> Redirigido (login)
        self.client.logout()
        resp_anon = self.client.post(reverse('crear_coordinador'), data=post_data)
        self.assertIn(resp_anon.status_code, [302, 403])
        self.assertFalse(User.objects.filter(username='nuevo_coordinador_2026').exists())

        # 4. Un coordinador autenticado registra exitosamente al nuevo directivo
        self.client.force_login(self.coordinador)
        resp_coord = self.client.post(reverse('crear_coordinador'), data=post_data, follow=True)
        self.assertEqual(resp_coord.status_code, 200)
        self.assertRedirects(resp_coord, reverse('panel_coordinador'))
        self.assertContains(resp_coord, 'dado de alta exitosamente')

        # 5. Validar existencia, rol COORDINADOR y contraseña encriptada
        nuevo_coord = User.objects.get(username='nuevo_coordinador_2026')
        self.assertEqual(nuevo_coord.rol, User.ROLE_COORDINADOR)
        self.assertEqual(nuevo_coord.role, 'COORDINADOR')
        self.assertTrue(nuevo_coord.is_coordinador)
        self.assertTrue(nuevo_coord.check_password('CoordPassword2026!'))
        self.assertEqual(nuevo_coord.email, 'claudia.coord@edtech.cl')
        self.assertEqual(nuevo_coord.first_name, 'Claudia')
        self.assertEqual(nuevo_coord.last_name, 'González')

        # 6. Validar que no se permita registrar con contraseñas que no coincidan
        post_data_invalida = post_data.copy()
        post_data_invalida['username'] = 'otro_coord_invalido'
        post_data_invalida['password'] = 'Pass1234!'
        post_data_invalida['confirm_password'] = 'NoCoincide!'
        resp_mismatch = self.client.post(reverse('crear_coordinador'), data=post_data_invalida, follow=True)
        self.assertContains(resp_mismatch, 'Las contraseñas no coinciden')
        self.assertFalse(User.objects.filter(username='otro_coord_invalido').exists())





