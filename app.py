# ===== Taipy "health" -> "dash" (versão para deploy online) =====
import os
import pandas as pd
from taipy.gui import Gui

# ---------- Fonte de dados ----------
# Defina CSV_PATH nas variáveis de ambiente do Render (ex.: data/ativo.csv)
CSV_PATH = os.getenv("CSV_PATH", "data/ativo.csv")

def load_df():
    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        # Fallback com dado demo para a app não ficar em branco ao subir
        demo = [
            {"DATA":"31/07/2025","CART":"INTRAGS3120","ATIVO":"LFT_01/06/2030","QNT":42,"PRECO":16958.28,"VM":712247.8,"PL":402.46,"BP":0},
            {"DATA":"31/07/2025","CART":"INTRAGS3120","ATIVO":"ZERAGEM","QNT":None,"PRECO":None,"VM":200289.59,"PL":103.95,"BP":0},
            {"DATA":"31/07/2025","CART":"INTRAGS3120","ATIVO":"FACT SEED II FIC FIM","QNT":195727519.93,"PRECO":1.404275,"VM":274855263.05,"PL":-281593.18,"BP":-5.4},
            {"DATA":"31/07/2025","CART":"INTRAGS3120","ATIVO":"ITAU SOBERANO","QNT":1387.98,"PRECO":20.625698,"VM":28628.14,"PL":15.58,"BP":0},
            {"DATA":"31/07/2025","CART":"INTRAGS3120","ATIVO":"CAPITAL FIDC NP","QNT":0.45188,"PRECO":320818.7425,"VM":144971.57,"PL":-12.15,"BP":0},
        ]
        df = pd.DataFrame(demo)
    return df

# 0) Carrega DF
_df = load_df()

# 1) Página mínima (health)
head5 = _df.head(5)
page_health = """
# ✅ Health check
Se você está vendo esta página, o servidor está funcionando.

### Head(5) do seu DataFrame:
<|{head5}|table|height=240|rebuild=True|>

Ir para o dashboard: <|Open|button|on_action=go_dash|>
"""

def go_dash(state):
    state.navigate("/dash")

# 2) Normalização simplificada
def _normalize(df_in: pd.DataFrame):
    df = df_in.copy()
    cols = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None
    C_ATIVO = pick("ativo","descrição","descricao","fundo","ticker","nome") or "__ATIVO__"
    if C_ATIVO == "__ATIVO__":
        df[C_ATIVO] = "(sem nome)"

    C_SETOR = pick("setor","categoria","segmento","classe")
    if C_SETOR is None:
        C_SETOR = "__SETOR__"
        df[C_SETOR] = "Sem setor"

    C_DATA  = pick("data","date","dt")
    if C_DATA:
        df[C_DATA] = pd.to_datetime(df[C_DATA], errors="coerce", dayfirst=True)

    C_VALOR = pick("vm","valor","valor_mercado","value","preco","price","market_value")
    C_QTD   = pick("qnt","quantidade","qtde","qtd","shares","units")

    for c in (C_VALOR, C_QTD):
        if c and c in df.columns and not pd.api.types.is_numeric_dtype(df[c]):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, C_ATIVO, C_SETOR, C_DATA, C_VALOR, C_QTD

df_raw, C_ATIVO, C_SETOR, C_DATA, C_VALOR, C_QTD = _normalize(_df)

# 3) Estado inicial
setores = ["(Todos)"] + sorted(df_raw[C_SETOR].astype(str).dropna().unique().tolist())
setor_sel = setores[0]
if C_DATA and df_raw[C_DATA].notna().any():
    date_min = pd.to_datetime(df_raw[C_DATA].min()).date()
    date_max = pd.to_datetime(df_raw[C_DATA].max()).date()
else:
    date_min = date_max = None
date_from, date_to = date_min, date_max
linhas = 0; soma_valor = 0.0; soma_qtd = 0.0
df_view = pd.DataFrame(); fig = None

# 4) Filtro
def filtrar(state):
    df = df_raw.copy()
    if state.setor_sel and state.setor_sel != "(Todos)":
        df = df[df[C_SETOR].astype(str) == str(state.setor_sel)]
    if C_DATA and C_DATA in df.columns and df[C_DATA].notna().any():
        d_from = state.date_from or pd.to_datetime(df[C_DATA].min()).date()
        d_to   = state.date_to   or pd.to_datetime(df[C_DATA].max()).date()
        if d_from > d_to:
            d_from, d_to = d_to, d_from
        df = df[df[C_DATA].between(pd.to_datetime(d_from), pd.to_datetime(d_to))]
        state.date_from, state.date_to = d_from, d_to

    state.linhas = int(len(df))
    state.soma_valor = float(df[C_VALOR].sum()) if C_VALOR else 0.0
    state.soma_qtd   = float(df[C_QTD].sum())   if C_QTD   else 0.0
    if C_DATA and C_DATA in df.columns:
        df = df.sort_values(by=C_DATA)
    state.df_view = df

    state.fig = None
    if C_DATA and C_VALOR and not df.empty and df[C_DATA].notna().any():
        agg = df.groupby(C_DATA, as_index=False)[C_VALOR].sum()
        state.fig = {"data": agg, "x": C_DATA, "y": C_VALOR, "type": "line",
                     "title": "Evolução do Valor (agregado por dia)"}

# inicializa (simula um state)
class _S: pass
_tmp = _S()
_tmp.setor_sel, _tmp.date_from, _tmp.date_to = setor_sel, date_from, date_to
filtrar(_tmp)
linhas, soma_valor, soma_qtd, df_view, fig = _tmp.linhas, _tmp.soma_valor, _tmp.soma_qtd, _tmp.df_view, _tmp.fig

# 5) Página do dashboard
page_dash = """
# 📊 Dashboard

<|layout|columns=1 1 1|
**Linhas**: <|{linhas}|text|>
**Σ Valor**: <|{soma_valor}|text|>
**Σ Qtd**: <|{soma_qtd}|text|>
|>

<|layout|columns=1 1|
### Filtros
<|{setor_sel}|selector|lov={setores}|dropdown=True|label=Setor|on_change=on_change_filter|>
<|{date_from}|date|label=De|on_change=on_change_filter|>  <|{date_to}|date|label=Até|on_change=on_change_filter|>
|>

<|{fig}|chart|height=380|>

### Dados
<|{df_view}|table|height=420|rebuild=True|>
"""

def on_change_filter(state):
    filtrar(state)

# 6) App com duas rotas
pages = {"/": page_health, "dash": page_dash}
gui = Gui(pages=pages)

# 7) Run para servidor (Render, etc.)
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))  # Render fornece PORT
    gui.run(
        host="0.0.0.0",          # recebe conexões externas
        port=port,
        run_browser=False,
        use_reloader=False,
        single_client=False      # multi-usuário
    )
