"""
Descarrega os snapshots da AR para uma pasta de cache local.

A AR não publica ETags úteis nem Last-Modified fiáveis nos ficheiros de
dados abertos, pelo que o controlo de "está fresco?" é feito por idade do
ficheiro local. Para correr o script em GitHub Actions, a cache não persiste
entre execuções, pelo que descarrega sempre.

Para desenvolvimento local, podemos passar `max_age_hours` para evitar
descarregar a mesma coisa várias vezes seguidas.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from time import time

import requests

from .sources import Source

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Erro ao descarregar ou validar um snapshot."""


def fetch_source(
    source: Source,
    cache_dir: Path,
    max_age_hours: float | None = None,
    timeout_seconds: int = 120,
) -> Path:
    """
    Descarrega o ficheiro de `source` para `cache_dir/{filename}`.

    Se já existir um ficheiro válido em cache com idade inferior a
    `max_age_hours`, devolve-o sem fazer download.

    Devolve o caminho do ficheiro local. Levanta FetchError em caso de
    falha (HTTP error, JSON inválido, ficheiro vazio).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / source.filename

    if max_age_hours is not None and target.exists():
        age_hours = (time() - target.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            logger.info(
                "A usar cache local de '%s' (idade %.1fh < %.1fh)",
                source.key,
                age_hours,
                max_age_hours,
            )
            return target

    logger.info("A descarregar '%s' de %s", source.key, source.url[:80] + "...")
    try:
        response = requests.get(
            source.url,
            timeout=timeout_seconds,
            headers={
                # User-Agent realista evita possíveis bloqueios anti-bot.
                "User-Agent": (
                    "Mozilla/5.0 (parlamento-data; +https://github.com/)"
                ),
                "Accept-Encoding": "gzip, br",
            },
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise FetchError(f"Falha HTTP ao descarregar '{source.key}': {e}") from e

    content = response.content
    if not content:
        raise FetchError(f"Snapshot de '{source.key}' veio vazio")

    # Validar que é JSON antes de gravar — protege contra páginas de erro
    # HTML servidas com status 200, que já vi acontecer noutros serviços.
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        # Guardar o conteúdo para diagnóstico, mas falhar a operação.
        broken = cache_dir / f"{source.filename}.broken"
        broken.write_bytes(content[:5000])
        raise FetchError(
            f"Snapshot de '{source.key}' não é JSON válido "
            f"(primeiros 5KB em {broken})"
        ) from e

    target.write_bytes(content)
    size_mb = len(content) / (1024 * 1024)
    logger.info("'%s' guardado em %s (%.1f MB)", source.key, target, size_mb)
    return target


def fetch_all(
    sources: tuple[Source, ...],
    cache_dir: Path,
    max_age_hours: float | None = None,
) -> dict[str, Path]:
    """Descarrega todas as fontes e devolve um dict {key: caminho_local}."""
    results: dict[str, Path] = {}
    for source in sources:
        results[source.key] = fetch_source(source, cache_dir, max_age_hours)
    return results
