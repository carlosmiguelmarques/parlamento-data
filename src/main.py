"""
Orquestrador do pipeline parlamento-data.

Uso típico (local):
    python -m src.main --cache-max-age-hours 6

Uso em GitHub Actions:
    python -m src.main
"""

from __future__ import annotations

# IMPORTANTE: truststore.inject_into_ssl() tem de ser chamado ANTES de
# qualquer import que use SSL (requests, urllib, etc.). Isto faz com que
# o Python use o trust store do sistema operativo (Keychain no macOS,
# CA bundle do Linux, schannel no Windows) em vez do certifi, o que
# resolve problemas com servidores que enviam cadeias de certificados
# incompletas — incluindo app.parlamento.pt, que omite o certificado
# intermédio na cadeia que envia.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    # truststore é opcional — em ambientes onde o certifi default funciona
    # (ex: Linux com ca-certificates atualizado), o pipeline corre na mesma.
    pass

import argparse
import json
import logging
import sys
from pathlib import Path

from .fetch import FetchError, fetch_all
from .sources import ACTIVE_SOURCES
from .transform import (
    SCHEMA_VERSION,
    escrever_output,
    transformar_composicao,
    transformar_iniciativas,
)

logger = logging.getLogger("parlamento-data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline de dados abertos da AR")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
        help="Pasta onde guardar snapshots descarregados (default: ./cache)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Pasta onde escrever os ficheiros transformados (default: ./output)",
    )
    parser.add_argument(
        "--cache-max-age-hours",
        type=float,
        default=None,
        help=(
            "Se a cache local for mais nova que isto, reutiliza sem descarregar. "
            "Útil em desenvolvimento. Em produção, deixar vazio."
        ),
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Logs mais detalhados"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("A iniciar pipeline (schema v%d)", SCHEMA_VERSION)

    # 1. Descarregar
    try:
        paths = fetch_all(
            ACTIVE_SOURCES,
            cache_dir=args.cache_dir,
            max_age_hours=args.cache_max_age_hours,
        )
    except FetchError as e:
        logger.error("Falha no download: %s", e)
        return 1

    # 2. Carregar para memória
    logger.info("A carregar snapshots para memória...")
    with paths["iniciativas"].open(encoding="utf-8") as f:
        iniciativas_raw = json.load(f)
    with paths["composicao"].open(encoding="utf-8") as f:
        composicao_raw = json.load(f)

    if not isinstance(iniciativas_raw, list):
        logger.error("Snapshot de iniciativas não é uma lista")
        return 1
    if not isinstance(composicao_raw, dict):
        logger.error("Snapshot de composição não é um dict")
        return 1

    logger.info("Iniciativas carregadas: %d", len(iniciativas_raw))

    # 3. Transformar
    logger.info("A transformar iniciativas...")
    iniciativas_t = transformar_iniciativas(iniciativas_raw)
    logger.info("A transformar composição...")
    composicao_t = transformar_composicao(composicao_raw)

    # 4. Escrever
    logger.info("A escrever output para %s...", args.output_dir)
    counts = escrever_output(args.output_dir, iniciativas_t, composicao_t)

    logger.info("Pipeline concluído. Contagens: %s", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
