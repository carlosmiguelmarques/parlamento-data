"""
Fontes de dados abertos da Assembleia da República.

Cada entrada representa um snapshot publicado pela AR em
https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx

Os URLs têm tokens encriptados no parâmetro `path` que apontam para a pasta
no servidor da AR. Estes tokens parecem ser estáveis por dataset (não rodam
por sessão), pelo que podemos hardcodá-los. Se algum URL deixar de funcionar,
basta ir à página dos dados abertos, copiar o novo URL e atualizar aqui.

Os ficheiros têm extensão `.txt` no servidor da AR mas conteúdo JSON.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """Representa uma fonte de dados da AR."""

    key: str  # identificador interno
    url: str  # URL completo no servidor da AR
    filename: str  # nome para guardar localmente (sem caminho)
    description: str


# v1 — apenas iniciativas e composição.
# Atividades, agenda e atividades-deputados ficam para v2.

INICIATIVAS = Source(
    key="iniciativas",
    url=(
        "https://app.parlamento.pt/webutils/docs/doc.txt"
        "?path=QiMgdroKsZ9e5NkiVltwPj43gE4xdkGXkmFXwzDo%2fxbG0RFAx2kCQkfI%2bW33lrim"
        "tk%2bntPkMiljsTRsXNhsEAtMoNUB4akeuu2w1tbVAtqYF4Gun%2fSqI1it6iKx6xBqzpuln"
        "VDRW%2fFkFyyRH%2f3ZmN4%2fcH%2f5jdKSCpRWZ%2fpKbCEWzrK6O3Hzc34FAWGSkhoQG5"
        "qRrlm914JkQIiU1%2baHV%2fWrbpB5%2fZiQCsnAQsXa9btP23qPL8HGO%2fp5TK6Cf36DE"
        "a6VGHwbAUPSRx4hGsWz6K9xO9yiI6eKWQ2%2fRUnf9G13wOAKwXkTIuX5fGz4Jlcxbt92tx"
        "kbW4PhFXD3aDiCPu38mXjAp6TAwxAQC8F%2b1vFE3ja8r7WzFKeKWYBMAsT69"
        "&fich=IniciativasXVII_json.txt&Inline=true"
    ),
    filename="iniciativas.json",
    description="Iniciativas legislativas da XVII Legislatura",
)

COMPOSICAO = Source(
    key="composicao",
    url=(
        "https://app.parlamento.pt/webutils/docs/doc.txt"
        "?path=wzhc%2bQYG1MnVDwzMq8hILKGc1EonocLTEos7x2EwrlEk7Jle5rQnr%2b2cROwePOg"
        "MyrLpniDZtC2VAikIgXkbNn9%2bSPasHZy9nAWgt4Jh%2b%2f8GbXGLi5gq6%2bRLaLc4Mgkkqu"
        "IqzwOPLbmBHVHv6KjErnrPx%2fcxY3XlvPREvuiqFgZukzlfNO2BIPbQeKxQPgPmpWXg2hS2Q"
        "4doTuyXQszUp%2fD56dKwqxDI5nKHNKMCEhmRpiev5qurbPmFw8tk%2b5VSPc5hAufGp256Gk"
        "Np5j88COH3X6LAl4BPx1YTPisn350c4lgYOz52UYofjs0EiU7Yv3TeBiLcAd2h%2fAR8c42tw"
        "lNpxc7aXwE%2fM0TWU5Cbplfl8XlEl2moNtUYYOmyDOocFFWBqLNZiwkUy%2fkYBsSEGIF1to"
        "i9jRMV7uFmg7gPMiVDw2TP2EJx16t0AbY64JKF"
        "&fich=OrgaoComposicaoXVII_json.txt&Inline=true"
    ),
    filename="composicao.json",
    description="Composição dos órgãos parlamentares (Plenário, Comissões, etc.)",
)


# Sources em uso na v1.
ACTIVE_SOURCES: tuple[Source, ...] = (INICIATIVAS, COMPOSICAO)


# Reservado para v2 — guardado aqui para referência futura.
# AGENDA = Source(...)
# ATIVIDADES = Source(...)
# ATIVIDADES_DEPUTADOS = Source(...)
