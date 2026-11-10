import {
  BookOpen,
  Building2,
  ClipboardList,
  GraduationCap,
  Home,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  UserCog,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";

import type { Rol } from "../api/tipos";
import { useAuth } from "../contexts/Auth";

const MENU: { a: string; texto: string; Icono: typeof Home; roles: Rol[] }[] = [
  { a: "/", texto: "Inicio", Icono: Home, roles: ["Administrador", "Docente", "Operador"] },
  { a: "/talleres", texto: "Talleres y asistencia", Icono: BookOpen, roles: ["Administrador", "Docente"] },
  { a: "/estudiantes", texto: "Estudiantes", Icono: GraduationCap, roles: ["Administrador"] },
  { a: "/docentes", texto: "Docentes", Icono: Users, roles: ["Administrador"] },
  { a: "/catalogos", texto: "Sedes y catálogos", Icono: Building2, roles: ["Administrador"] },
  { a: "/usuarios", texto: "Usuarios", Icono: UserCog, roles: ["Administrador"] },
  { a: "/auditoria", texto: "Auditoría", Icono: ShieldCheck, roles: ["Administrador"] },
  { a: "/parametros", texto: "Parámetros", Icono: Settings, roles: ["Administrador"] },
];

export function AppLayout() {
  const { usuario, salir } = useAuth();
  const navegar = useNavigate();
  const [abierto, setAbierto] = useState(false);
  if (!usuario) return null;
  const opciones = MENU.filter((m) => m.roles.includes(usuario.rol));

  const menu = (
    <nav aria-label="Menú principal" className="flex flex-col gap-1 p-3">
      {opciones.map(({ a, texto, Icono }) => (
        <NavLink
          key={a}
          to={a}
          end={a === "/"}
          onClick={() => setAbierto(false)}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-white/15 text-white" : "text-marca-100 hover:bg-white/10 hover:text-white"}`
          }
        >
          <Icono className="h-4 w-4" aria-hidden /> {texto}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-2">Ir al contenido</a>
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col overflow-y-auto bg-marca-800 lg:flex">
        <Marca />
        {menu}
      </aside>
      {abierto && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="w-64 bg-marca-800">
            <div className="flex items-center justify-between pr-2"><Marca /><button type="button" onClick={() => setAbierto(false)} aria-label="Cerrar menú" className="text-white"><X className="h-5 w-5" /></button></div>
            {menu}
          </div>
          <button type="button" aria-label="Cerrar menú" className="flex-1 bg-slate-900/40" onClick={() => setAbierto(false)} />
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-2.5">
          <button type="button" className="rounded p-1 text-slate-600 lg:hidden" onClick={() => setAbierto(true)} aria-label="Abrir menú">
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden text-sm text-slate-500 lg:block">Sistema de Gestión de Talleres Extracurriculares</div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-medium text-slate-800">{usuario.nombre_completo}</p>
              <p className="text-xs text-slate-500">{usuario.rol}</p>
            </div>
            <button
              type="button"
              onClick={async () => { await salir(); navegar("/login"); }}
              className="flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
            >
              <LogOut className="h-4 w-4" aria-hidden /> Salir
            </button>
          </div>
        </header>
        <main id="contenido" className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Marca() {
  return (
    <div className="flex items-center gap-2 px-4 py-4 text-white">
      <ClipboardList className="h-6 w-6" aria-hidden />
      <div>
        <p className="text-base font-semibold leading-tight">SIGET WEB</p>
        <p className="text-xs text-marca-100">UNAB · Arte y cultura</p>
      </div>
    </div>
  );
}
