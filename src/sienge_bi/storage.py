"""Upload de arquivos crus pro Supabase Storage."""
from __future__ import annotations

import datetime
import os
import unicodedata


def _sanitizar_path(path: str) -> str:
    """Remove acentos/cedilhas - Supabase Storage so aceita ASCII no path."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", path)
        if not unicodedata.combining(c)
    ).encode("ascii", "ignore").decode("ascii")


def enviar_para_storage(arquivo_local: str, path_no_bucket: str | None = None,
                         logger=print) -> str | None:
    """Sobe arquivo pro bucket SUPABASE_BUCKET (default 'sienge-raw').

    `path_no_bucket` default: {ano}/{mes}/{dia}/{nome_arquivo}.
    Retorna path final ou None em caso de erro/sem credenciais.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    bucket = os.environ.get("SUPABASE_BUCKET", "sienge-raw")

    if not (supabase_url and supabase_key):
        logger("Supabase nao configurado - pulando upload para storage.")
        return None
    if not os.path.exists(arquivo_local):
        logger(f"Arquivo nao encontrado para upload: {arquivo_local}")
        return None

    try:
        from supabase import create_client
    except ImportError:
        logger("Biblioteca supabase nao instalada - pulando upload.")
        return None

    if path_no_bucket is None:
        hoje = datetime.date.today()
        nome = os.path.basename(arquivo_local)
        path_no_bucket = f"{hoje.year}/{hoje.month:02d}/{hoje.day:02d}/{nome}"

    path_no_bucket = _sanitizar_path(path_no_bucket)

    try:
        client = create_client(supabase_url, supabase_key)
        with open(arquivo_local, "rb") as f:
            client.storage.from_(bucket).upload(
                path=path_no_bucket,
                file=f,
                file_options={"upsert": "true"},
            )
        logger(f"Upload Storage OK: {bucket}/{path_no_bucket}")
        return path_no_bucket
    except Exception as e:
        logger(f"Erro no upload para Supabase Storage: {e}")
        return None
