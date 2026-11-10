export const DIAS = ["", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"] as const;
export const DIAS_CORTOS = ["", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"] as const;

export function fecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

export function fechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return `${fecha(iso)} ${iso.slice(11, 16)}`;
}

export function hora(valor: string): string {
  return valor.slice(0, 5);
}

export function diaDeFecha(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const dia = new Date(Date.UTC(a!, m! - 1, d!)).getUTCDay();
  return DIAS[dia === 0 ? 7 : dia]!;
}

export function nombreEstudiante(e: { nombres: string; apellido_paterno: string; apellido_materno: string | null }): string {
  return `${e.apellido_paterno} ${e.apellido_materno ?? ""}, ${e.nombres}`.replace(" ,", ",");
}
