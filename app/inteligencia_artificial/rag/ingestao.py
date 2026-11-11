import json
from pathlib import Path
import re

from pydantic import ValidationError

from app.inteligencia_artificial.rag.esquemas import DocumentoConhecimento

EXTENSOES_SUPORTADAS = {".md", ".txt"}


def normalizar_conteudo(conteudo: str) -> str:
    conteudo = conteudo.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    conteudo = "".join(caractere for caractere in conteudo if caractere in "\n\t" or ord(caractere) >= 32)
    return re.sub(r"[ \t]+\n", "\n", conteudo).strip()


def ingerir_diretorio(
    diretorio: str | Path,
    *,
    limite_documento_bytes: int = 5_000_000,
    limite_documentos: int = 100,
    limite_total_bytes: int = 50_000_000,
    limite_metadados_bytes: int = 65_536,
) -> list[DocumentoConhecimento]:
    """Lê somente arquivos locais .md/.txt com sidecar .metadata.json correspondente.

    Formato: documento.md e documento.metadata.json. A ingestão nunca percorre
    URLs nem executa conteúdo dos documentos.
    """
    for nome, valor in (
        ("limite_documento_bytes", limite_documento_bytes),
        ("limite_documentos", limite_documentos),
        ("limite_total_bytes", limite_total_bytes),
        ("limite_metadados_bytes", limite_metadados_bytes),
    ):
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 1:
            raise ValueError(f"{nome} deve ser um inteiro positivo.")

    raiz = Path(diretorio).resolve(strict=True)
    if not raiz.is_dir():
        raise ValueError("O caminho de ingestão precisa ser um diretório local.")

    candidatos: list[tuple[Path, Path, int, int]] = []
    total_previo = 0
    for caminho in raiz.rglob("*"):
        if not caminho.is_file() or caminho.suffix.lower() not in EXTENSOES_SUPORTADAS:
            continue
        if len(candidatos) >= limite_documentos:
            raise ValueError(f"A ingestão excede o limite de {limite_documentos} documentos.")
        resolvido = caminho.resolve(strict=True)
        if not resolvido.is_relative_to(raiz):
            raise ValueError("A ingestão não pode sair do diretório local configurado.")
        sidecar = caminho.with_name(f"{caminho.stem}.metadata.json")
        if not sidecar.is_file():
            raise ValueError(f"Metadados obrigatórios ausentes para {caminho.name}.")
        sidecar_resolvido = sidecar.resolve(strict=True)
        if not sidecar_resolvido.is_relative_to(raiz):
            raise ValueError("O arquivo de metadados precisa permanecer no diretório local configurado.")
        tamanho_documento = resolvido.stat().st_size
        tamanho_metadados = sidecar_resolvido.stat().st_size
        if tamanho_documento > limite_documento_bytes:
            raise ValueError(f"Documento {caminho.name} excede {limite_documento_bytes} bytes.")
        if tamanho_metadados > limite_metadados_bytes:
            raise ValueError(f"Metadados de {caminho.name} excedem {limite_metadados_bytes} bytes.")
        total_previo += tamanho_documento + tamanho_metadados
        if total_previo > limite_total_bytes:
            raise ValueError(f"A ingestão excede o limite total de {limite_total_bytes} bytes.")
        candidatos.append((resolvido, sidecar_resolvido, tamanho_documento, tamanho_metadados))

    candidatos.sort(key=lambda item: item[0].relative_to(raiz).as_posix())
    documentos: list[DocumentoConhecimento] = []
    identificadores: set[str] = set()
    total_lido = 0
    for resolvido, sidecar_resolvido, tamanho_documento, tamanho_metadados in candidatos:
        try:
            with sidecar_resolvido.open("rb") as arquivo_metadados:
                bytes_metadados = arquivo_metadados.read(limite_metadados_bytes + 1)
            if len(bytes_metadados) > limite_metadados_bytes:
                raise ValueError("Metadados excedem o limite configurado.")
            with resolvido.open("rb") as arquivo_documento:
                bytes_documento = arquivo_documento.read(limite_documento_bytes + 1)
            if len(bytes_documento) > limite_documento_bytes:
                raise ValueError("Documento excede o limite configurado.")
            total_lido += len(bytes_metadados) + len(bytes_documento)
            if total_lido > limite_total_bytes:
                raise ValueError("A ingestão excede o limite total configurado.")
            if len(bytes_metadados) != tamanho_metadados or len(bytes_documento) != tamanho_documento:
                raise ValueError("Um arquivo mudou durante a ingestão; repita a operação.")
            metadados = json.loads(bytes_metadados.decode("utf-8"))
            if not isinstance(metadados, dict):
                raise ValueError("O arquivo de metadados precisa conter um objeto JSON.")
            documento = DocumentoConhecimento.model_validate({
                **metadados,
                "conteudo": normalizar_conteudo(bytes_documento.decode("utf-8")),
            })
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValidationError) as erro:
            raise ValueError(f"Documento ou metadados inválidos em {resolvido.name}.") from erro
        if documento.identificador in identificadores:
            raise ValueError(f"Identificador documental duplicado: {documento.identificador}.")
        identificadores.add(documento.identificador)
        documentos.append(documento)
    return documentos
