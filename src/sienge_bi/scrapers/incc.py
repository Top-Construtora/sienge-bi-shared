"""Scraper do INCC (Indice Nacional de Custo da Construcao).

Fonte: Secovi-SP, que republica os dados oficiais da FGV.
URL: https://indiceseconomicos.secovi.com.br/indicadormensal.php?idindicador=59

Estrutura da pagina:
    Cada ano tem um <div id="p20"> ... <div id="p32"> (e por ai vai).
    Dentro de cada div, ha uma <table class="relatorioTabela">
    com colunas: Mes | INCC % | Indice (e mais 2-3 colunas).

Comportamento idempotente: upsert em sienge.dim_incc.
"""
import datetime
import logging
import re
import sys
import urllib.request
import ssl
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from ..db import get_engine

_log = logging.getLogger(__name__)


def adicionar_ao_log(msg: str) -> None:
    """Log + print (mantem compatibilidade com codigo legado)."""
    _log.info(msg)
    print(msg)


URL_SECOVI = "https://indiceseconomicos.secovi.com.br/indicadormensal.php?idindicador=59"

MESES_PT = {
    # Abreviacoes (formato usado pelo Secovi)
    'JAN': 1, 'FEV': 2, 'MAR': 3, 'ABR': 4, 'MAI': 5, 'JUN': 6,
    'JUL': 7, 'AGO': 8, 'SET': 9, 'OUT': 10, 'NOV': 11, 'DEZ': 12,
    # Por extenso (defensivo)
    'JANEIRO': 1, 'FEVEREIRO': 2, 'MARCO': 3, 'MARÇO': 3, 'ABRIL': 4,
    'MAIO': 5, 'JUNHO': 6, 'JULHO': 7, 'AGOSTO': 8, 'SETEMBRO': 9,
    'OUTUBRO': 10, 'NOVEMBRO': 11, 'DEZEMBRO': 12,
}


def _baixar_html(url: str = URL_SECOVI) -> str:
    """Faz GET no Secovi e retorna o HTML."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extrair_ano_da_secao(secao_html: str) -> int | None:
    """Procura 'Ano: 2024' no cabecalho da secao."""
    m = re.search(r"Ano:\s*(20\d{2})", secao_html)
    if m:
        return int(m.group(1))
    return None


def _parse_numero_br(s: str) -> float | None:
    """Converte string 'pt-BR' (1.234,567) para float."""
    if not s or not s.strip() or s.strip() in ("-", "—"):
        return None
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_secao(secao_html: str, ano: int) -> list[dict]:
    """Extrai linhas (mes, indice, variacao) de uma secao HTML.

    Estrutura real do Secovi (cada ano):
      Tabela 1: navegacao de anos (ignorar)
      Tabela 2: dados | colunas = Mes | Indice | Var% Mes | Acum.Ano% | Acum.12m%
    """
    # Pega TODAS as tabelas relatorioTabela e usa a com mais linhas (a de dados)
    tabelas = re.findall(
        r'<table[^>]*class="[^"]*relatorioTabela[^"]*"[^>]*>(.*?)</table>',
        secao_html, re.DOTALL | re.IGNORECASE,
    )
    if not tabelas:
        return []
    # A tabela de dados tem >= 12 linhas (1 header + 12 meses)
    tabelas.sort(key=lambda t: len(re.findall(r"<tr", t, re.IGNORECASE)), reverse=True)
    tabela = tabelas[0]

    linhas_out = []
    for tr in re.finditer(r"<tr[^>]*>(.*?)</tr>", tabela, re.DOTALL | re.IGNORECASE):
        celulas = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr.group(1), re.DOTALL | re.IGNORECASE)
        celulas = [re.sub(r"<[^>]+>", "", c).strip() for c in celulas]
        celulas = [re.sub(r"\s+", " ", c).strip() for c in celulas]
        if not celulas:
            continue
        # Primeira celula deve ser mes - tenta achar nos primeiros 2 itens
        mes_num = None
        for cel in celulas[:2]:
            cel_clean = re.sub(r"[^A-ZÇÃÁÉÍÓÚÊÔÂ]", "", cel.upper())
            if cel_clean in MESES_PT:
                mes_num = MESES_PT[cel_clean]
                break
        if not mes_num:
            continue
        # Indice = primeiro numero > 100 nas demais celulas
        # Variacao = primeiro numero com '%' ou pequeno (< 50) nas demais celulas
        indice = None
        variacao = None
        for cel in celulas:
            v = _parse_numero_br(cel.replace("%", ""))
            if v is None:
                continue
            if v > 100 and indice is None:
                indice = v
            elif v < 50 and variacao is None and "%" in cel:
                variacao = v
        if indice is None:
            continue
        linhas_out.append({
            "data": datetime.date(ano, mes_num, 1),
            "indice": indice,
            "variacao": variacao,
        })
    return linhas_out


def coletar_indices(url: str = URL_SECOVI) -> pd.DataFrame:
    """Faz scraping e retorna DataFrame com (data, indice, variacao)."""
    adicionar_ao_log(f"Baixando HTML do Secovi: {url}")
    html = _baixar_html(url)
    adicionar_ao_log(f"HTML recebido: {len(html)} bytes")

    # Encontra todas as secoes <div id='pN'> ... </div> que tem tabela INCC
    todas = []
    for m in re.finditer(
        r'<div[^>]*id=["\']p(\d+)["\'][^>]*>(.*?)(?=<div[^>]*id=["\']p\d+["\']|</body>)',
        html, re.DOTALL | re.IGNORECASE,
    ):
        secao_id = int(m.group(1))
        secao_html = m.group(2)
        if "relatorioTabela" not in secao_html:
            continue
        ano = _extrair_ano_da_secao(secao_html)
        if not ano:
            continue
        linhas = _parse_secao(secao_html, ano)
        if linhas:
            todas.extend(linhas)
            adicionar_ao_log(f"  ano {ano} (div p{secao_id}): {len(linhas)} linhas")

    if not todas:
        adicionar_ao_log("ATENCAO: nenhuma linha extraida do HTML.")
        return pd.DataFrame(columns=["data", "indice", "variacao"])
    df = pd.DataFrame(todas).drop_duplicates(subset=["data"]).sort_values("data").reset_index(drop=True)
    adicionar_ao_log(f"Total de indices coletados: {len(df)}")
    return df


def upsert_no_banco(df: pd.DataFrame) -> dict:
    """Upsert na tabela sienge.dim_incc. Retorna {'inseridos': N, 'atualizados': M}."""
    if df.empty:
        return {"inseridos": 0, "atualizados": 0}
    eng = get_engine()
    with eng.begin() as conn:
        antes = conn.execute(text("SELECT COUNT(*) FROM sienge.dim_incc")).scalar() or 0
        for _, row in df.iterrows():
            conn.execute(text("""
                INSERT INTO sienge.dim_incc (data, indice, variacao, atualizado_em)
                VALUES (:data, :indice, :variacao, now())
                ON CONFLICT (data) DO UPDATE SET
                    indice = EXCLUDED.indice,
                    variacao = EXCLUDED.variacao,
                    atualizado_em = now()
            """), {"data": row["data"], "indice": float(row["indice"]),
                   "variacao": float(row["variacao"]) if pd.notna(row["variacao"]) else None})
        depois = conn.execute(text("SELECT COUNT(*) FROM sienge.dim_incc")).scalar() or 0
    inseridos = depois - antes
    return {"inseridos": int(inseridos), "atualizados": int(max(len(df) - inseridos, 0))}


def executar() -> None:
    """Ponto de entrada: scraping + upsert."""
    adicionar_ao_log("\n========== SCRAPER INCC ==========")
    df = coletar_indices()
    if df.empty:
        adicionar_ao_log("ATENCAO: nenhum indice extraido. Talvez o HTML do Secovi tenha mudado.")
        sys.exit(1)
    resultado = upsert_no_banco(df)
    adicionar_ao_log(
        f"INCC: lidos={len(df)}, inseridos={resultado['inseridos']}, "
        f"atualizados={resultado['atualizados']}"
    )
    adicionar_ao_log("========== SCRAPER INCC FINALIZADO ==========\n")


if __name__ == "__main__":
    executar()
