import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.db import FabricaSesion
from app.core.errores import ConflictoError, ConflictoHorarioError, PermisoDenegadoError, ReglaNegocioError
from app.models import (
    AutorizacionEdicion,
    EstadoAsistencia,
    EstadoInscripcion,
    EstadoSesion,
    ListaAptosDetalle,
    MovimientoInscripcion,
    Sesion,
    TipoMovimiento,
)
from app.services import aptos_service, asistencia_service, inscripcion_service, taller_service
from app.services import asistencia_calculator as calc
from app.services.asistencia_service import RegistroEntrada
from app.services.contexto import Actor, Contexto
from app.services.taller_service import BloqueHorario

P, A, J = EstadoAsistencia.PRESENTE, EstadoAsistencia.AUSENTE, EstadoAsistencia.JUSTIFICADO


# ---------- AsistenciaCalculator (unitarias) ----------

def _sesiones(n: int, inicio: date = date(2026, 9, 1)) -> list[tuple[int, date]]:
    return [(i + 1, inicio + timedelta(days=7 * i)) for i in range(n)]


def test_p_y_j_cuentan_a_no_cuenta():
    r = calc.calcular(sesiones_realizadas=_sesiones(4), periodos=[calc.Periodo(date(2026, 1, 1), None)],
                      asistencias={1: P, 2: J, 3: A, 4: P}, umbral_aptitud=80, umbral_riesgo_pct=10)
    assert (r.validas, r.faltas, r.porcentaje, r.apto) == (3, 1, Decimal("75.00"), False)


def test_sin_sesiones_realizadas_porcentaje_cero_sin_aptitud_ni_riesgo():
    r = calc.calcular(sesiones_realizadas=[], periodos=[calc.Periodo(date(2026, 1, 1), None)],
                      asistencias={}, umbral_aptitud=80, umbral_riesgo_pct=10)
    assert (r.porcentaje, r.calculable, r.apto, r.en_riesgo) == (Decimal("0.00"), False, None, None)


def test_riesgo_en_exactamente_diez_por_ciento_de_faltas():
    s = _sesiones(10)
    todo = calc.Periodo(date(2026, 1, 1), None)
    nueve = calc.calcular(sesiones_realizadas=s, periodos=[todo], asistencias={i: P for i in range(1, 10)} | {10: A},
                          umbral_aptitud=80, umbral_riesgo_pct=10)
    diez = calc.calcular(sesiones_realizadas=s, periodos=[todo], asistencias={i: P for i in range(1, 11)},
                         umbral_aptitud=80, umbral_riesgo_pct=10)
    assert nueve.en_riesgo is True and nueve.porcentaje == Decimal("90.00")
    assert diez.en_riesgo is False


def test_estudiante_que_entra_tarde_y_periodo_de_retiro():
    s = _sesiones(6)  # 1/9, 8/9, 15/9, 22/9, 29/9, 6/10
    movs = [(TipoMovimiento.ALTA, date(2026, 9, 8)), (TipoMovimiento.RETIRO, date(2026, 9, 20)),
            (TipoMovimiento.REACTIVACION, date(2026, 9, 29))]
    periodos = calc.periodos_desde_movimientos(movs)
    r = calc.calcular(sesiones_realizadas=s, periodos=periodos, asistencias={2: P, 3: P, 5: P, 6: A},
                      umbral_aptitud=75, umbral_riesgo_pct=10)
    # Le corresponden 8/9, 15/9, 29/9 y 6/10: la del 1/9 (antes del alta) y la del 22/9 (retirado) no.
    assert (r.sesiones_correspondientes, r.validas, r.porcentaje, r.apto) == (4, 3, Decimal("75.00"), True)


# ---------- Inscripciones ----------

def test_inscripcion_cupo_y_duplicado(mundo):
    t = mundo.taller("T1", cupo=1)
    e1, e2 = mundo.estudiante(), mundo.estudiante()
    inscripcion_service.inscribir(mundo.ctx, t.id, e1.id)
    with pytest.raises(ConflictoError, match="ya está inscrito"):
        inscripcion_service.inscribir(mundo.ctx, t.id, e1.id)
    with pytest.raises(ConflictoError, match="cupo"):
        inscripcion_service.inscribir(mundo.ctx, t.id, e2.id)


def test_estudiante_inactivo_no_se_inscribe(mundo):
    t = mundo.taller("T1")
    with pytest.raises(ReglaNegocioError, match="inactivo"):
        inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante(estado="Inactivo").id)


def test_cruce_de_estudiante(mundo):
    t1 = mundo.taller("T1", bloques=[BloqueHorario(3, time(8), time(10))])
    otro, _ = mundo.nuevo_docente("doc2", "Danza")
    t2 = mundo.taller("T2", docente=otro, ambiente=mundo.aula_a2, bloques=[BloqueHorario(3, time(9), time(11))])
    tercero, _ = mundo.nuevo_docente("doc3", "Danza")
    t3 = mundo.taller("T3", docente=tercero, ambiente=None, bloques=[BloqueHorario(3, time(10), time(12))])
    e = mundo.estudiante()
    inscripcion_service.inscribir(mundo.ctx, t1.id, e.id)
    with pytest.raises(ConflictoHorarioError, match="Estudiante: cruce de horario"):
        inscripcion_service.inscribir(mundo.ctx, t2.id, e.id)
    inscripcion_service.inscribir(mundo.ctx, t3.id, e.id)  # 10:00 con 10:00 no choca


def _realizar(mundo, taller, n):  # type: ignore[no-untyped-def]
    """Marca como realizadas las n primeras sesiones (registro completo como administrador)."""
    for sesion in taller_service.listar_sesiones(mundo.ctx, taller.id)[:n]:
        _, inscritos, _, _ = asistencia_service.hoja(mundo.ctx, sesion.id)
        asistencia_service.guardar(mundo.ctx, sesion.id, [RegistroEntrada(i.id, P, None) for i in inscritos])


def test_inscripciones_cerradas_tras_tres_sesiones_realizadas(mundo):
    t = mundo.taller("T1", bloques=[BloqueHorario(d, time(8), time(9)) for d in (1, 2, 3, 4, 5)], inicio=date(2026, 11, 2))
    inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    _realizar(mundo, t, 2)
    inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    _realizar(mundo, t, 3)
    with pytest.raises(ReglaNegocioError, match="Inscripciones cerradas"):
        inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)


def test_bloqueo_manual(mundo):
    t = mundo.taller("T1")
    taller_service.bloquear_inscripciones(mundo.ctx, t.id, True, "Revisión de cupos")
    with pytest.raises(ReglaNegocioError, match="Inscripciones bloqueadas: Revisión de cupos"):
        inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    taller_service.bloquear_inscripciones(mundo.ctx, t.id, False, None)
    inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)


def test_retiro_y_reactivacion_conservan_la_misma_inscripcion(mundo, db):
    t = mundo.taller("T1")
    e = mundo.estudiante()
    i = inscripcion_service.inscribir(mundo.ctx, t.id, e.id)
    inscripcion_service.retirar(mundo.ctx, i.id, "Motivos personales")
    otra = inscripcion_service.inscribir(mundo.ctx, t.id, e.id)
    assert otra.id == i.id and otra.estado == EstadoInscripcion.ACTIVO
    tipos = [m.tipo for m in inscripcion_service.listar_movimientos(db, i.id)]
    assert tipos == [TipoMovimiento.ALTA, TipoMovimiento.RETIRO, TipoMovimiento.REACTIVACION]


def test_cambio_de_taller(mundo, db):
    t1 = mundo.taller("T1", bloques=[BloqueHorario(1, time(8), time(10))])
    otro, _ = mundo.nuevo_docente("doc2", "Danza")
    t2 = mundo.taller("T2", docente=otro, ambiente=mundo.aula_a2, bloques=[BloqueHorario(1, time(9), time(11))])
    e = mundo.estudiante()
    i = inscripcion_service.inscribir(mundo.ctx, t1.id, e.id)
    destino = inscripcion_service.cambiar_taller(mundo.ctx, i.id, t2.id, "Cambio solicitado")
    assert db.get(type(i), i.id).estado == EstadoInscripcion.RETIRADO
    assert destino.taller_id == t2.id  # el cruce con el origen no cuenta: el origen se retira
    assert [m.tipo for m in inscripcion_service.listar_movimientos(db, destino.id)] == [TipoMovimiento.CAMBIO_ENTRADA]


def test_cupo_con_inscripciones_simultaneas(mundo, db):
    t = mundo.taller("T1", cupo=1)
    e1, e2 = mundo.estudiante(), mundo.estudiante()
    db.commit()
    resultados: list[str] = []
    barrera = threading.Barrier(2)

    def intentar(estudiante_id: int) -> None:
        with FabricaSesion() as sesion:
            ctx = Contexto(sesion, Actor(mundo.admin.id, "Administrador"), mundo.reloj)
            barrera.wait()
            try:
                inscripcion_service.inscribir(ctx, t.id, estudiante_id)
                sesion.commit()
                resultados.append("ok")
            except ConflictoError:
                sesion.rollback()
                resultados.append("sin_cupo")

    hilos = [threading.Thread(target=intentar, args=(e,)) for e in (e1.id, e2.id)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(resultados) == ["ok", "sin_cupo"]


# ---------- Asistencia ----------

def _ctx_docente(mundo, db):  # type: ignore[no-untyped-def]
    return Contexto(db, Actor(mundo.docente.usuario_id, "Docente"), mundo.reloj)


def test_registro_incompleto_y_j_sin_observacion(mundo):
    t = mundo.taller("T1")
    i1 = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    i2 = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    hoy = [s for s in taller_service.listar_sesiones(mundo.ctx, t.id) if s.fecha == mundo.reloj.hoy()][0]
    with pytest.raises(ReglaNegocioError, match="todos los inscritos"):
        asistencia_service.guardar(mundo.ctx, hoy.id, [RegistroEntrada(i1.id, P, None)])
    with pytest.raises(ReglaNegocioError, match="observación"):
        asistencia_service.guardar(mundo.ctx, hoy.id, [RegistroEntrada(i1.id, P, None), RegistroEntrada(i2.id, J, " ")])
    sesion = asistencia_service.guardar(mundo.ctx, hoy.id, [RegistroEntrada(i1.id, P, None), RegistroEntrada(i2.id, J, "Cita médica")])
    assert sesion.estado == EstadoSesion.REALIZADA


def test_asistencia_duplicada_impedida_por_la_base(mundo, db):
    t = mundo.taller("T1")
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    s = taller_service.listar_sesiones(mundo.ctx, t.id)[1]
    asistencia_service.guardar(mundo.ctx, s.id, [RegistroEntrada(i.id, P, None)])
    with pytest.raises(IntegrityError):
        db.execute(text("INSERT INTO asistencia (inscripcion_id, sesion_id, estado, registrado_por) VALUES (:i, :s, 'A', 1)"),
                   {"i": i.id, "s": s.id})


def test_congelacion_y_autorizacion_puntual(mundo, db):
    t = mundo.taller("T1")  # sesión del lunes 2/11 ya pasó (congelada)
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    pasada = taller_service.listar_sesiones(mundo.ctx, t.id)[0]
    docente = _ctx_docente(mundo, db)
    asistencia_service.guardar(docente, pasada.id, [RegistroEntrada(i.id, P, None)])  # primer registro, dentro de 7 días
    with pytest.raises(PermisoDenegadoError, match="congelada"):
        asistencia_service.guardar(docente, pasada.id, [RegistroEntrada(i.id, A, None)])
    autorizacion = asistencia_service.autorizar_edicion(mundo.ctx, pasada.id, "Error de digitación")
    asistencia_service.guardar(docente, pasada.id, [RegistroEntrada(i.id, A, None)])
    assert db.get(AutorizacionEdicion, autorizacion.id).consumida_en is not None
    with pytest.raises(PermisoDenegadoError):  # se consumió
        asistencia_service.guardar(docente, pasada.id, [RegistroEntrada(i.id, P, None)])
    asistencia_service.guardar(mundo.ctx, pasada.id, [RegistroEntrada(i.id, P, None)])  # el administrador siempre puede


def test_autorizacion_vence(mundo, db):
    t = mundo.taller("T1")
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    pasada = taller_service.listar_sesiones(mundo.ctx, t.id)[0]
    asistencia_service.guardar(mundo.ctx, pasada.id, [RegistroEntrada(i.id, P, None)])
    asistencia_service.autorizar_edicion(mundo.ctx, pasada.id, "Corrección")
    mundo.reloj.momento += timedelta(hours=73)
    with pytest.raises(PermisoDenegadoError):
        asistencia_service.guardar(_ctx_docente(mundo, db), pasada.id, [RegistroEntrada(i.id, A, None)])


def test_primer_registro_tardio_dentro_y_fuera_del_plazo(mundo, db):
    t = mundo.taller("T1", bloques=[BloqueHorario(d, time(8), time(9)) for d in (1, 2)], inicio=date(2026, 10, 26))
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    sesiones = {s.fecha: s for s in taller_service.listar_sesiones(mundo.ctx, t.id)}
    docente = _ctx_docente(mundo, db)
    asistencia_service.guardar(docente, sesiones[date(2026, 11, 2)].id, [RegistroEntrada(i.id, P, None)])  # 7 días: sí
    with pytest.raises(PermisoDenegadoError, match="solo el administrador"):
        asistencia_service.guardar(docente, sesiones[date(2026, 10, 27)].id, [RegistroEntrada(i.id, P, None)])  # 13 días


def test_cambio_de_dia_en_lima(mundo, db):
    t = mundo.taller("T1")
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    hoy = [s for s in taller_service.listar_sesiones(mundo.ctx, t.id) if s.fecha == date(2026, 11, 9)][0]
    docente = _ctx_docente(mundo, db)
    mundo.reloj.momento = datetime(2026, 11, 9, 23, 59)
    asistencia_service.guardar(docente, hoy.id, [RegistroEntrada(i.id, P, None)])
    mundo.reloj.momento = datetime(2026, 11, 10, 0, 1)  # un minuto después ya está congelada
    with pytest.raises(PermisoDenegadoError, match="congelada"):
        asistencia_service.guardar(docente, hoy.id, [RegistroEntrada(i.id, A, None)])


# ---------- Sesiones ----------

def test_cancelar_sesion_reglas(mundo, db):
    t = mundo.taller("T1", inicio=date(2026, 10, 19))
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    s = {x.fecha: x for x in taller_service.listar_sesiones(mundo.ctx, t.id)}
    docente = _ctx_docente(mundo, db)
    taller_service.cancelar_sesion(docente, s[date(2026, 11, 2)].id, "Feriado local")  # 7 días: permitido
    with pytest.raises(PermisoDenegadoError):
        taller_service.cancelar_sesion(docente, s[date(2026, 10, 19)].id, "Fuera de plazo")
    taller_service.cancelar_sesion(mundo.ctx, s[date(2026, 10, 19)].id, "El administrador siempre puede")
    asistencia_service.guardar(mundo.ctx, s[date(2026, 10, 26)].id, [RegistroEntrada(i.id, P, None)])
    with pytest.raises(ReglaNegocioError, match="asistencia registrada"):
        taller_service.cancelar_sesion(mundo.ctx, s[date(2026, 10, 26)].id, "No debe poder")


def test_sesiones_vencidas_sin_registro(mundo, db):
    t = mundo.taller("T1", inicio=date(2026, 10, 26))
    vencidas = taller_service.sesiones_vencidas(db, mundo.reloj.hoy())
    assert {s.fecha for s in vencidas} == {date(2026, 10, 26), date(2026, 11, 2)}
    assert all(s.taller_id == t.id for s in vencidas)


# ---------- Lista de aptos ----------

def _taller_corto(mundo):  # type: ignore[no-untyped-def]
    return mundo.taller("T1", bloques=[BloqueHorario(1, time(8), time(10))], inicio=date(2026, 10, 19), fin=date(2026, 11, 9))


def test_lista_bloqueada_mientras_haya_programadas(mundo):
    t = _taller_corto(mundo)
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    _realizar(mundo, t, 2)
    with pytest.raises(ReglaNegocioError, match="programadas"):
        aptos_service.generar(mundo.ctx, t.id, {})
    sesiones = taller_service.listar_sesiones(mundo.ctx, t.id)
    taller_service.cancelar_sesion(mundo.ctx, sesiones[2].id, "Feriado")  # cancelada no bloquea
    asistencia_service.guardar(mundo.ctx, sesiones[3].id, [RegistroEntrada(i.id, A, None)])
    lista = aptos_service.generar(mundo.ctx, t.id, {})
    assert lista.total_aptos == 0  # 2 de 3 = 66,67 % < 80 %


def test_lista_inmutable_exclusion_y_versiones(mundo, db):
    t = _taller_corto(mundo)
    e1, e2 = mundo.estudiante(nombres="=CMD()"), mundo.estudiante()
    inscripcion_service.inscribir(mundo.ctx, t.id, e1.id)
    i2 = inscripcion_service.inscribir(mundo.ctx, t.id, e2.id)
    _realizar(mundo, t, 4)
    lista = aptos_service.generar(mundo.ctx, t.id, {e2.id: "Sanción disciplinaria"})
    assert lista.total_aptos == 1 and lista.total_excluidos == 1
    with pytest.raises(ConflictoError, match="vigente"):
        aptos_service.generar(mundo.ctx, t.id, {})
    # Cambiar asistencias y umbral después no altera la lista generada.
    s = taller_service.listar_sesiones(mundo.ctx, t.id)[0]
    asistencia_service.guardar(mundo.ctx, s.id, [RegistroEntrada(x.id, A, None) for x in asistencia_service.hoja(mundo.ctx, s.id)[1]])
    taller_service.actualizar(mundo.ctx, t.id, {"umbral_aptitud": 50}, None)
    db.expire_all()
    detalle = {d.estudiante_id: d for d in db.scalars(select(ListaAptosDetalle).where(ListaAptosDetalle.lista_id == lista.id))}
    assert detalle[e1.id].porcentaje == Decimal("100.00") and detalle[e1.id].es_apto
    assert detalle[e2.id].excluido_manual and detalle[e2.id].motivo_exclusion == "Sanción disciplinaria"
    aptos_service.anular(mundo.ctx, lista.id, "Error en exclusión")
    nueva = aptos_service.generar(mundo.ctx, t.id, {})
    assert nueva.version == 2


def test_exportacion_excel_neutraliza_formulas(mundo):
    t = _taller_corto(mundo)
    inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante(nombres="=HYPERLINK(\"x\")").id)
    _realizar(mundo, t, 4)
    lista = aptos_service.generar(mundo.ctx, t.id, {})
    _, contenido = aptos_service.exportar_excel(mundo.ctx, lista.id)
    hoja = load_workbook(BytesIO(contenido)).active
    nombres = [fila[6] for fila in hoja.iter_rows(min_row=5, values_only=True)]
    assert nombres == ["'=HYPERLINK(\"x\")"]


def test_docente_no_genera_lista(cliente, mundo, db):
    from tests.conftest import iniciar

    t = _taller_corto(mundo)
    db.commit()
    iniciar(cliente, "doc1")
    assert cliente.post(f"/api/v1/talleres/{t.id}/aptos", json={"exclusiones": []}).status_code == 403
    assert cliente.get(f"/api/v1/talleres/{t.id}/aptos/avance").status_code == 200


def test_movimientos_registran_usuario(mundo, db):
    t = mundo.taller("T1")
    i = inscripcion_service.inscribir(mundo.ctx, t.id, mundo.estudiante().id)
    m = db.scalar(select(MovimientoInscripcion).where(MovimientoInscripcion.inscripcion_id == i.id))
    assert m.usuario_id == mundo.admin.id and m.fecha == mundo.reloj.hoy()
