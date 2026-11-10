"""AsistenciaCalculator: único cálculo de porcentaje, riesgo y aptitud.

Porcentaje = (P + J) ÷ sesiones realizadas que le corresponden al estudiante × 100.
Le corresponde una sesión si su fecha cae en un periodo activo de la inscripción:
desde el día de alta (incluido) hasta el día de retiro (excluido). Propuesta P4 aprobada.
Las comparaciones usan aritmética entera para que el redondeo nunca cambie un resultado.
"""
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.models import EstadoAsistencia, TipoMovimiento

ABREN = {TipoMovimiento.ALTA, TipoMovimiento.REACTIVACION, TipoMovimiento.CAMBIO_ENTRADA}
CIERRAN = {TipoMovimiento.RETIRO, TipoMovimiento.CAMBIO_SALIDA}
VALIDOS = {EstadoAsistencia.PRESENTE, EstadoAsistencia.JUSTIFICADO}


@dataclass(frozen=True)
class Periodo:
    desde: date
    hasta: date | None  # excluido; None = sigue activo

    def contiene(self, fecha: date) -> bool:
        return self.desde <= fecha and (self.hasta is None or fecha < self.hasta)


@dataclass(frozen=True)
class ResultadoAsistencia:
    sesiones_correspondientes: int
    validas: int
    faltas: int
    porcentaje: Decimal
    calculable: bool
    en_riesgo: bool | None
    apto: bool | None


def periodos_desde_movimientos(movimientos: Iterable[tuple[TipoMovimiento, date]]) -> list[Periodo]:
    periodos: list[Periodo] = []
    abierto: date | None = None
    for tipo, fecha in movimientos:  # en orden cronológico
        if tipo in ABREN and abierto is None:
            abierto = fecha
        elif tipo in CIERRAN and abierto is not None:
            if fecha > abierto:
                periodos.append(Periodo(abierto, fecha))
            abierto = None
    if abierto is not None:
        periodos.append(Periodo(abierto, None))
    return periodos


def calcular(
    *,
    sesiones_realizadas: Sequence[tuple[int, date]],
    periodos: Sequence[Periodo],
    asistencias: Mapping[int, EstadoAsistencia],
    umbral_aptitud: int,
    umbral_riesgo_pct: int,
) -> ResultadoAsistencia:
    correspondientes = [sid for sid, fecha in sesiones_realizadas if any(p.contiene(fecha) for p in periodos)]
    total = len(correspondientes)
    validas = sum(1 for sid in correspondientes if asistencias.get(sid) in VALIDOS)
    if total == 0:
        return ResultadoAsistencia(0, 0, 0, Decimal("0.00"), False, None, None)
    porcentaje = (Decimal(validas * 100) / Decimal(total)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    # Riesgo: faltas ≥ umbral_riesgo % ⇔ porcentaje ≤ 100 − umbral_riesgo.
    en_riesgo = validas * 100 <= (100 - umbral_riesgo_pct) * total
    apto = validas * 100 >= umbral_aptitud * total
    return ResultadoAsistencia(total, validas, total - validas, porcentaje, True, en_riesgo, apto)
