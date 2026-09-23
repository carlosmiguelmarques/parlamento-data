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
import time
from pathlib import Path

import requests

from .sources import Source

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """Erro ao descarregar ou validar um snapshot."""


_RETRY_DELAYS = (30, 60, 120)  # segundos entre tentativas (3 retries)


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

    Faz até 3 retries com backoff (30s, 60s, 120s) para lidar com
    indisponibilidade transitória do servidor da AR durante atualizações.

    Devolve o caminho do ficheiro local. Levanta FetchError em caso de
    falha persistente (HTTP error, JSON inválido, ficheiro vazio).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / source.filename

    if max_age_hours is not None and target.exists():
        age_hours = (time.time() - target.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            logger.info(
                "A usar cache local de '%s' (idade %.1fh < %.1fh)",
                source.key,
                age_hours,
                max_age_hours,
            )
            return target

    last_error: FetchError | None = None
    attempts = 1 + len(_RETRY_DELAYS)

    for attempt in range(attempts):
        if attempt > 0:
            delay = _RETRY_DELAYS[attempt - 1]
            logger.warning(
                "'%s' tentativa %d/%d falhou — a aguardar %ds antes de repetir.",
                source.key, attempt, attempts, delay,
            )
            time.sleep(delay)

        logger.info(
            "A descarregar '%s' (tentativa %d/%d) de %s",
            source.key, attempt + 1, attempts, source.url[:80] + "...",
        )
        try:
            content = _download(source, timeout_seconds)
        except FetchError as e:
            last_error = e
            continue

        target.write_bytes(content)
        size_mb = len(content) / (1024 * 1024)
        logger.info("'%s' guardado em %s (%.1f MB)", source.key, target, size_mb)
        return target

    raise last_error  # type: ignore[misc]


def _download(source: Source, timeout_seconds: int) -> bytes:
    """Faz um único pedido HTTP e valida que o conteúdo é JSON. Levanta FetchError."""
    try:
        response = requests.get(
            source.url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "Mozilla/5.0 (parlamento-data; +https://github.com/)",
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
    # HTML servidas com status 200, que já vi acontecer neste servidor.
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        preview = content[:200].decode("utf-8", errors="replace")
        raise FetchError(
            f"Snapshot de '{source.key}' não é JSON válido. "
            f"Início da resposta: {preview!r}"
        ) from e

    return content


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
