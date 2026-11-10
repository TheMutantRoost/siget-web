from datetime import date, time

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.errores import ConflictoError, ConflictoHorarioError, PermisoDenegadoError, ReglaNegocioError
from app.models import Ambiente, Auditoria, CicloAcademico, EstadoSesion, ExcepcionAreaDocente, Sesion
from app.services import asistencia_service, catalogo_service, taller_service
from app.services.contexto import Actor, Contexto
from app.services.disponibilidad_service import MOTIVO_CRUCE, MOTIVO_TRASLADO, Ocurrencia, motivo_conflicto
from app.services.taller_service import BloqueHorario

D = date(2026, 11, 16)


def oc(ini: str, fin: str, sede: int = 1, fecha: date = D) -> Ocurrencia:
    h = lambda s: time(*map(int, s.split(":")))  # noqa: E731
    return Ocurrencia(fecha, h(ini), h(fin), sede, f"S{sede}", 1, "T")


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        (oc("08:00", "10:00"), oc("09:00", "11:00"), MOTIVO_CRUCE),
        (oc("08:00", "10:00"), oc("10:00", "12:00"), None),  # límite exacto: no choca
        (oc("08:00", "10:00", fecha=D), oc("08:00", "10:00", fecha=date(2026, 11, 17)), None),
        (oc("08:00", "10:00", sede=1), oc("10:30", "12:00", sede=2), MOTIVO_TRASLADO),
        (oc("08:00", "10:00", sede=1), oc("11:00", "12:00", sede=2), None),  # 60 min justos
        (oc("08:00", "10:00", sede=1), oc("09:00", "11:00", sede=2), MOTIVO_CRUCE),
    ],
)
def test_condicion_de_solape(a, b, esperado):
    assert motivo_conflicto(a, b, 60) == esperado


def test_un_solo_ciclo_activo_garantizado_por_la_base(mundo, db):
    otro = catalogo_service.crear(mundo.ctx, CicloAcademico, {"nombre": "2027-I", "fecha_inicio": date(2027, 3, 1), "fecha_fin": date(2027, 7, 1)})
    catalogo_service.activar_ciclo(mundo.ctx, mundo.ciclo.id)
    catalogo_service.activar_ciclo(mundo.ctx, otro.id)
    db.flush()
    assert [c.nombre for c in db.scalars(select(CicloAcademico).where(CicloAcademico.activo.is_(True)))] == ["2027-I"]
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE ciclos_academicos SET activo = 1"))


def test_codigo_de_ambiente_unico_por_sede(mundo):
    catalogo_service.crear(mundo.ctx, Ambiente, {"sede_id": mundo.sede_b.id, "codigo": "A1", "nombre": "Mismo código, otra sede"})
    with pytest.raises(ConflictoError):
        catalogo_service.crear(mundo.ctx, Ambiente, {"sede_id": mundo.sede_a.id, "codigo": "A1", "nombre": "Duplicado"})


def test_ambiente_de_otra_sede_rechazado(mundo):
    with pytest.raises(ReglaNegocioError, match="otra sede"):
        mundo.taller("TX", sede=mundo.sede_a, ambiente=mundo.aula_b)


def test_la_base_rechaza_ambiente_de_otra_sede(mundo, db):
    t = mundo.taller("T1")
    db.flush()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE talleres SET ambiente_id = :a WHERE id = :t"), {"a": mundo.aula_b.id, "t": t.id})
        db.flush()


def test_umbral_fuera_de_rango_rechazado_por_la_base(mundo, db):
    t = mundo.taller("T1")
    db.flush()
    with pytest.raises((IntegrityError, OperationalError)):
        db.execute(text("UPDATE talleres SET umbral_aptitud = 40 WHERE id = :t"), {"t": t.id})


def test_varios_dias_y_bloques_generan_sesiones_numeradas(mundo, db):
    t = mundo.taller("T1", bloques=[
        BloqueHorario(1, time(8), time(10)), BloqueHorario(3, time(15), time(17)), BloqueHorario(3, time(18), time(19)),
    ], inicio=date(2026, 11, 9), fin=date(2026, 11, 22))
    sesiones = taller_service.listar_sesiones(mundo.ctx, t.id)
    assert [(s.numero_sesion, s.fecha.isoformat(), f"{s.hora_inicio:%H:%M}") for s in sesiones] == [
        (1, "2026-11-09", "08:00"), (2, "2026-11-11", "15:00"), (3, "2026-11-11", "18:00"),
        (4, "2026-11-16", "08:00"), (5, "2026-11-18", "15:00"), (6, "2026-11-18", "18:00"),
    ]


def test_regenerar_no_choca_con_numeros_conservados_ni_altera_historial(mundo, db):
    """Reproduce el defecto del escritorio: al regenerar numeraba desde 1 (uq_taller_sesion)."""
    t = mundo.taller("T1")  # lunes 08–10 desde el 2/11
    e = mundo.estudiante()
    from app.services import inscripcion_service
    insc = inscripcion_service.inscribir(mundo.ctx, t.id, e.id)
    primera = taller_service.listar_sesiones(mundo.ctx, t.id)[0]
    asistencia_service.guardar(mundo.ctx, primera.id, [asistencia_service.RegistroEntrada(insc.id, "P", None)])
    taller_service.fijar_horarios(mundo.ctx, t.id, [BloqueHorario(2, time(14), time(16))], "Cambio de horario")
    sesiones = taller_service.listar_sesiones(mundo.ctx, t.id)
    numeros = [s.numero_sesion for s in sesiones]
    assert len(numeros) == len(set(numeros))
    conservada = db.get(Sesion, primera.id)
    assert conservada.estado == EstadoSesion.REALIZADA and f"{conservada.hora_inicio:%H:%M}" == "08:00"
    futuras = [s for s in sesiones if s.fecha >= mundo.reloj.hoy()]
    assert all(s.fecha.isoweekday() == 2 for s in futuras)
    assert min(s.numero_sesion for s in futuras) > conservada.numero_sesion


def test_cruce_de_docente_rechazado(mundo):
    mundo.taller("T1", bloques=[BloqueHorario(1, time(8), time(10))])
    with pytest.raises(ConflictoHorarioError, match="Docente: cruce de horario"):
        mundo.taller("T2", bloques=[BloqueHorario(1, time(9), time(11))], ambiente=mundo.aula_a2)


def test_docente_con_traslado_insuficiente_entre_sedes(mundo):
    mundo.taller("T1", bloques=[BloqueHorario(1, time(8), time(10))])
    with pytest.raises(ConflictoHorarioError, match="tiempo de traslado insuficiente entre sedes"):
        mundo.taller("T2", sede=mundo.sede_b, bloques=[BloqueHorario(1, time(10), time(12))])
    mundo.taller("T3", sede=mundo.sede_b, bloques=[BloqueHorario(1, time(11), time(13))])


def test_docente_fuera_de_su_disponibilidad(mundo):
    docente, _ = mundo.nuevo_docente("tarde", "Danza", (time(14), time(20)))
    with pytest.raises(ConflictoHorarioError, match="fuera de su disponibilidad"):
        mundo.taller("T1", docente=docente)


def test_ambiente_ocupado(mundo):
    mundo.taller("T1", bloques=[BloqueHorario(1, time(8), time(10))])
    otro, _ = mundo.nuevo_docente("doc2", "Danza")
    with pytest.raises(ConflictoHorarioError, match="ambiente ocupado"):
        mundo.taller("T2", docente=otro, bloques=[BloqueHorario(1, time(9), time(10))])


def test_area_no_autorizada_y_excepcion_del_administrador(mundo, db):
    with pytest.raises(ReglaNegocioError, match="no está autorizado"):
        mundo.taller("T1", area="Teatro")
    datos = {
        "codigo": "T1", "nombre": "Teatro", "descripcion": None, "area_id": mundo.areas["Teatro"].id,
        "ciclo_academico_id": mundo.ciclo.id, "docente_id": mundo.docente.id, "sede_id": mundo.sede_a.id,
        "ambiente_id": mundo.aula_a.id, "cupo_maximo": 10, "horas_totales": 20, "umbral_aptitud": 80,
        "fecha_inicio": date(2026, 11, 9), "fecha_fin": date(2026, 12, 9),
    }
    docente_ctx = Contexto(db, Actor(mundo.docente.usuario_id, "Docente"), mundo.reloj)
    with pytest.raises(PermisoDenegadoError):
        taller_service.crear(docente_ctx, datos, "Justificación suficiente")
    taller = taller_service.crear(mundo.ctx, datos, "Reemplazo temporal aprobado por la dirección")
    db.flush()
    assert db.scalar(select(ExcepcionAreaDocente).where(ExcepcionAreaDocente.taller_id == taller.id))
    assert db.scalar(select(Auditoria).where(Auditoria.evento == "excepcion_area_docente"))


def test_cupo_no_supera_capacidad_del_ambiente(mundo):
    with pytest.raises(ReglaNegocioError, match="capacidad"):
        mundo.taller("T1", cupo=31)
