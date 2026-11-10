"""Comandos de consola.

  python -m app.cli crear-admin --usuario admin --email admin@unab.edu.pe
      Pide la contraseña (o la lee de ADMIN_PASSWORD) y obliga a cambiarla al entrar.
  python -m app.cli datos-demo
      Carga datos de ejemplo. Se niega a correr con ENTORNO=produccion.
"""
import argparse
import getpass
import os
import sys
from datetime import time, timedelta

from sqlalchemy import select, update

from app.core.config import obtener_configuracion
from app.core.db import FabricaSesion
from app.core.reloj import obtener_reloj
from app.models import EstadoAsistencia, Rol, Usuario
from app.services import (
    asistencia_service,
    catalogo_service,
    inscripcion_service,
    persona_service,
    taller_service,
    usuario_service,
)
from app.services.contexto import Actor, Contexto


def crear_admin(args: argparse.Namespace) -> int:
    with FabricaSesion() as db:
        if args.si_no_existe and db.scalar(select(Usuario.id).join(Rol).where(Rol.nombre == Rol.ADMINISTRADOR)):
            print("Ya existe un administrador; no se crea otro.")
            return 0
        password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Contraseña inicial: ")
        # Sin actor: la auditoría registra que lo creó la consola, no una persona del sistema.
        ctx = Contexto(db=db, actor=None, reloj=obtener_reloj())  # type: ignore[arg-type]
        usuario, _ = usuario_service.crear(
            ctx, username=args.usuario, email=args.email, nombres=args.nombres,
            apellido_paterno=args.apellido, apellido_materno=None, rol=Rol.ADMINISTRADOR,
            password=password, debe_cambiar=True,
        )
        db.commit()
        print(f"Administrador '{usuario.username}' creado. Deberá cambiar la contraseña al ingresar.")
    return 0


def datos_demo(_: argparse.Namespace) -> int:
    if obtener_configuracion().es_produccion:
        print("Los datos de ejemplo nunca se cargan con ENTORNO=produccion.", file=sys.stderr)
        return 1
    reloj = obtener_reloj()
    hoy = reloj.hoy()
    with FabricaSesion() as db:
        admin = db.scalar(select(Usuario).join(Rol).where(Rol.nombre == Rol.ADMINISTRADOR))
        if admin is None:
            print("Primero cree el administrador con crear-admin.", file=sys.stderr)
            return 1
        ctx = Contexto(db=db, actor=Actor(usuario_id=admin.id, rol=Rol.ADMINISTRADOR, ip="consola"), reloj=reloj)
        from app.models import Ambiente, Area, Carrera, CicloAcademico, Facultad, Sede

        if db.scalar(select(Sede.id)):
            print("Ya hay datos cargados; no se cargan los de ejemplo.")
            return 0
        sede_a = catalogo_service.crear(ctx, Sede, {"nombre": "Sede Central (ejemplo)", "direccion": "Av. Ejemplo 100"})
        sede_b = catalogo_service.crear(ctx, Sede, {"nombre": "Sede Norte (ejemplo)", "direccion": "Jr. Ejemplo 200"})
        aula_a = catalogo_service.crear(ctx, Ambiente, {"sede_id": sede_a.id, "codigo": "A-101", "nombre": "Sala de danza", "capacidad": 30})
        catalogo_service.crear(ctx, Ambiente, {"sede_id": sede_a.id, "codigo": "A-102", "nombre": "Sala de música", "capacidad": 25})
        aula_b = catalogo_service.crear(ctx, Ambiente, {"sede_id": sede_b.id, "codigo": "N-201", "nombre": "Taller de artes", "capacidad": 20})
        facultad = catalogo_service.crear(ctx, Facultad, {"codigo": "FI", "nombre": "Facultad de Ingeniería (ejemplo)"})
        carreras = [
            catalogo_service.crear(ctx, Carrera, {"facultad_id": facultad.id, "codigo": c, "nombre": n})
            for c, n in (("IS", "Ingeniería de Sistemas"), ("II", "Ingeniería Industrial"))
        ]
        ciclo = catalogo_service.crear(ctx, CicloAcademico, {"nombre": f"{hoy.year}-DEMO", "fecha_inicio": hoy - timedelta(days=60), "fecha_fin": hoy + timedelta(days=60)})
        catalogo_service.activar_ciclo(ctx, ciclo.id)
        areas = {a.nombre: a for a in db.scalars(select(Area))}

        docentes = []
        for i, (nombre, ap, area) in enumerate((("Lucía", "Ramos", "Danza"), ("Jorge", "Salas", "Dibujo y Pintura"))):
            docente, _ = persona_service.crear_docente(ctx, {
                "username": f"docente{i + 1}", "email": f"docente{i + 1}@ejemplo.pe", "tipo_documento_id": 1,
                "numero_documento": f"4000000{i + 1}", "nombres": nombre, "apellido_paterno": ap,
                "apellido_materno": "Demo", "area_ids": [areas[area].id],
            })
            persona_service.fijar_disponibilidad(ctx, docente.id, [(d, time(8), time(20), None, None) for d in range(1, 7)])
            docentes.append(docente)

        estudiantes = []
        nombres = ["Ana", "Bruno", "Carla", "Diego", "Elena", "Fabio", "Gina", "Hugo", "Inés", "Julio", "Karen", "Luis"]
        apellidos = ["Quispe", "Huamán", "Flores", "Rojas", "Torres", "Díaz", "Castillo", "Vargas", "Mendoza", "Paredes", "Chávez", "Ríos"]
        for i, (n, a) in enumerate(zip(nombres, apellidos, strict=True)):
            estudiantes.append(persona_service.crear_estudiante(ctx, {
                "tipo_documento_id": 1, "numero_documento": f"7{i:07d}", "codigo_universitario": f"2026{i:04d}",
                "nombres": n, "apellido_paterno": a, "apellido_materno": "Demo", "carrera_id": carreras[i % 2].id,
                "ciclo_actual": 1 + i % 8, "estado": "Activo",
            }))

        hace = hoy - timedelta(days=21)
        t1 = taller_service.crear(ctx, {
            "codigo": "DAN-01", "nombre": "Danza folclórica", "descripcion": "Taller de ejemplo", "area_id": areas["Danza"].id,
            "ciclo_academico_id": ciclo.id, "docente_id": docentes[0].id, "sede_id": sede_a.id, "ambiente_id": aula_a.id,
            "cupo_maximo": 25, "horas_totales": 32, "umbral_aptitud": 80, "fecha_inicio": hace, "fecha_fin": hoy + timedelta(days=35),
        }, None)
        taller_service.fijar_horarios(ctx, t1.id, [
            taller_service.BloqueHorario(1, time(8), time(10)), taller_service.BloqueHorario(3, time(15), time(17))
        ], "Horario inicial")
        t2 = taller_service.crear(ctx, {
            "codigo": "DIB-01", "nombre": "Dibujo y pintura", "descripcion": "Taller de ejemplo", "area_id": areas["Dibujo y Pintura"].id,
            "ciclo_academico_id": ciclo.id, "docente_id": docentes[1].id, "sede_id": sede_b.id, "ambiente_id": aula_b.id,
            "cupo_maximo": 20, "horas_totales": 24, "umbral_aptitud": 75, "fecha_inicio": hace, "fecha_fin": hoy + timedelta(days=35),
        }, None)
        taller_service.fijar_horarios(ctx, t2.id, [taller_service.BloqueHorario(5, time(9), time(12))], "Horario inicial")
        for e in estudiantes[:8]:
            inscripcion_service.inscribir(ctx, t1.id, e.id)
        for e in estudiantes[6:]:
            inscripcion_service.inscribir(ctx, t2.id, e.id)
        # Solo para el ejemplo: simular que se inscribieron al iniciar el taller.
        from app.models import Inscripcion, MovimientoInscripcion
        ids = list(db.scalars(select(Inscripcion.id)))
        db.execute(update(Inscripcion).where(Inscripcion.id.in_(ids)).values(fecha_inscripcion=hace))
        db.execute(update(MovimientoInscripcion).where(MovimientoInscripcion.inscripcion_id.in_(ids)).values(fecha=hace))
        # Asistencia de las sesiones pasadas, menos la más reciente (queda como "vencida sin registro").
        pasadas = [s for s in taller_service.listar_sesiones(ctx, t1.id) if s.fecha < hoy][:-1]
        for n, sesion in enumerate(pasadas):
            _, inscritos, _, _ = asistencia_service.hoja(ctx, sesion.id)
            registros = [
                asistencia_service.RegistroEntrada(
                    i.id,
                    EstadoAsistencia("A" if (k + n) % 5 == 0 else ("J" if (k + n) % 7 == 0 else "P")),
                    "Certificado médico (ejemplo)" if (k + n) % 7 == 0 and (k + n) % 5 else None,
                )
                for k, i in enumerate(inscritos)
            ]
            asistencia_service.guardar(ctx, sesion.id, registros)
        db.commit()
        print("Datos de ejemplo cargados: 2 sedes, 2 docentes (docente1, docente2), 12 estudiantes, 2 talleres.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(prog="python -m app.cli")
    sub = analizador.add_subparsers(dest="comando", required=True)
    admin = sub.add_parser("crear-admin")
    admin.add_argument("--usuario", default=os.environ.get("ADMIN_USERNAME", "admin"))
    admin.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", "admin@siget.local"))
    admin.add_argument("--nombres", default="Administrador")
    admin.add_argument("--apellido", default="SIGET")
    admin.add_argument("--si-no-existe", action="store_true")
    admin.set_defaults(fn=crear_admin)
    demo = sub.add_parser("datos-demo")
    demo.set_defaults(fn=datos_demo)
    args = analizador.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
