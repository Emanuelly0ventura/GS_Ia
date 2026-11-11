import re

from app.inteligencia_artificial.rag.esquemas import DocumentoConhecimento, TrechoConhecimento


def segmentar_documento(
    documento: DocumentoConhecimento,
    tamanho_maximo: int = 1200,
    sobreposicao: int = 160,
    limite_trechos: int | None = None,
) -> list[TrechoConhecimento]:
    """Divide por parágrafos e, quando necessário, por caracteres.

    Os offsets são relativos ao texto original. A sobreposição preserva contexto
    entre trechos adjacentes. Esta segmentação não avalia relevância científica.
    """
    if tamanho_maximo < 100:
        raise ValueError("tamanho_maximo deve ser pelo menos 100 caracteres.")
    if sobreposicao < 0 or sobreposicao >= tamanho_maximo:
        raise ValueError("sobreposicao deve estar entre zero e tamanho_maximo exclusivo.")
    if limite_trechos is not None and (
        not isinstance(limite_trechos, int) or isinstance(limite_trechos, bool) or limite_trechos < 1
    ):
        raise ValueError("limite_trechos deve ser um inteiro positivo.")

    texto = documento.conteudo
    paragrafos = [
        (match.start(), match.end(), match.group(0))
        for match in re.finditer(r"\S(?:[\s\S]*?\S)?(?=\n\s*\n|\Z)", texto)
    ]
    blocos: list[tuple[int, int]] = []
    atual_inicio: int | None = None
    atual_fim = 0
    for inicio, fim, paragrafo in paragrafos:
        if len(paragrafo) > tamanho_maximo:
            if atual_inicio is not None:
                blocos.append((atual_inicio, atual_fim))
                atual_inicio = None
            cursor = inicio
            while cursor < fim:
                final = min(cursor + tamanho_maximo, fim)
                blocos.append((cursor, final))
                if final == fim:
                    break
                cursor = final - sobreposicao
            continue
        if atual_inicio is None:
            atual_inicio, atual_fim = inicio, fim
        elif fim - atual_inicio <= tamanho_maximo:
            atual_fim = fim
        else:
            blocos.append((atual_inicio, atual_fim))
            inicio_sobreposto = max(atual_inicio, atual_fim - sobreposicao)
            atual_inicio = inicio_sobreposto if inicio_sobreposto < inicio else inicio
            atual_fim = fim
    if atual_inicio is not None:
        blocos.append((atual_inicio, atual_fim))

    blocos_validos = [(inicio, fim) for inicio, fim in blocos if texto[inicio:fim].strip()]
    if limite_trechos is not None and len(blocos_validos) > limite_trechos:
        raise ValueError(f"A segmentação excede o limite de {limite_trechos} trechos.")

    return [
        TrechoConhecimento.a_partir_do_documento(
            documento=documento,
            indice_trecho=indice,
            inicio=inicio,
            fim=fim,
            texto=texto[inicio:fim].strip(),
        )
        for indice, (inicio, fim) in enumerate(blocos_validos)
    ]
