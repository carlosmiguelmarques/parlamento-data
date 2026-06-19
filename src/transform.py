"""
Transforma os snapshots brutos da AR para o nosso schema de API estática.

Recebe os JSON descarregados (iniciativas e composição) e produz uma árvore
de ficheiros que será servida pelo GitHub Pages.

Decisões de design:
- Os tipos primitivos são saneados (CodigoFase de string para int, datas
  "0001-01-01..." para None).
- O detalhe de cada iniciativa mantém-se fiel à AR para não perdermos
  informação que possa ser útil mais tarde.
- O índice tem apenas o necessário para listar/filtrar/ordenar — para
  ficar leve.
- IDs nunca são string nem float. Se a AR der "9008.0", convertemos para 9008.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .categorias import CATEGORIA_LABEL, Categoria, categorizar

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Datas placeholder que a AR usa para "sem data" — convertemos para None.
_DATA_PLACEHOLDERS = {"0001-01-01", "0001-01-01T00:00:00", ""}


# ---------------------------------------------------------------------------
# Utilitários de saneamento
# ---------------------------------------------------------------------------


def _to_int(value: Any) -> int | None:
    """Converte de qualquer forma razoável para int, ou devolve None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            try:
                return int(float(s))
            except ValueError:
                return None
    return None


def _to_date(value: Any) -> str | None:
    """
    Normaliza uma data para ISO `YYYY-MM-DD` ou devolve None.

    A AR mistura formatos: `"2025-06-03"`, `"0001-01-01T00:00:00"`,
    `"19/05/2026"`. Tratamos os principais.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s or s in _DATA_PLACEHOLDERS or s.startswith("0001-01-01"):
        return None
    # Formato ISO com hora: corta no T
    if "T" in s:
        s = s.split("T", 1)[0]
    # Formato dd/mm/yyyy
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
    # Já é YYYY-MM-DD?
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # Desconhecido — preserva mas avisa.
    logger.debug("Formato de data não reconhecido: %r", value)
    return s


def _strip_html(value: Any) -> str | None:
    """Remove tags HTML simples — usado para limpar textos com <I>, <BR>, etc."""
    if not isinstance(value, str):
        return None
    s = re.sub(r"<[^>]+>", " ", value)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


# Parsing do campo `detalhe` das votações.
# A AR serve algo tipo: "A Favor: <I>PSD</I>, <I>CDS-PP</I><BR>Contra: <I>PS</I><BR>..."
_VOTACAO_SEC_RE = re.compile(
    r"(A Favor|Contra|Abstenção|Abstençao|Ausência|Ausencia)\s*:(.*?)(?=(?:A Favor|Contra|Abstenção|Abstençao|Ausência|Ausencia)\s*:|$)",
    re.IGNORECASE | re.DOTALL,
)


def _parse_votacao_detalhe(detalhe: Any) -> dict[str, list[str]] | None:
    """
    Decompõe o detalhe textual de uma votação em listas de partidos.

    Devolve um dict com chaves `aFavor`, `contra`, `abstencao` (listas de
    siglas de partido). Devolve None se não conseguir decompor.
    """
    if not isinstance(detalhe, str) or not detalhe.strip():
        return None
    # Limpar HTML primeiro.
    texto = re.sub(r"<[^>]+>", " ", detalhe)
    texto = re.sub(r"\s+", " ", texto)

    out: dict[str, list[str]] = {"aFavor": [], "contra": [], "abstencao": []}
    matches = _VOTACAO_SEC_RE.findall(texto)
    if not matches:
        return None
    for tipo, partidos in matches:
        siglas = [p.strip() for p in partidos.split(",") if p.strip()]
        tipo_lower = tipo.lower().replace("ç", "c").replace("ê", "e")
        if "favor" in tipo_lower:
            out["aFavor"].extend(siglas)
        elif "contra" in tipo_lower:
            out["contra"].extend(siglas)
        elif "absten" in tipo_lower:
            out["abstencao"].extend(siglas)
        # Ausências ignoramos aqui — já vêm separadas noutro campo.
    return out


# ---------------------------------------------------------------------------
# Transformação de deputados (composicao.json → deputados/...)
# ---------------------------------------------------------------------------


@dataclass
class DeputadoIndex:
    """Resumo de deputado para o índice."""

    id_cadastro: int
    nome_parlamentar: str
    nome_completo: str
    gp_atual: str | None
    circulo: str | None
    situacao_atual: str | None
    ativo: bool


def _transformar_deputado(dep_raw: dict) -> tuple[DeputadoIndex, dict] | None:
    """Transforma uma entrada de Plenário.Composicao num par (resumo, detalhe)."""
    id_cad = _to_int(dep_raw.get("DepCadId"))
    if id_cad is None:
        return None

    nome_parlamentar = (dep_raw.get("DepNomeParlamentar") or "").strip()
    nome_completo = (dep_raw.get("DepNomeCompleto") or "").strip() or nome_parlamentar

    # Histórico de GP — pode ter várias entradas se mudou de partido.
    gps_raw = dep_raw.get("DepGP") or []
    gps = [
        {
            "sigla": (g.get("gpSigla") or "").strip() or None,
            "dataInicio": _to_date(g.get("gpDtInicio")),
            "dataFim": _to_date(g.get("gpDtFim")),
        }
        for g in gps_raw
        if isinstance(g, dict)
    ]
    gp_atual = next((g["sigla"] for g in gps if g["dataFim"] is None), None)
    if gp_atual is None and gps:
        gp_atual = gps[-1]["sigla"]

    # Histórico de situação — última é a atual.
    sits_raw = dep_raw.get("DepSituacao") or []
    sits = [
        {
            "descricao": (s.get("sioDes") or "").strip() or None,
            "dataInicio": _to_date(s.get("sioDtInicio")),
            "dataFim": _to_date(s.get("sioDtFim")),
        }
        for s in sits_raw
        if isinstance(s, dict)
    ]
    sit_atual = sits[-1]["descricao"] if sits else None
    # "Ativo" para nós significa atualmente a exercer mandato como efetivo.
    ativo = sit_atual in {"Efetivo", "Efetivo Temporário", "Efetivo Definitivo"}

    circulo = (dep_raw.get("DepCPDes") or "").strip() or None

    # DepCargo vem como lista de cargos exercidos (com datas) ou None.
    cargos_raw = dep_raw.get("DepCargo") or []
    if not isinstance(cargos_raw, list):
        cargos_raw = []
    cargos = [
        {
            "descricao": (c.get("carDes") or "").strip() or None,
            "dataInicio": _to_date(c.get("carDtInicio")),
            "dataFim": _to_date(c.get("carDtFim")),
        }
        for c in cargos_raw
        if isinstance(c, dict)
    ]
    cargo_atual = next(
        (c["descricao"] for c in cargos if c["dataFim"] is None and c["descricao"]),
        None,
    )

    resumo = DeputadoIndex(
        id_cadastro=id_cad,
        nome_parlamentar=nome_parlamentar,
        nome_completo=nome_completo,
        gp_atual=gp_atual,
        circulo=circulo,
        situacao_atual=sit_atual,
        ativo=ativo,
    )

    detalhe = {
        "idCadastro": id_cad,
        "nomeParlamentar": nome_parlamentar,
        "nomeCompleto": nome_completo,
        "gpAtual": gp_atual,
        "gpsHistorico": gps,
        "situacaoAtual": sit_atual,
        "situacoesHistorico": sits,
        "circulo": circulo,
        "cargoAtual": cargo_atual,
        "cargosHistorico": cargos,
        "ativo": ativo,
        "legislatura": (dep_raw.get("LegDes") or "").strip() or None,
    }
    return resumo, detalhe


def transformar_composicao(composicao_raw: dict) -> dict[str, Any]:
    """
    Transforma o snapshot de composição.

    Devolve um dict com:
      - 'deputados_index': lista de resumos
      - 'deputados_detalhe': dict {id_cadastro: detalhe}
      - 'gps_index': lista de GPs com contagem de efetivos
      - 'comissoes_index': lista de comissões resumidas
      - 'comissoes_detalhe': dict {orgId: detalhe}
    """
    plenario = composicao_raw.get("Plenario") or {}
    composicao = plenario.get("Composicao") or []

    # Deduplicar por idCadastro — a Composicao pode ter várias entradas
    # para o mesmo deputado se ele teve múltiplos mandatos. Para a v1
    # ficamos com a entrada mais "ativa" (preferimos Efetivo).
    by_id: dict[int, tuple[DeputadoIndex, dict]] = {}
    for dep_raw in composicao:
        result = _transformar_deputado(dep_raw)
        if result is None:
            continue
        resumo, detalhe = result
        existing = by_id.get(resumo.id_cadastro)
        if existing is None:
            by_id[resumo.id_cadastro] = (resumo, detalhe)
            continue
        # Manter o mais "preferível": ativo > não-ativo.
        if resumo.ativo and not existing[0].ativo:
            by_id[resumo.id_cadastro] = (resumo, detalhe)

    deputados_index = [
        {
            "idCadastro": r.id_cadastro,
            "nomeParlamentar": r.nome_parlamentar,
            "nomeCompleto": r.nome_completo,
            "gpAtual": r.gp_atual,
            "circulo": r.circulo,
            "situacaoAtual": r.situacao_atual,
            "ativo": r.ativo,
        }
        for r, _ in sorted(by_id.values(), key=lambda x: x[0].nome_parlamentar.lower())
    ]
    deputados_detalhe = {str(r.id_cadastro): d for r, d in by_id.values()}

    # GPs — agregar a partir dos deputados ativos.
    contagem_gp: Counter[str] = Counter()
    for r, _ in by_id.values():
        if r.ativo and r.gp_atual:
            contagem_gp[r.gp_atual] += 1
    gps_index = [
        {"sigla": sigla, "deputadosEfetivos": n}
        for sigla, n in contagem_gp.most_common()
    ]

    # Comissões — transformação simples por agora.
    comissoes_raw = composicao_raw.get("Comissoes") or []
    comissoes_index: list[dict] = []
    comissoes_detalhe: dict[str, dict] = {}
    for c in comissoes_raw:
        det = c.get("DetalheOrgao") or {}
        org_id = _to_int(det.get("idOrgao"))
        if org_id is None:
            continue
        resumo = {
            "idOrgao": org_id,
            "sigla": (det.get("OrgSigla") or det.get("siglaOrgao") or "").strip()
            or None,
            "nome": (det.get("OrgDes") or det.get("nomeSigla") or "").strip() or None,
        }
        comissoes_index.append(resumo)
        comissoes_detalhe[str(org_id)] = {
            **resumo,
            "membros": c.get("HistoricoComposicao") or [],
        }

    return {
        "deputados_index": deputados_index,
        "deputados_detalhe": deputados_detalhe,
        "gps_index": gps_index,
        "comissoes_index": comissoes_index,
        "comissoes_detalhe": comissoes_detalhe,
    }


# ---------------------------------------------------------------------------
# Transformação de iniciativas
# ---------------------------------------------------------------------------


def _ultima_data_evento(eventos: list[dict]) -> str | None:
    """Devolve a data mais recente entre os eventos."""
    datas = [e.get("dataFase") for e in eventos if e.get("dataFase")]
    return max(datas) if datas else None


def _transformar_evento(ev_raw: dict) -> dict:
    """Transforma um IniEvento sanando tipos e parseando votações."""
    cod = _to_int(ev_raw.get("CodigoFase"))
    cat = categorizar(cod)

    # Votações vêm como lista — pode haver múltiplas (generalidade,
    # especialidade, etc.). Parseamos o detalhe HTML para algo estruturado
    # mas guardamos o original para debug.
    votacoes_raw = ev_raw.get("Votacao") or []
    votacoes: list[dict] = []
    for v in votacoes_raw:
        if not isinstance(v, dict):
            continue
        votacoes.append(
            {
                "id": _to_int(v.get("id")),
                "resultado": v.get("resultado"),
                "unanime": v.get("unanime"),
                "data": _to_date(v.get("data")),
                "detalheOriginal": v.get("detalhe"),
                "detalhe": _parse_votacao_detalhe(v.get("detalhe")),
                "ausencias": v.get("ausencias"),
                "reuniao": v.get("reuniao"),
            }
        )

    return {
        "evtId": _to_int(ev_raw.get("EvtId")),
        "oevId": _to_int(ev_raw.get("OevId")),
        "codigoFase": cod,
        "fase": ev_raw.get("Fase"),
        "categoria": cat.value,
        "categoriaLabel": CATEGORIA_LABEL[cat],
        "dataFase": _to_date(ev_raw.get("DataFase")),
        "comissao": ev_raw.get("Comissao"),
        "votacoes": votacoes,
        "publicacaoFase": ev_raw.get("PublicacaoFase"),
        "intervencoes": ev_raw.get("Intervencoesdebates"),
        "anexosFase": ev_raw.get("AnexosFase"),
        "textosAprovados": ev_raw.get("TextosAprovados"),
        "iniciativasConjuntas": ev_raw.get("IniciativasConjuntas"),
        "peticoesConjuntas": ev_raw.get("PeticoesConjuntas"),
    }


def _autores_resumo(ini_raw: dict) -> dict:
    """Extrai um resumo dos autores para o índice (3 listas: GP, deputados, outros)."""
    gps_raw = ini_raw.get("IniAutorGruposParlamentares") or []
    gps = [g.get("GP") for g in gps_raw if isinstance(g, dict) and g.get("GP")]

    deps_raw = ini_raw.get("IniAutorDeputados") or []
    deps = [
        _to_int(d.get("idCadastro"))
        for d in deps_raw
        if isinstance(d, dict) and d.get("idCadastro") is not None
    ]
    deps = [d for d in deps if d is not None]

    outros = ini_raw.get("IniAutorOutros")
    outros_sigla = None
    outros_nome = None
    if isinstance(outros, dict):
        outros_sigla = outros.get("sigla")
        outros_nome = outros.get("nome")

    return {
        "gp": gps,
        "deputados": deps,
        "outroSigla": outros_sigla,
        "outroNome": outros_nome,
    }


def _transformar_iniciativa(ini_raw: dict) -> tuple[dict, dict]:
    """Devolve (resumo_para_index, detalhe_completo)."""
    ini_id = _to_int(ini_raw.get("IniId"))
    ini_nr = ini_raw.get("IniNr")  # pode ter sufixos, mantemos string
    ini_leg = ini_raw.get("IniLeg")
    ini_tipo = ini_raw.get("IniTipo")
    ini_tipo_desc = ini_raw.get("IniDescTipo")
    ini_titulo = ini_raw.get("IniTitulo") or ""

    # Eventos transformados, ordenados por data crescente.
    eventos_raw = ini_raw.get("IniEventos") or []
    eventos = [_transformar_evento(e) for e in eventos_raw]
    eventos.sort(key=lambda e: e.get("dataFase") or "")

    data_ultimo = _ultima_data_evento(eventos)
    data_inicio = _to_date(ini_raw.get("DataInicioleg"))

    # Estado atual = categoria do último evento.
    estado: dict[str, Any]
    if eventos:
        ultimo = eventos[-1]
        estado = {
            "codigoFase": ultimo["codigoFase"],
            "fase": ultimo["fase"],
            "categoria": ultimo["categoria"],
            "categoriaLabel": ultimo["categoriaLabel"],
            "dataFase": ultimo["dataFase"],
        }
    else:
        estado = {
            "codigoFase": None,
            "fase": None,
            "categoria": Categoria.ENTRADA.value,
            "categoriaLabel": CATEGORIA_LABEL[Categoria.ENTRADA],
            "dataFase": None,
        }

    # Flag conveniente: tornou-se lei?
    tornou_se_lei = any(e.get("categoria") == Categoria.PUBLICADA.value for e in eventos)

    autores = _autores_resumo(ini_raw)

    resumo = {
        "id": ini_id,
        "numero": ini_nr,
        "legislatura": ini_leg,
        "tipo": ini_tipo,
        "tipoDesc": ini_tipo_desc,
        "titulo": ini_titulo,
        "dataInicio": data_inicio,
        "dataUltimoEvento": data_ultimo,
        "estado": estado,
        "autoresGP": autores["gp"],
        "autoresDeputados": autores["deputados"],
        "autorOutroSigla": autores["outroSigla"],
        "autorOutroNome": autores["outroNome"],
        "tornouSeLei": tornou_se_lei,
    }

    detalhe = {
        **resumo,
        "linkTexto": ini_raw.get("IniLinkTexto"),
        "textoSubstituido": ini_raw.get("IniTextoSubst") == "SIM",
        "textoSubstituidoNota": ini_raw.get("IniTextoSubstCampo"),
        "epigrafe": ini_raw.get("IniEpigrafe"),
        "observacoes": ini_raw.get("IniObs"),
        "autoresDeputadosDetalhe": ini_raw.get("IniAutorDeputados") or [],
        "anexos": ini_raw.get("IniAnexos") or [],
        "eventos": eventos,
        "links": ini_raw.get("Links"),
        "peticoes": ini_raw.get("Peticoes"),
        "propostasAlteracao": ini_raw.get("PropostasAlteracao"),
        "iniciativasOrigem": ini_raw.get("IniciativasOrigem"),
        "iniciativasOriginadas": ini_raw.get("IniciativasOriginadas"),
        "iniciativasEuropeias": ini_raw.get("IniciativasEuropeias"),
    }
    return resumo, detalhe


def transformar_iniciativas(iniciativas_raw: list[dict]) -> dict[str, Any]:
    """
    Transforma a lista de iniciativas.

    Devolve um dict com:
      - 'index': lista de resumos
      - 'detalhe': dict {ini_id: detalhe_completo}
    """
    index: list[dict] = []
    detalhe: dict[str, dict] = {}
    descartadas = 0

    for ini_raw in iniciativas_raw:
        resumo, det = _transformar_iniciativa(ini_raw)
        if resumo["id"] is None:
            descartadas += 1
            continue
        index.append(resumo)
        detalhe[str(resumo["id"])] = det

    if descartadas:
        logger.warning("%d iniciativas descartadas (sem IniId)", descartadas)

    # Ordenar o índice por data do último evento descendente (mais recentes
    # primeiro). Iniciativas sem data ficam no fim.
    index.sort(
        key=lambda i: (i.get("dataUltimoEvento") or "0000-00-00"),
        reverse=True,
    )

    return {"index": index, "detalhe": detalhe}


# ---------------------------------------------------------------------------
# Escrita da árvore de output
# ---------------------------------------------------------------------------


def escrever_output(
    output_dir: Path,
    iniciativas_transformadas: dict[str, Any],
    composicao_transformada: dict[str, Any],
) -> dict[str, int]:
    """
    Escreve toda a árvore de ficheiros de saída em `output_dir`.

    Devolve um dict de contagens por categoria de ficheiros, útil para logs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    # Iniciativas
    ini_dir = output_dir / "iniciativas"
    ini_dir.mkdir(exist_ok=True)
    _write_json(
        ini_dir / "index.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "iniciativas": iniciativas_transformadas["index"],
        },
    )
    for ini_id, detalhe in iniciativas_transformadas["detalhe"].items():
        _write_json(ini_dir / f"{ini_id}.json", detalhe)
    counts["iniciativas"] = len(iniciativas_transformadas["detalhe"])

    # Deputados
    dep_dir = output_dir / "deputados"
    dep_dir.mkdir(exist_ok=True)
    _write_json(
        dep_dir / "index.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "deputados": composicao_transformada["deputados_index"],
        },
    )
    for dep_id, detalhe in composicao_transformada["deputados_detalhe"].items():
        _write_json(dep_dir / f"{dep_id}.json", detalhe)
    counts["deputados"] = len(composicao_transformada["deputados_detalhe"])

    # Grupos parlamentares
    gp_dir = output_dir / "grupos-parlamentares"
    gp_dir.mkdir(exist_ok=True)
    _write_json(
        gp_dir / "index.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "gruposParlamentares": composicao_transformada["gps_index"],
        },
    )
    counts["grupos_parlamentares"] = len(composicao_transformada["gps_index"])

    # Comissões
    com_dir = output_dir / "comissoes"
    com_dir.mkdir(exist_ok=True)
    _write_json(
        com_dir / "index.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "comissoes": composicao_transformada["comissoes_index"],
        },
    )
    for org_id, detalhe in composicao_transformada["comissoes_detalhe"].items():
        _write_json(com_dir / f"{org_id}.json", detalhe)
    counts["comissoes"] = len(composicao_transformada["comissoes_detalhe"])

    # Meta no topo
    _write_json(
        output_dir / "meta.json",
        {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "counts": counts,
            "legislatura": "XVII",
        },
    )

    return counts


def _write_json(path: Path, payload: Any) -> None:
    """Escreve JSON compacto (sem indentação) para reduzir tamanho dos ficheiros."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
