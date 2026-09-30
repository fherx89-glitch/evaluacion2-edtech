"""
Comando de Gestión para poblar la base de datos EdTech con datos iniciales de prueba
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from academico.models import AreaConocimiento, Curso, CarroMatricula

User = get_user_model()


class Command(BaseCommand):
    help = 'Puebla la base de datos con usuarios de prueba, 2 áreas de conocimiento y 4 cursos (uno con 2 cupos para demostrar quiebre de stock).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Iniciando Poblado de Datos - Plataforma EdTech ==="))
        self.stdout.write(self.style.WARNING("Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026\n"))

        # 1. Crear Coordinador
        coord_user, created_coord = User.objects.get_or_create(
            username='coordinador_admin',
            defaults={
                'email': 'coordinador@edtech.cl',
                'first_name': 'Coordinador',
                'last_name': 'Académico',
                'rol': User.ROLE_COORDINADOR,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        coord_user.set_password('Coord2026!')
        coord_user.rol = User.ROLE_COORDINADOR
        coord_user.is_staff = True
        coord_user.is_superuser = True
        coord_user.save()
        CarroMatricula.objects.get_or_create(estudiante=coord_user)

        if created_coord:
            self.stdout.write(self.style.SUCCESS('[OK] Coordinador creado: coordinador_admin (Coord2026!)'))
        else:
            self.stdout.write(self.style.SUCCESS('[OK] Coordinador actualizado: coordinador_admin (Coord2026!)'))

        # 2. Crear Estudiante
        est_user, created_est = User.objects.get_or_create(
            username='estudiante_1',
            defaults={
                'email': 'estudiante1@edtech.cl',
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'rol': User.ROLE_ESTUDIANTE,
            }
        )
        est_user.set_password('Est2026!')
        est_user.rol = User.ROLE_ESTUDIANTE
        est_user.save()
        CarroMatricula.objects.get_or_create(estudiante=est_user)

        if created_est:
            self.stdout.write(self.style.SUCCESS('[OK] Estudiante creado: estudiante_1 (Est2026!)'))
        else:
            self.stdout.write(self.style.SUCCESS('[OK] Estudiante actualizado: estudiante_1 (Est2026!)'))

        # 3. Crear exactamente 2 Áreas de Conocimiento
        areas_data = [
            {
                'nombre': 'Desarrollo Web',
                'descripcion': 'Programas avanzados de ingeniería web, backend con Django, microservicios y frontend reactivo.'
            },
            {
                'nombre': 'Ciencia de Datos',
                'descripcion': 'Programas intensivos de análisis cuantitativo, machine learning, deep learning e inteligencia artificial.'
            },
        ]

        areas_creadas = {}
        for area_info in areas_data:
            area_obj, _ = AreaConocimiento.objects.get_or_create(
                nombre=area_info['nombre'],
                defaults={'descripcion': area_info['descripcion']}
            )
            areas_creadas[area_obj.nombre] = area_obj
            self.stdout.write(self.style.SUCCESS(f'[OK] Área creada/verificada: {area_obj.nombre}'))

        # 4. Crear exactamente 4 Cursos con laboratorios y capacidades de computadores diferenciadas
        cursos_data = [
            {
                'titulo': 'Bootcamp Full Stack Django',
                'area': areas_creadas['Desarrollo Web'],
                'descripcion': 'Domina Django, Django REST Framework, arquitectura de microservicios, autenticación JWT y despliegue profesional en producción.',
                'costo_matricula': Decimal('450000.00'),
                'fecha_inicio': date(2026, 10, 15),
                'fecha_termino': date(2026, 12, 20),
                'cupos_maximos': 2,
                'cupos_disponibles': 2,  # Curso con 2 cupos para demostrar quiebre de stock
                'laboratorio': 'Lab Desarrollo Web 101',
                'cantidad_computadores': 15,  # Sala pequeña (menos de 20 PCs)
            },
            {
                'titulo': 'Bootcamp Python & Machine Learning',
                'area': areas_creadas['Ciencia de Datos'],
                'descripcion': 'Aprende Python científico con Pandas, NumPy, Scikit-Learn y TensorFlow para crear modelos predictivos y soluciones basadas en IA.',
                'costo_matricula': Decimal('520000.00'),
                'fecha_inicio': date(2026, 11, 1),
                'fecha_termino': date(2027, 1, 30),
                'cupos_maximos': 10,
                'cupos_disponibles': 10,
                'laboratorio': 'Lab Inteligencia Artificial 204',
                'cantidad_computadores': 28,  # Sala grande (más de 20 PCs)
            },
            {
                'titulo': 'Taller de Arquitectura Backend y Microservicios',
                'area': areas_creadas['Desarrollo Web'],
                'descripcion': 'Patrones avanzados de diseño backend, integración de mensajería asíncrona, Dockerización y APIs escalables.',
                'costo_matricula': Decimal('290000.00'),
                'fecha_inicio': date(2026, 10, 25),
                'fecha_termino': date(2026, 11, 30),
                'cupos_maximos': 6,
                'cupos_disponibles': 6,
                'laboratorio': 'Sala Taller Microcomputación 105',
                'cantidad_computadores': 16,  # Taller especializado (menos de 20 PCs)
            },
            {
                'titulo': 'Bootcamp Data Engineering & Big Data',
                'area': areas_creadas['Ciencia de Datos'],
                'descripcion': 'Diseño e implementación de pipelines ETL/ELT robustos con Apache Spark, Kafka y data warehouses en la nube.',
                'costo_matricula': Decimal('490000.00'),
                'fecha_inicio': date(2026, 11, 10),
                'fecha_termino': date(2027, 1, 20),
                'cupos_maximos': 8,
                'cupos_disponibles': 8,
                'laboratorio': 'Lab Cómputo Avanzado & Cloud 301',
                'cantidad_computadores': 32,  # Sala de alto rendimiento (más de 20 PCs)
            }
        ]

        for c_data in cursos_data:
            curso_obj, created = Curso.objects.get_or_create(
                titulo=c_data['titulo'],
                defaults=c_data
            )
            if not created:
                curso_obj.area = c_data['area']
                curso_obj.descripcion = c_data['descripcion']
                curso_obj.cupos_maximos = c_data['cupos_maximos']
                curso_obj.cupos_disponibles = c_data['cupos_disponibles']
                curso_obj.costo_matricula = c_data['costo_matricula']
                curso_obj.laboratorio = c_data['laboratorio']
                curso_obj.cantidad_computadores = c_data['cantidad_computadores']
                curso_obj.save()

            self.stdout.write(self.style.SUCCESS(
                f'[OK] Curso listo: "{curso_obj.titulo}" | Lab: {curso_obj.laboratorio} ({curso_obj.cantidad_computadores} PCs) | Cupos: {curso_obj.cupos_disponibles}/{curso_obj.cupos_maximos} | Costo: ${curso_obj.costo_matricula:,.0f}'
            ))

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Poblado completado con éxito ==="))
        self.stdout.write(self.style.NOTICE("Credenciales disponibles:"))
        self.stdout.write(self.style.NOTICE("  - Coordinador: coordinador_admin / Coord2026!"))
        self.stdout.write(self.style.NOTICE("  - Estudiante:  estudiante_1 / Est2026!"))
