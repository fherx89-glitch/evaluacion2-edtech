"""
Filtros de Formato de Moneda Chilena (CLP)
Caso 2: Plataforma de Reservas de Cursos y Bootcamps (EdTech)
Alumno: Fernando Pailahueque | Sección: AP-N4-C2 | Año: 2026
"""

from django import template

register = template.Library()


# ¿Por qué este filtro personalizado y no los filtros estándar de Django (floatformat / intcomma)?:
# Aquí utilicé este filtro 'formato_clp' porque el peso chileno (CLP) no utiliza centavos en el
# comercio institucional habitual y exige el signo '$' prefijado junto con puntos '.' como separador de miles.
# Los filtros nativos de Django como intcomma aplican comas anglosajonas (ej: 450,000) o decimales con coma
# (floatformat), lo que generaba incoherencias monetarias con la pauta de evaluación.
@register.filter(name='formato_clp')
def formato_clp(valor):
    """
    Formatea un valor monetario al estándar chileno (CLP):
    Sin decimales y con puntos como separador de miles.
    Ejemplo: 450000 -> "$450.000"
    """
    if valor is None:
        return "$0"
    try:
        entero = int(round(float(valor)))
        formateado = f"{entero:,}".replace(",", ".")
        return f"${formateado}"
    except (ValueError, TypeError):
        return valor
