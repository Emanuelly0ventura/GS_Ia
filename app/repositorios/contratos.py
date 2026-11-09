from datetime import datetime
from typing import Protocol
from uuid import UUID

RegistroCanonico = dict[str, object]

class RepositorioAutorizacao(Protocol):
    def usuario_pode_acessar(self, id_usuario: str, id_talhao: UUID, id_dispositivo: UUID) -> bool:
        """Verifica a relação autorizada sem presumir como ela é armazenada."""
        ...

class RepositorioPropriedadeETalhao(Protocol):
    def consultar_propriedade(self, id_talhao: UUID) -> RegistroCanonico | None:
        ...

    def consultar_talhao(self, id_talhao: UUID) -> RegistroCanonico | None:
        ...

class RepositorioContextoAgronomico(Protocol):
    def consultar_plantio(self, id_talhao: UUID) -> RegistroCanonico | None:
        ...

    def consultar_cultura(self, id_plantio: str) -> RegistroCanonico | None:
        ...

    def consultar_semente(self, id_plantio: str) -> RegistroCanonico | None:
        ...

    def consultar_solo(self, id_talhao: UUID) -> RegistroCanonico | None:
        ...

    def consultar_parametros_agronomicos(self, id_plantio: str) -> list[RegistroCanonico]:
        ...

class RepositorioDispositivosESensores(Protocol):
    def consultar_dispositivo(self, id_dispositivo: UUID) -> RegistroCanonico | None:
        ...

    def consultar_sensores(self, id_dispositivo: UUID) -> list[RegistroCanonico]:
        ...

    def consultar_eventos_e_qualidade(self, id_dispositivo: UUID, inicio: datetime, fim: datetime) -> list[RegistroCanonico]:
        ...

class RepositorioTelemetria(Protocol):
    def consultar_historico(self, id_dispositivo: UUID, inicio: datetime, fim: datetime) -> list[RegistroCanonico]:
        """Retorna leituras em formato canônico, independente do schema físico."""
        ...
