"""
Mapeamento entre os 65 códigos de fase observados no campo `CodigoFase` dos
eventos de uma iniciativa e categorias agregadas mais úteis para a UI.

Os códigos vêm da AR como strings (e.g. "10", "580"). Convertemos para int
no transform e usamos este mapa para classificar o estado da iniciativa.

A categoria de uma iniciativa é a categoria do seu evento *mais recente*
(ordenado por DataFase descendente). Isto significa que se uma iniciativa
foi vetada e depois reapreciada e aprovada, o estado fica "publicada_lei",
não "vetada".

Para a v1, escolhemos 8 categorias que cobrem os casos relevantes para a app.
Podem ser refinadas em versões futuras sem alterar a estrutura da API.
"""

from __future__ import annotations

from enum import Enum


class Categoria(str, Enum):
    """Categorias de estado de uma iniciativa, ordenadas pelo fluxo típico."""

    ENTRADA = "entrada"
    EM_APRECIACAO = "em_apreciacao"  # comissões, audições, especialidade
    VOTACAO_GENERALIDADE = "votacao_generalidade"
    APROVADA_GENERALIDADE = "aprovada_generalidade"
    VOTACAO_FINAL = "votacao_final"
    APROVADA = "aprovada"  # decreto da AR, antes da promulgação
    VETADA = "vetada"
    PUBLICADA = "publicada"  # lei publicada no DR
    RETIRADA = "retirada"
    REJEITADA = "rejeitada"
    CADUCADA = "caducada"
    OUTRO = "outro"


# Mapeamento código de fase → categoria.
# Os códigos foram extraídos do dataset de iniciativas da XVII Legislatura
# (1566 iniciativas, 65 códigos distintos observados).
#
# Onde não temos certeza sobre o significado de um código, mapeamos para OUTRO
# e refinamos quando aparecerem casos reais.

_FASE_PARA_CATEGORIA: dict[int, Categoria] = {
    # Entrada e admissão
    10: Categoria.ENTRADA,  # Entrada
    20: Categoria.ENTRADA,  # Admissão
    21: Categoria.ENTRADA,  # Anúncio
    30: Categoria.REJEITADA,  # Não admissão
    50: Categoria.EM_APRECIACAO,  # Publicação
    55: Categoria.EM_APRECIACAO,  # Publicação em Separata
    22: Categoria.EM_APRECIACAO,  # Audição promovida pelo PAR
    # Distribuição e apreciação em comissão
    150: Categoria.EM_APRECIACAO,  # Recurso da não admissão
    160: Categoria.EM_APRECIACAO,  # Decisão sobre recurso
    172: Categoria.EM_APRECIACAO,  # Parecer da ALRAA
    173: Categoria.EM_APRECIACAO,  # Parecer da ALRAM
    174: Categoria.EM_APRECIACAO,  # Parecer do Governo da RAA
    180: Categoria.EM_APRECIACAO,  # Baixa à comissão (generalidade)
    181: Categoria.EM_APRECIACAO,  # Baixa à comissão para discussão
    190: Categoria.EM_APRECIACAO,  # Discussão na generalidade
    200: Categoria.EM_APRECIACAO,  # Discussão na especialidade em comissão
    210: Categoria.EM_APRECIACAO,  # Audições / pareceres
    220: Categoria.EM_APRECIACAO,  # Discussão pública
    225: Categoria.EM_APRECIACAO,  # Requerimento
    230: Categoria.EM_APRECIACAO,  # Apreciação pública
    240: Categoria.EM_APRECIACAO,  # Relatório / parecer
    243: Categoria.EM_APRECIACAO,  # Apreciação
    245: Categoria.EM_APRECIACAO,  # Nova baixa comissão para discussão
    # Votação na generalidade
    250: Categoria.VOTACAO_GENERALIDADE,  # Votação na generalidade
    260: Categoria.APROVADA_GENERALIDADE,  # Aprovação na generalidade
    # Especialidade
    270: Categoria.EM_APRECIACAO,  # Baixa à comissão (especialidade)
    280: Categoria.EM_APRECIACAO,  # Propostas de alteração
    290: Categoria.EM_APRECIACAO,  # Apreciação na especialidade
    300: Categoria.EM_APRECIACAO,  # Discussão na especialidade
    310: Categoria.EM_APRECIACAO,  # Votação na especialidade
    # Votação final
    320: Categoria.VOTACAO_FINAL,  # Votação final global
    330: Categoria.VOTACAO_FINAL,  # Votação global
    335: Categoria.VOTACAO_FINAL,  # Votação Deliberação
    340: Categoria.APROVADA,  # Redação final
    348: Categoria.APROVADA,  # Envio para promulgação (texto)
    350: Categoria.APROVADA,  # Decreto da AR
    360: Categoria.PUBLICADA,  # Resolução (Publicação DAR)
    365: Categoria.PUBLICADA,  # Deliberação (Publicação DAR)
    # Promulgação
    370: Categoria.APROVADA,  # Envio ao PR
    371: Categoria.APROVADA,  # Envio para Ratificação / Assinatura
    380: Categoria.APROVADA,  # Promulgação
    390: Categoria.APROVADA,  # Referenda governamental
    400: Categoria.APROVADA,  # Envio para publicação
    # Veto
    409: Categoria.VETADA,  # Veto presidencial recebido
    410: Categoria.VETADA,  # Veto
    411: Categoria.VETADA,
    412: Categoria.VETADA,
    413: Categoria.VETADA,
    414: Categoria.VETADA,
    415: Categoria.VETADA,  # Reenvio para promulgação após confirmação
    441: Categoria.EM_APRECIACAO,  # Reapreciação após veto
    # Publicação
    580: Categoria.PUBLICADA,  # Lei publicada
    600: Categoria.PUBLICADA,  # Resolução publicada
    603: Categoria.EM_APRECIACAO,  # Constituição de Comissão de Inquérito
    # Terminação antecipada
    648: Categoria.RETIRADA,  # Retirada pelo autor
    650: Categoria.CADUCADA,
    660: Categoria.CADUCADA,
}


# Etiquetas legíveis para mostrar na UI (também úteis no script).
CATEGORIA_LABEL: dict[Categoria, str] = {
    Categoria.ENTRADA: "Entrada",
    Categoria.EM_APRECIACAO: "Em apreciação",
    Categoria.VOTACAO_GENERALIDADE: "Em votação (generalidade)",
    Categoria.APROVADA_GENERALIDADE: "Aprovada na generalidade",
    Categoria.VOTACAO_FINAL: "Em votação final",
    Categoria.APROVADA: "Aprovada",
    Categoria.VETADA: "Vetada",
    Categoria.PUBLICADA: "Publicada",
    Categoria.RETIRADA: "Retirada",
    Categoria.REJEITADA: "Rejeitada",
    Categoria.CADUCADA: "Caducada",
    Categoria.OUTRO: "Outro",
}


def categorizar(codigo_fase: int | None) -> Categoria:
    """Devolve a categoria correspondente a um código de fase."""
    if codigo_fase is None:
        return Categoria.OUTRO
    return _FASE_PARA_CATEGORIA.get(codigo_fase, Categoria.OUTRO)
