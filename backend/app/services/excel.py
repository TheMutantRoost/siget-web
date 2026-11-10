"""Utilidades de Excel seguras frente a inyección de fórmulas."""
from typing import Any

PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def celda_segura(valor: Any) -> Any:
    """Antepone un apóstrofo a textos que Excel interpretaría como fórmula."""
    if isinstance(valor, str) and valor.startswith(PELIGROSOS):
        return "'" + valor
    return valor
