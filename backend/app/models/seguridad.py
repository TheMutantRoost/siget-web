from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ConFechas


class Rol(Base):
    __tablename__ = "roles"
    ADMINISTRADOR = "Administrador"
    DOCENTE = "Docente"
    OPERADOR = "Operador"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)


class Usuario(ConFechas, Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    nombres: Mapped[str] = mapped_column(String(100))
    apellido_paterno: Mapped[str] = mapped_column(String(60))
    apellido_materno: Mapped[str | None] = mapped_column(String(60))
    password_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)
    intentos_fallidos: Mapped[int] = mapped_column(SmallInteger, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime)

    rol: Mapped[Rol] = relationship(lazy="joined")

    @property
    def nombre_completo(self) -> str:
        return " ".join(p for p in (self.nombres, self.apellido_paterno, self.apellido_materno) if p)

    @property
    def rol_nombre(self) -> str:
        return self.rol.nombre


class SesionUsuario(Base):
    __tablename__ = "sesiones_usuario"
    __table_args__ = (Index("ix_sesiones_usuario_usuario_cerrada", "usuario_id", "cerrada_en"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    creada_en: Mapped[datetime] = mapped_column(DateTime)
    ultimo_uso: Mapped[datetime] = mapped_column(DateTime)
    expira_absoluta: Mapped[datetime] = mapped_column(DateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime)
    cerrada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo_cierre: Mapped[str | None] = mapped_column(String(40))

    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id], lazy="joined")


class IntentoLogin(Base):
    __tablename__ = "intentos_login"
    __table_args__ = (
        Index("ix_intentos_login_ip_fecha", "ip", "fecha"),
        Index("ix_intentos_login_username_fecha", "username", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
    ip: Mapped[str] = mapped_column(String(45))
    exito: Mapped[bool] = mapped_column(Boolean)
    fecha: Mapped[datetime] = mapped_column(DateTime)


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (
        Index("ix_auditoria_modulo_fecha", "modulo", "created_at"),
        Index("ix_auditoria_entidad_registro", "entidad", "registro_id"),
        Index("ix_auditoria_usuario_fecha", "usuario_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    modulo: Mapped[str] = mapped_column(String(40))
    evento: Mapped[str] = mapped_column(String(60))
    accion: Mapped[str] = mapped_column(String(10))  # crear, modificar, eliminar, evento
    entidad: Mapped[str | None] = mapped_column(String(60))
    registro_id: Mapped[str | None] = mapped_column(String(40))
    datos_anteriores: Mapped[dict | None] = mapped_column(JSON)
    datos_nuevos: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ParametroSistema(Base):
    __tablename__ = "parametros_sistema"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    clave: Mapped[str] = mapped_column(String(60), unique=True)
    valor: Mapped[int] = mapped_column(Integer)
    minimo: Mapped[int] = mapped_column(Integer)
    maximo: Mapped[int] = mapped_column(Integer)
    descripcion: Mapped[str] = mapped_column(Text)
    actualizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
