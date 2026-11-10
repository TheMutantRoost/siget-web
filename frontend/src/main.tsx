import "./configZod";
import "./index.css";

import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, Outlet, RouterProvider, useLocation } from "react-router";

import type { Rol } from "./api/tipos";
import { Cargando, Vacio } from "./components/ui";
import { ProveedorAuth, useAuth } from "./contexts/Auth";
import { ProveedorNotificaciones } from "./contexts/Notificaciones";
import { AppLayout } from "./layouts/AppLayout";
import { Auditoria, Parametros, Usuarios } from "./pages/Administracion";
import { Asistencia } from "./pages/Asistencia";
import { CambiarPassword } from "./pages/CambiarPassword";
import { Catalogos } from "./pages/Catalogos";
import { Dashboard } from "./pages/Dashboard";
import { Docentes } from "./pages/Docentes";
import { Estudiantes } from "./pages/Estudiantes";
import { Login } from "./pages/Login";
import { TallerDetalle } from "./pages/TallerDetalle";
import { Talleres } from "./pages/Talleres";

function Protegida() {
  const { usuario, cargando } = useAuth();
  const ubicacion = useLocation();
  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (!usuario) return <Navigate to="/login" replace />;
  if (usuario.debe_cambiar_password && ubicacion.pathname !== "/cambiar-password") return <Navigate to="/cambiar-password" replace />;
  return <Outlet />;
}

function SoloRoles({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { usuario } = useAuth();
  if (!usuario || !roles.includes(usuario.rol)) return <Vacio titulo="No tiene acceso a esta sección." />;
  return children;
}

const ADMIN: Rol[] = ["Administrador"];
const ACADEMICO: Rol[] = ["Administrador", "Docente"];

const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    element: <Protegida />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Dashboard /> },
          { path: "cambiar-password", element: <CambiarPassword /> },
          { path: "talleres", element: <SoloRoles roles={ACADEMICO}><Talleres /></SoloRoles> },
          { path: "talleres/:id", element: <SoloRoles roles={ACADEMICO}><TallerDetalle /></SoloRoles> },
          { path: "sesiones/:id/asistencia", element: <SoloRoles roles={ACADEMICO}><Asistencia /></SoloRoles> },
          { path: "estudiantes", element: <SoloRoles roles={ADMIN}><Estudiantes /></SoloRoles> },
          { path: "docentes", element: <SoloRoles roles={ADMIN}><Docentes /></SoloRoles> },
          { path: "catalogos", element: <SoloRoles roles={ADMIN}><Catalogos /></SoloRoles> },
          { path: "usuarios", element: <SoloRoles roles={ADMIN}><Usuarios /></SoloRoles> },
          { path: "auditoria", element: <SoloRoles roles={ADMIN}><Auditoria /></SoloRoles> },
          { path: "parametros", element: <SoloRoles roles={ADMIN}><Parametros /></SoloRoles> },
          { path: "*", element: <Vacio titulo="Página no encontrada." /> },
        ],
      },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ProveedorNotificaciones>
      <ProveedorAuth>
        <RouterProvider router={router} />
      </ProveedorAuth>
    </ProveedorNotificaciones>
  </StrictMode>,
);
