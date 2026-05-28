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


def purgar_storage_antigos(dias_retencao: int = 5, logger=print) -> int:
    """Deleta arquivos do bucket com path YYYY/MM/DD/... mais antigo que N dias.

    Espera estrutura: `<bucket>/<YYYY>/<MM>/<DD>/<nome_relatorio>/<file>.xlsx`
    (formato usado por enviar_para_storage). Retorna numero de arquivos deletados.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
    bucket = os.environ.get("SUPABASE_BUCKET", "sienge-raw")

    if not (supabase_url and supabase_key):
        return 0

    try:
        from supabase import create_client
    except ImportError:
        return 0

    cutoff = datetime.date.today() - datetime.timedelta(days=dias_retencao)
    client = create_client(supabase_url, supabase_key)
    storage = client.storage.from_(bucket)

    deletados = 0
    try:
        anos = storage.list("")
    except Exception as e:
        logger(f"[purge-storage] falhou listar bucket: {e}")
        return 0

    for ano_entry in anos:
        ano = ano_entry.get("name", "")
        if not ano.isdigit() or len(ano) != 4:
            continue
        try:
            meses = storage.list(ano)
        except Exception:
            continue
        for mes_entry in meses:
            mes = mes_entry.get("name", "")
            if not mes.isdigit() or len(mes) != 2:
                continue
            try:
                dias = storage.list(f"{ano}/{mes}")
            except Exception:
                continue
            for dia_entry in dias:
                dia = dia_entry.get("name", "")
                if not dia.isdigit() or len(dia) != 2:
                    continue
                try:
                    dt = datetime.date(int(ano), int(mes), int(dia))
                except ValueError:
                    continue
                if dt >= cutoff:
                    continue
                # lista subpastas (nome_relatorio) e seus arquivos
                pasta_dia = f"{ano}/{mes}/{dia}"
                paths_para_deletar: list[str] = []
                try:
                    subs = storage.list(pasta_dia)
                    for sub in subs:
                        nome_sub = sub.get("name", "")
                        if not nome_sub:
                            continue
                        try:
                            files = storage.list(f"{pasta_dia}/{nome_sub}")
                            for f in files:
                                fn = f.get("name", "")
                                if fn:
                                    paths_para_deletar.append(f"{pasta_dia}/{nome_sub}/{fn}")
                        except Exception:
                            pass
                except Exception:
                    continue
                if paths_para_deletar:
                    try:
                        storage.remove(paths_para_deletar)
                        deletados += len(paths_para_deletar)
                        logger(f"[purge-storage] {pasta_dia}: -{len(paths_para_deletar)} arquivos")
                    except Exception as e:
                        logger(f"[purge-storage] erro deletando {pasta_dia}: {e}")

    return deletados
