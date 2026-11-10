"""Única fuente de "hoy" y "ahora" (America/Lima). Las pruebas la reemplazan."""
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from app.core.config import ZONA_HORARIA

_ZONA = ZoneInfo(ZONA_HORARIA)


class Reloj(Protocol):
    def ahora(self) -> datetime: ...

    def hoy(self) -> date: ...


class RelojSistema:
    """Devuelve fecha y hora de Lima sin tzinfo, igual que las columnas DATETIME."""

    def ahora(self) -> datetime:
        return datetime.now(_ZONA).replace(tzinfo=None, microsecond=0)

    def hoy(self) -> date:
        return self.ahora().date()


class RelojFijo:
    def __init__(self, momento: datetime) -> None:
        self.momento = momento

    def ahora(self) -> datetime:
        return self.momento

    def hoy(self) -> date:
        return self.momento.date()


_reloj: Reloj = RelojSistema()


def obtener_reloj() -> Reloj:
    return _reloj
