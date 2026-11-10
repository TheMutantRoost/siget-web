import { AlertTriangle, BookOpen, CalendarClock, CheckCircle2, GraduationCap, Percent, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import type { Dashboard as Datos, Sede, TallerIndicador } from "../api/tipos";
import { Alerta, Cargando, Celda, Encabezado, Selector, Tabla, Tarjeta, Vacio } from "../components/ui";
import { useAuth } from "../contexts/Auth";
import { useApi } from "../hooks/useApi";
import { diaDeFecha, fecha } from "../utils/formato";

function Indicador({ titulo, valor, Icono, color = "text-marca-700" }: { titulo: string; valor: string | number; Icono: typeof Users; color?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-xs">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{titulo}</p>
        <Icono className={`h-5 w-5 ${color}`} aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{valor}</p>
    </div>
  );
}

function BarraAptos({ aptos, noAptos }: { aptos: number; noAptos: number }) {
  const total = aptos + noAptos;
  if (!total) return <p className="text-sm text-slate-500">Aún no hay sesiones realizadas para calcular la aptitud.</p>;
  const pct = Math.round((aptos * 100) / total);
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-red-100" role="img" aria-label={`${pct} % aptos`}>
        <div className="bg-green-600" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-2 flex justify-between text-sm">
        <span className="text-green-700">{aptos} aptos ({pct} %)</span>
        <span className="text-red-700">{noAptos} no aptos</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">Avance informativo según el umbral de cada taller; no es la lista definitiva.</p>
    </div>
  );
}

function TablaTalleres({ filas }: { filas: TallerIndicador[] }) {
  return (
    <Tabla encabezados={["Taller", "Sede", "Fin", "Inscritos", "En riesgo", "% prom."]} vacio={!filas.length}>
      {filas.map((t) => (
        <tr key={t.id}>
          <Celda><Link to={`/talleres/${t.id}`} className="font-medium text-marca-700 hover:underline">{t.codigo} · {t.nombre}</Link></Celda>
          <Celda>{t.sede}</Celda>
          <Celda>{fecha(t.fecha_fin)}</Celda>
          <Celda>{t.inscritos}</Celda>
          <Celda>{t.en_riesgo}</Celda>
          <Celda>{t.porcentaje_promedio ?? "—"}</Celda>
        </tr>
      ))}
    </Tabla>
  );
}

export function Dashboard() {
  const { usuario } = useAuth();
  const [sede, setSede] = useState("");
  const { datos, cargando, error } = useApi<Datos>("/dashboard", { sede_id: sede });
  const sedes = useApi<Sede[]>("/catalogos/sedes");
  const esAdmin = usuario?.rol === "Administrador";

  if (usuario?.rol === "Operador") {
    return (
      <>
        <Encabezado titulo={`Hola, ${usuario.nombre_completo}`} />
        <Alerta>El módulo de bienes patrimoniales se habilitará en la siguiente entrega.</Alerta>
      </>
    );
  }

  return (
    <>
      <Encabezado
        titulo="Inicio"
        descripcion={esAdmin ? "Indicadores generales de los talleres" : "Indicadores de sus talleres"}
        acciones={
          <div className="w-56">
            <Selector etiqueta="Sede" value={sede} onChange={(e) => setSede(e.target.value)} vacio="Todas las sedes" opciones={(sedes.datos ?? []).map((s) => ({ valor: s.id, texto: s.nombre }))} />
          </div>
        }
      />
      {error && <Alerta tipo="error">{error}</Alerta>}
      {cargando || !datos ? <Cargando /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {esAdmin && <Indicador titulo="Estudiantes activos" valor={datos.estudiantes_activos} Icono={GraduationCap} />}
            {esAdmin && <Indicador titulo="Docentes activos" valor={datos.docentes_activos} Icono={Users} />}
            <Indicador titulo="Talleres activos" valor={datos.talleres_activos} Icono={BookOpen} />
            <Indicador titulo="Talleres finalizados" valor={datos.talleres_finalizados} Icono={CheckCircle2} color="text-slate-500" />
            <Indicador titulo="Inscripciones activas" valor={datos.inscripciones_activas} Icono={Users} />
            <Indicador titulo="Asistencia general" valor={datos.asistencia_general === null ? "—" : `${datos.asistencia_general} %`} Icono={Percent} />
          </div>
          {esAdmin && datos.sesiones_vencidas.length > 0 && (
            <Tarjeta titulo={<span className="flex items-center gap-2 text-amber-800"><CalendarClock className="h-5 w-5" aria-hidden /> Sesiones vencidas sin registro ({datos.sesiones_vencidas.length})</span>}>
              <Tabla encabezados={["Taller", "Sesión", "Fecha", "Horario", ""]}>
                {datos.sesiones_vencidas.slice(0, 10).map((s) => (
                  <tr key={s.sesion_id}>
                    <Celda>{s.taller}</Celda>
                    <Celda>N.° {s.numero}</Celda>
                    <Celda>{diaDeFecha(s.fecha)} {fecha(s.fecha)}</Celda>
                    <Celda>{s.inicio}–{s.fin}</Celda>
                    <Celda className="text-right space-x-3">
                      <Link to={`/sesiones/${s.sesion_id}/asistencia`} className="text-marca-700 hover:underline">Registrar</Link>
                      <Link to={`/talleres/${s.taller_id}?pestana=sesiones`} className="text-marca-700 hover:underline">Cancelar</Link>
                    </Celda>
                  </tr>
                ))}
              </Tabla>
            </Tarjeta>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Tarjeta titulo="Aptos y no aptos (avance)"><BarraAptos aptos={datos.aptos} noAptos={datos.no_aptos} /></Tarjeta>
            <Tarjeta titulo={<span className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-amber-600" aria-hidden /> Estudiantes en riesgo: {datos.estudiantes_en_riesgo}</span>}>
              {datos.talleres_en_riesgo.length ? <TablaTalleres filas={datos.talleres_en_riesgo} /> : <Vacio titulo="Ningún taller tiene estudiantes en riesgo." />}
            </Tarjeta>
          </div>
          <Tarjeta titulo="Talleres próximos a finalizar (14 días)">
            {datos.proximos_a_finalizar.length ? <TablaTalleres filas={datos.proximos_a_finalizar} /> : <Vacio titulo="No hay talleres por finalizar en los próximos 14 días." />}
          </Tarjeta>
        </div>
      )}
    </>
  );
}
