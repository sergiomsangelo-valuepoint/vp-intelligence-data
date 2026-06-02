"""
VP · Real Estate Intelligence — Script de Recolha Automática de Dados
======================================================================
Fontes: INE API JSON · BPStat API (Banco de Portugal) · BCE SDMX
Destino: Google Sheets (base de dados leve, lida pelo site)
"""

import requests
import json
import pandas as pd
from datetime import datetime, date
import time
import sys
import os

# ─── Configuração ────────────────────────────────────────────────────────────

SHEET_ID = "1vfyiRKaH9sR588chc9iuPeoW9Kn798VxtKI0anef1xE"
CREDENTIALS_FILE = "credentials.json"
WRITE_TO_SHEET = True

# ─── Mapeamento de Indicadores INE ───────────────────────────────────────────

INE_INDICATORS = {
    "preco_mediano": {
        "varcd": "0012234",
        "geo": "PT",
        "desc": "Preço mediano habitação (€/m²)",
        "unidade": "€/m²",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "notas": "Estatísticas de Preços da Habitação · INE · Metodologia 2022"
    },
    "preco_mediano_novos": {
        "varcd": "0012234",
        "geo": "PT",
        "desc": "Preço mediano habitação — novos (€/m²)",
        "unidade": "€/m²",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "notas": "Estatísticas de Preços da Habitação · INE · Metodologia 2022"
    },
    "preco_mediano_existentes": {
        "varcd": "0012234",
        "geo": "PT",
        "desc": "Preço mediano habitação — existentes (€/m²)",
        "unidade": "€/m²",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "notas": "Estatísticas de Preços da Habitação · INE · Metodologia 2022"
    },
    "renda_mediana": {
        "varcd": "0012571",
        "geo": "PT",
        "desc": "Renda mediana novos contratos (€/m²/mês)",
        "unidade": "€/m²/mês",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "notas": "Estatísticas de Rendas da Habitação · INE · Metodologia 2021"
    },
    "rendimento_liquido": {
        "varcd": "0012133",
        "geo": "PT",
        "desc": "Rendimento médio líquido mensal (€)",
        "unidade": "€/mês",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "notas": "Inquérito ao Emprego · INE · Série 2021 · Total profissões"
    },
    "fogos_licenciados": {
        "varcd": "0001371",
        "geo": "PT",
        "desc": "Fogos licenciados — construções novas (N.º)",
        "unidade": "N.º",
        "cadencia": "Mensal",
        "dimensao": "Oferta",
        "notas": "Estatísticas das Obras Licenciadas · INE"
    },
    "fogos_concluidos": {
        "varcd": "0012778",
        "geo": "PT",
        "desc": "Fogos concluídos (N.º)",
        "unidade": "N.º",
        "cadencia": "Trimestral",
        "dimensao": "Oferta",
        "notas": "Estatísticas das Obras Concluídas · INE"
    },
    "iph_variacao": {
        "varcd": "0014341",
        "geo": "PT",
        "desc": "IPH — variação anual (%)",
        "unidade": "%",
        "cadencia": "Trimestral",
        "dimensao": "Mercado",
        "notas": "Índice de Preços da Habitação · INE"
    },
    "transaccoes_total": {
        "varcd": "0012785",
        "geo": "PT",
        "desc": "Transacções de alojamentos familiares (N.º)",
        "unidade": "N.º fogos",
        "cadencia": "Trimestral",
        "dimensao": "Mercado",
        "notas": "Estatísticas de Preços da Habitação · INE · Total · Todos compradores"
    },
    "custo_construcao": {
        "varcd": "0011751",
        "geo": "PT",
        "desc": "Custo de construção — variação homóloga ICCHN (%)",
        "unidade": "%",
        "cadencia": "Trimestral",
        "dimensao": "Viabilidade",
        "notas": "Índice de Custo de Construção de Habitação Nova · INE"
    },
    "ipc_hicp": {
        "varcd": "0014664",
        "geo": "PT",
        "desc": "Inflação HICP — variação anual (%)",
        "unidade": "%",
        "cadencia": "Mensal",
        "dimensao": "Macro",
        "notas": "Índice Harmonizado de Preços no Consumidor · INE / Eurostat"
    },
    "pib_real": {
        "varcd": "0013431",
        "geo": "PT",
        "desc": "PIB real — variação homóloga (%)",
        "unidade": "%",
        "cadencia": "Trimestral",
        "dimensao": "Macro",
        "notas": "Contas Nacionais Trimestrais · INE / BdP"
    },
    "divisoes_por_fogo": {
        "varcd": "0000079",
        "geo": "PT",
        "desc": "Divisões por fogo concluído (N.º)",
        "unidade": "N.º",
        "cadencia": "Anual",
        "dimensao": "Oferta",
        "notas": "Estatísticas das Obras Concluídas · INE · Construções novas"
    },
    "superficie_habitavel": {
        "varcd": "0008333",
        "geo": "PT",
        "desc": "Superfície habitável média das divisões concluídas (m²)",
        "unidade": "m²",
        "cadencia": "Anual",
        "dimensao": "Oferta",
        "notas": "Estatísticas das Obras Concluídas · INE · Construções novas"
    },
}


# ─── Funções de recolha ───────────────────────────────────────────────────────

def fetch_ine(varcd: str, geo: str = "PT", n_periods: int = 20) -> list:
    url = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
    params = {"op": "2", "varcd": varcd, "lang": "PT"}

    try:
        resp = requests.get(url, params=params, timeout=30,
                            headers={"User-Agent": "VP-RealEstateIntelligence/1.0"})
        resp.raise_for_status()
        data = resp.json()

        resultados = []
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            dados = item.get("Dados", {})

            for periodo, observacoes in dados.items():
                if isinstance(observacoes, list):
                    melhor_obs = None
                    for obs in observacoes:
                        if obs.get("geocod") != geo:
                            continue
                        if obs.get("sinal_conv") == "x":
                            continue
                        valor_str = obs.get("valor", obs.get("ind_string", ""))
                        if not valor_str or valor_str == "x":
                            continue
                        dim3 = obs.get("dim_3_t", "Total")
                        dim4 = obs.get("dim_4_t", "Total")
                        dim5 = obs.get("dim_5_t", "Total")
                        is_total = (dim3 == "Total" and dim4 == "Total" and dim5 == "Total")
                        if is_total:
                            melhor_obs = obs
                            break
                        if melhor_obs is None:
                            melhor_obs = obs
                    if melhor_obs:
                        valor_str = melhor_obs.get("valor", melhor_obs.get("ind_string", ""))
                        try:
                            valor = float(str(valor_str).replace(" ", "").replace(",", "."))
                            resultados.append({"periodo": periodo, "valor": valor, "geocod": geo})
                        except (ValueError, AttributeError):
                            pass

        resultados.sort(key=lambda x: x["periodo"])
        return resultados[-n_periods:] if n_periods else resultados

    except requests.RequestException as e:
        print(f"  ⚠ Erro INE (varcd={varcd}): {e}")
        return []
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  ⚠ Erro parsing INE (varcd={varcd}): {e}")
        return []


# ─── Cálculo IPA ─────────────────────────────────────────────────────────────

def calcular_ipa(dados: dict) -> dict:
    divisoes = dados.get("divisoes_por_fogo_ultimo") or 4.2
    superficie = dados.get("superficie_habitavel_ultimo") or 21.1
    AREA_TIPICA = divisoes * superficie
    print(f"  Área típica calculada: {divisoes} div × {superficie} m²/div = {AREA_TIPICA:.1f} m²")

    LTV = 0.76
    PRAZO_ANOS = 30
    SPREAD = 0.015
    LIMIAR_BDP = 0.45
    LIMIAR_VP = 0.45

    resultado = {}

    preco = dados.get("preco_mediano_ultimo")
    renda_m2 = dados.get("renda_mediana_ultimo")
    rendimento = dados.get("rendimento_liquido_ultimo")
    euribor = dados.get("euribor_12m_ultimo")
    preco_2019 = dados.get("preco_mediano_2019")
    rendimento_2019 = dados.get("rendimento_liquido_2019")

    if all(v is not None for v in [preco, euribor, rendimento]):
        taxa_mensal = (euribor / 100 + SPREAD) / 12
        n_meses = PRAZO_ANOS * 12
        capital = preco * AREA_TIPICA * LTV
        if taxa_mensal > 0:
            prestacao = capital * taxa_mensal / (1 - (1 + taxa_mensal) ** (-n_meses))
        else:
            prestacao = capital / n_meses
        racio_a = prestacao / rendimento
        resultado["ipa_racio_a"] = round(racio_a * 100, 1)
        resultado["ipa_racio_a_prestacao"] = round(prestacao, 0)
        resultado["ipa_racio_a_estado"] = (
            "Pressão crítica" if racio_a > LIMIAR_VP else
            "Pressão elevada" if racio_a > LIMIAR_BDP else
            "Pressão moderada" if racio_a > 0.25 else
            "Acessibilidade saudável"
        )

    if all(v is not None for v in [renda_m2, rendimento]):
        renda_mensal_total = renda_m2 * AREA_TIPICA
        racio_b = renda_mensal_total / rendimento
        resultado["ipa_racio_b"] = round(racio_b * 100, 1)
        resultado["ipa_racio_b_renda_total"] = round(renda_mensal_total, 0)

    if all(v is not None for v in [preco, rendimento, preco_2019, rendimento_2019]):
        var_preco = (preco / preco_2019 - 1) * 100
        var_rendimento = (rendimento / rendimento_2019 - 1) * 100
        divergencia = var_preco - var_rendimento
        resultado["ipa_racio_c"] = round(divergencia, 1)
        resultado["ipa_racio_c_var_preco"] = round(var_preco, 1)
        resultado["ipa_racio_c_var_rendimento"] = round(var_rendimento, 1)

    return resultado


# ─── Cálculo DPW ─────────────────────────────────────────────────────────────

def calcular_dpw(dados: dict) -> dict:
    YIELD_BRUTO = 0.055
    ELAST_RENDA_STOCK = -0.6
    ELAST_OFERTA_CONSTR = 0.3
    TAXA_DEPRECIACAO = 0.02
    STOCK_BASE_2021 = 5_972_449
    CRESC_STOCK = 0.005
    ANO_REF_CENSOS = 2021

    divisoes = dados.get("divisoes_por_fogo_ultimo") or 4.2
    superficie = dados.get("superficie_habitavel_ultimo") or 21.1
    AREA_TIPICA = divisoes * superficie

    ano_corrente = datetime.now().year
    anos_desde_censos = ano_corrente - ANO_REF_CENSOS
    stock_corrente = STOCK_BASE_2021 * (1 + CRESC_STOCK) ** anos_desde_censos

    preco_obs = dados.get("preco_mediano_ultimo")
    renda_obs_m2 = dados.get("renda_mediana_ultimo")
    fogos_concluidos = dados.get("fogos_concluidos_ultimo")

    if any(v is None for v in [preco_obs, renda_obs_m2]):
        return {"dpw_disponivel": False}

    renda_obs = renda_obs_m2
    nc_anual = (fogos_concluidos or 6000) * 4

    A_q1 = renda_obs / (stock_corrente ** ELAST_RENDA_STOCK)
    B_q3 = nc_anual / (preco_obs ** ELAST_OFERTA_CONSTR)

    n_pontos = 20
    s_min = stock_corrente * 0.5
    s_max = stock_corrente * 1.5
    q1_pontos = []
    for i in range(n_pontos):
        s = s_min + (s_max - s_min) * i / (n_pontos - 1)
        r = A_q1 * (s ** ELAST_RENDA_STOCK)
        q1_pontos.append({"stock": round(s, 0), "renda": round(r, 4)})

    r_min = min(p["renda"] for p in q1_pontos)
    r_max = max(p["renda"] for p in q1_pontos)
    q2_pontos = []
    for i in range(n_pontos):
        r = r_min + (r_max - r_min) * i / (n_pontos - 1)
        p = (r * 12) / YIELD_BRUTO
        q2_pontos.append({"renda": round(r, 4), "preco": round(p, 0)})

    p_min = min(p["preco"] for p in q2_pontos)
    p_max = max(p["preco"] for p in q2_pontos)
    q3_pontos = []
    for i in range(n_pontos):
        p = p_min + (p_max - p_min) * i / (n_pontos - 1)
        nc = B_q3 * (p ** ELAST_OFERTA_CONSTR)
        q3_pontos.append({"preco": round(p, 0), "nc": round(nc, 0)})

    nc_min = min(p["nc"] for p in q3_pontos)
    nc_max = max(p["nc"] for p in q3_pontos)
    q4_pontos = []
    for i in range(n_pontos):
        nc = nc_min + (nc_max - nc_min) * i / (n_pontos - 1)
        s = nc / TAXA_DEPRECIACAO
        q4_pontos.append({"nc": round(nc, 0), "stock": round(s, 0)})

    preco_eq = (renda_obs * 12) / YIELD_BRUTO
    nc_eq = B_q3 * (preco_eq ** ELAST_OFERTA_CONSTR)

    return {
        "dpw_disponivel": True,
        "dpw_ano": ano_corrente,
        "dpw_stock_corrente": round(stock_corrente, 0),
        "dpw_yield": YIELD_BRUTO * 100,
        "dpw_preco_equilibrio": round(preco_eq, 0),
        "dpw_renda_equilibrio": round(renda_obs, 4),
        "dpw_nc_equilibrio": round(nc_eq, 0),
        "dpw_nc_anual_observado": round(nc_anual, 0),
        "dpw_q1": q1_pontos,
        "dpw_q2": q2_pontos,
        "dpw_q3": q3_pontos,
        "dpw_q4": q4_pontos,
    }


# ─── Escrita na Google Sheet ──────────────────────────────────────────────────

def escrever_google_sheets(todos_dados: dict, sheet_id: str, credentials_file: str):
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ── Separador 1: Indicadores ──────────────────────────────────────────
        try:
            ws_ind = sh.worksheet("VP_Indicadores")
        except gspread.WorksheetNotFound:
            ws_ind = sh.add_worksheet("VP_Indicadores", rows=500, cols=10)

        cabecalho_ind = ["Indicador", "Descrição", "Dimensão", "Período", "Valor",
                         "Unidade", "Fonte", "Notas", "Actualizado_em"]
        linhas_ind = [cabecalho_ind]

        for nome, series in todos_dados.get("series", {}).items():
            cfg = INE_INDICATORS.get(nome, {})
            for obs in series:
                linhas_ind.append([
                    nome,
                    cfg.get("desc", nome),
                    cfg.get("dimensao", ""),
                    obs["periodo"],
                    obs["valor"],
                    cfg.get("unidade", ""),
                    "INE",
                    cfg.get("notas", ""),
                    timestamp
                ])

        if len(linhas_ind) > 1:
            try:
                existentes = ws_ind.get_all_records()
                manuais = [r for r in existentes if r.get("Fonte") not in ("INE", "BdP/BPStat")]
                if manuais:
                    for m in manuais:
                        linhas_ind.append([
                            m.get("Indicador", ""), m.get("Descrição", ""),
                            m.get("Dimensão", ""), m.get("Período", ""),
                            m.get("Valor", ""), m.get("Unidade", ""),
                            m.get("Fonte", ""), m.get("Notas", ""),
                            m.get("Actualizado_em", "")
                        ])
            except Exception:
                pass
            ws_ind.clear()
            ws_ind.update(linhas_ind, value_input_option="USER_ENTERED")
            print(f"  ✓ VP_Indicadores → {len(linhas_ind)-1} observações escritas")
        else:
            print(f"  ⚠ VP_Indicadores → sem dados novos, Sheet preservada")

        # ── Separador 2: IPA ──────────────────────────────────────────────────
        try:
            ws_ipa = sh.worksheet("VP_IPA")
        except gspread.WorksheetNotFound:
            ws_ipa = sh.add_worksheet("VP_IPA", rows=50, cols=6)

        ipa = todos_dados.get("ipa", {})
        linhas_ipa = [
            ["Rácio", "Valor", "Descrição", "Limiar BdP", "Estado", "Actualizado_em"],
            ["A_pressao_compra", ipa.get("ipa_racio_a"), "Prestação / Rendimento (%)", 35, ipa.get("ipa_racio_a_estado"), timestamp],
            ["A_prestacao_estimada", ipa.get("ipa_racio_a_prestacao"), "Prestação mensal (€)", "", "", timestamp],
            ["B_pressao_arrendamento", ipa.get("ipa_racio_b"), "Renda total / Rendimento (%)", 35, "", timestamp],
            ["B_renda_total", ipa.get("ipa_racio_b_renda_total"), "Renda mensal total área típica (€)", "", "", timestamp],
            ["C_divergencia", ipa.get("ipa_racio_c"), "Divergência acumulada preços vs rendimentos (p.p., base 2019)", 0, "", timestamp],
            ["C_var_preco_2019", ipa.get("ipa_racio_c_var_preco"), "Variação preços desde 2019 (%)", "", "", timestamp],
            ["C_var_rendimento_2019", ipa.get("ipa_racio_c_var_rendimento"), "Variação rendimento desde 2019 (%)", "", "", timestamp],
        ]
        ws_ipa.clear()
        ws_ipa.update(linhas_ipa, value_input_option="USER_ENTERED")
        print(f"  ✓ VP_IPA → {len(linhas_ipa)-1} rácios escritos")

        # ── Separador 3: DPW ──────────────────────────────────────────────────
        dpw = todos_dados.get("dpw", {})
        if dpw.get("dpw_disponivel"):
            try:
                ws_dpw = sh.worksheet("VP_DPW")
            except gspread.WorksheetNotFound:
                ws_dpw = sh.add_worksheet("VP_DPW", rows=200, cols=6)

            linhas_dpw = [["Quadrante", "X", "Y", "Label_X", "Label_Y", "Actualizado_em"]]
            for pt in dpw["dpw_q1"]:
                linhas_dpw.append(["Q1_Uso", pt["stock"], pt["renda"], "Stock (fogos)", "Renda (€/m²/mês)", timestamp])
            for pt in dpw["dpw_q2"]:
                linhas_dpw.append(["Q2_Capitalizacao", pt["preco"], pt["renda"], "Preço (€/m²)", "Renda (€/m²/mês)", timestamp])
            for pt in dpw["dpw_q3"]:
                linhas_dpw.append(["Q3_Oferta", pt["preco"], pt["nc"], "Preço (€/m²)", "Nova Construção (anual)", timestamp])
            for pt in dpw["dpw_q4"]:
                linhas_dpw.append(["Q4_Stock", pt["nc"], pt["stock"], "Nova Construção (anual)", "Stock (fogos)", timestamp])
            linhas_dpw.append(["EQUILIBRIO", dpw["dpw_preco_equilibrio"], dpw["dpw_renda_equilibrio"], "Preço (€/m²)", "Renda (€/m²/mês)", timestamp])

            ws_dpw.clear()
            ws_dpw.update(linhas_dpw, value_input_option="USER_ENTERED")
            print(f"  ✓ VP_DPW → {len(linhas_dpw)-1} pontos escritos")

        print(f"\n  ✅ Google Sheet actualizada: https://docs.google.com/spreadsheets/d/{sheet_id}")

    except ImportError:
        print("  ⚠ gspread não instalado")
    except FileNotFoundError:
        print(f"  ⚠ credentials.json não encontrado: {credentials_file}")
    except Exception as e:
        print(f"  ⚠ Erro ao escrever na Sheet: {e}")


def guardar_json_local(todos_dados: dict, ficheiro: str = "vp_dados.json"):
    with open(ficheiro, "w", encoding="utf-8") as f:
        json.dump(todos_dados, f, ensure_ascii=False, indent=2, default=str)
    print(f"  ✓ Dados guardados em {ficheiro}")


def extrair_ultimo_valor(series: list, ano_base: int = None):
    if not series:
        return None
    series_validas = [s for s in series if s.get("valor") is not None]
    if not series_validas:
        return None
    if ano_base:
        candidatos = [s for s in series_validas if str(ano_base) in s["periodo"]]
        if candidatos:
            return candidatos[0]["valor"]
        return None
    return series_validas[-1]["valor"]


# ─── Orquestrador principal ───────────────────────────────────────────────────

def correr():
    print("=" * 60)
    print("VP · Real Estate Intelligence — Recolha de Dados")
    print(f"Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    todos_dados = {
        "meta": {
            "versao": "1.0",
            "data_recolha": datetime.now().isoformat(),
            "trimestre_referencia": f"Q{(datetime.now().month - 1) // 3 + 1} {datetime.now().year}"
        },
        "series": {},
        "euribor": [],
        "ipa": {},
        "dpw": {}
    }

    # ── 1. Indicadores INE ────────────────────────────────────────────────────
    print("\n[1/4] INE — Recolha de indicadores")
    for nome, cfg in INE_INDICATORS.items():
        print(f"  → {cfg['desc']} (varcd={cfg['varcd']})")
        series = fetch_ine(cfg["varcd"], geo=cfg.get("geo", "PT"), n_periods=40)
        todos_dados["series"][nome] = series
        if series:
            ultimo = series[-1]
            print(f"     Último: {ultimo['periodo']} = {ultimo['valor']} {cfg['unidade']}")
        else:
            print(f"     ⚠ Sem dados")
        time.sleep(0.5)

    # ── 2. Fontes manuais ─────────────────────────────────────────────────────
    print("\n[2/4] BPStat / Euribor — entrada manual (PDF BdP + euribor-rates.eu)")
    print("  ℹ Euribor 12M, crédito habitação e taxa de esforço: inserir manualmente na Sheet VP_Manual")
    todos_dados["series"]["credito_habitacao"] = []
    todos_dados["series"]["taxa_esforco"] = []
    todos_dados["series"]["euribor_12m"] = []
    todos_dados["euribor"] = []

    print("\n[3/4] Skipped — fontes manuais")

    # ── 4. Cálculo IPA e DPW ─────────────────────────────────────────────────
    print("\n[4/4] Cálculo IPA e DPW")

    # Ler Euribor do separador VP_Manual
    euribor_manual = None
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws_manual = sh.worksheet("VP_Manual")
        manuais = ws_manual.get_all_records()
        for row in manuais:
            if row.get("Indicador") == "euribor_12m":
                try:
                    euribor_manual = float(str(row.get("Valor", "")).replace(",", "."))
                except (ValueError, TypeError):
                    pass
        if euribor_manual:
            print(f"  ✓ Euribor manual lido: {euribor_manual}%")
    except Exception as e:
        print(f"  ⚠ Erro ao ler VP_Manual: {e}")

    # Preparar inputs
    inputs_calc = {
        "preco_mediano_ultimo": extrair_ultimo_valor(todos_dados["series"].get("preco_mediano", [])),
        "renda_mediana_ultimo": extrair_ultimo_valor(todos_dados["series"].get("renda_mediana", [])),
        "rendimento_liquido_ultimo": extrair_ultimo_valor(todos_dados["series"].get("rendimento_liquido", [])),
        "euribor_12m_ultimo": euribor_manual,
        "divisoes_por_fogo_ultimo": extrair_ultimo_valor(todos_dados["series"].get("divisoes_por_fogo", [])),
        "superficie_habitavel_ultimo": extrair_ultimo_valor(todos_dados["series"].get("superficie_habitavel", [])),
        "fogos_concluidos_ultimo": extrair_ultimo_valor(todos_dados["series"].get("fogos_concluidos", [])),
        "preco_mediano_2019": extrair_ultimo_valor(todos_dados["series"].get("preco_mediano", []), ano_base=2019),
        "rendimento_liquido_2019": extrair_ultimo_valor(todos_dados["series"].get("rendimento_liquido", []), ano_base=2019),
    }

    print(f"  Inputs IPA: {json.dumps({k: v for k, v in inputs_calc.items() if v is not None}, ensure_ascii=False)}")

    todos_dados["ipa"] = calcular_ipa(inputs_calc)
    todos_dados["dpw"] = calcular_dpw(inputs_calc)

    if todos_dados["ipa"].get("ipa_racio_a"):
        print(f"  IPA Rácio A (Compra): {todos_dados['ipa']['ipa_racio_a']}% — {todos_dados['ipa']['ipa_racio_a_estado']}")
    if todos_dados["ipa"].get("ipa_racio_b"):
        print(f"  IPA Rácio B (Arrendamento): {todos_dados['ipa']['ipa_racio_b']}%")
    if todos_dados["ipa"].get("ipa_racio_c") is not None:
        print(f"  IPA Rácio C (Divergência): +{todos_dados['ipa']['ipa_racio_c']} p.p.")
    if todos_dados["dpw"].get("dpw_disponivel"):
        print(f"  DPW Equilíbrio: Preço {todos_dados['dpw']['dpw_preco_equilibrio']} €/m²")

    # ── 5. Guardar resultados ─────────────────────────────────────────────────
    print("\n[Saída] Guardar dados")
    guardar_json_local(todos_dados, "vp_dados.json")

    if WRITE_TO_SHEET and SHEET_ID != "SUBSTITUIR_PELO_ID_DA_TUA_GOOGLE_SHEET":
        if os.path.exists(CREDENTIALS_FILE):
            escrever_google_sheets(todos_dados, SHEET_ID, CREDENTIALS_FILE)
        else:
            print(f"  ⚠ credentials.json não encontrado.")
    else:
        print(f"  ℹ Escrita na Google Sheet desactivada.")

    print("\n" + "=" * 60)
    print(f"✅ Concluído: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    return todos_dados


if __name__ == "__main__":
    correr()
