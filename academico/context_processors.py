"""
Context Processors para EdTech
Inyecta datos globales a todos los templates HTML, incluyendo datos del alumno y estado del carro.
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from .models import CarroMatricula

def global_academic_context(request):
    """
    Inyecta datos de autoría académica y métricas del carrito del estudiante.
    Retorna tanto las claves estándar requeridas como sus variantes para compatibilidad total.
    """
    total_items = 0
    total_monto = 0

    if request.user.is_authenticated:
        try:
            carro, _ = CarroMatricula.objects.get_or_create(estudiante=request.user)
            total_items = carro.items.count()
            total_monto = carro.total
        except Exception:
            total_items = 0
            total_monto = 0

    return {
        # Claves exactas requeridas por la pauta
        'alumno_nombre': 'Fernando Pailahueque',
        'alumno_seccion': 'AP-N4-C2',
        'alumno_anio': 2026,
        'carro_total_items': total_items,

        # Aliases adicionales para soporte en templates existentes
        'ALUMNO_NOMBRE': 'Fernando Pailahueque',
        'ALUMNO_SECCION': 'AP-N4-C2',
        'ALUMNO_ANIO': '2026',
        'cart_count': total_items,
        'cart_total': total_monto,
    }
