"""
VP · Real Estate Intelligence — Script de Recolha Automática de Dados
======================================================================
Fontes: INE API JSON · BPStat API (Banco de Portugal) · BCE SDMX
Destino: Google Sheets (base de dados leve, lida pelo site)

Execução: python vp_collect.py
Cadência recomendada: trimestral (ou via GitHub Actions - ver README)

Pré-requisitos:
  pip install requests gspread google-auth pandas openpyxl

Autenticação Google Sheets:
  1. Google Cloud Console → criar projecto → activar Sheets API + Drive API
  2. Criar Service Account → descarregar credentials.json para esta pasta
  3. Partilhar a Google Sheet com o email da Service Account
"""

import requests
import json
import pandas as pd
from datetime import datetime, date
import time
import sys
import os

# ─── Configuração ────────────────────────────────────────────────────────────

# ID da Google Sheet (retirar do URL: docs.google.com/spreadsheets/d/[ID]/edit)
SHEET_ID = "id: 1vfyiRKaH9sR588chc9iuPeoW9Kn798VxtKI0anef1xE"

# Caminho para o ficheiro de credenciais da Service Account
CREDENTIALS_FILE = "credentials.json"

# Activar escrita na Google Sheet (False = apenas mostra os dados no terminal)
WRITE_TO_SHEET = True

# ─── Mapeamento de Indicadores INE ───────────────────────────────────────────
# Formato: { "nome_interno": { "varcd": "código", "geo": "PT", "desc": "..." } }
# varcd = indOcorrCod dos URLs do Portal INE

INE_INDICATORS = {
    "preco_mediano": {
        "varcd": "0012234",
        "geo": "PT",
        "desc": "Preço mediano habitação (€/m²)",
        "unidade": "€/m²",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "dim_categoria": "Total",  # Total / Novos / Existentes
        "notas": "Estatísticas de Preços da Habitação · INE · Metodologia 2022"
    },
    "preco_mediano_novos": {
        "varcd": "0012234",
        "geo": "PT",
        "desc": "Preço mediano habitação — novos (€/m²)",
        "unidade": "€/m²",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "dim_categoria": "Novos",
        "notas": "Estatísticas de Preços da Habitação · INE · Metodologia 2022"
    },
    "preco_mediano_existentes": {
        "varcd": "0012234",
        "geo": "PT",
        "desc": "Preço mediano habitação — existentes (€/m²)",
        "unidade": "€/m²",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "dim_categoria": "Existentes",
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
        "varcd": "0001460",
        "geo": "PT",
        "desc": "Fogos concluídos (N.º)",
        "unidade": "N.º",
        "cadencia": "Trimestral",
        "dimensao": "Oferta",
        "notas": "Estatísticas das Obras Concluídas · INE"
    },
    "iph_variacao": {
        "varcd": "0009742",
        "geo": "PT",
        "desc": "IPH — variação anual (%)",
        "unidade": "%",
        "cadencia": "Trimestral",
        "dimensao": "Mercado",
        "notas": "Índice de Preços da Habitação · INE"
    },
    "transaccoes_total": {
        "varcd": "0008096",
        "geo": "PT",
        "desc": "Transacções de alojamentos familiares (N.º)",
        "unidade": "N.º fogos",
        "cadencia": "Trimestral",
        "dimensao": "Mercado",
        "notas": "Estatísticas de Preços da Habitação · INE"
    },
    "custo_construcao": {
        "varcd": "0000638",
        "geo": "PT",
        "desc": "Custo de construção — variação homóloga ICCHN (%)",
        "unidade": "%",
        "cadencia": "Trimestral",
        "dimensao": "Viabilidade",
        "notas": "Índice de Custo de Construção de Habitação Nova · INE"
    },
    "ipc_hicp": {
        "varcd": "0007735",
        "geo": "PT",
        "desc": "Inflação HICP — variação anual (%)",
        "unidade": "%",
        "cadencia": "Mensal",
        "dimensao": "Macro",
        "notas": "Índice Harmonizado de Preços no Consumidor · INE / Eurostat"
    },
    "pib_real": {
        "varcd": "0007637",
        "geo": "PT",
        "desc": "PIB real — variação homóloga (%)",
        "unidade": "%",
        "cadencia": "Trimestral",
        "dimensao": "Macro",
        "notas": "Contas Nacionais Trimestrais · INE / BdP"
    },
}

# ─── Mapeamento de Séries BPStat (Banco de Portugal) ─────────────────────────
# IDs numéricos das séries em bpstat.bportugal.pt/serie/{id}

BPSTAT_SERIES = {
    "credito_habitacao": {
        "serie_id": "17175873",
        "desc": "Novo crédito habitação — novas operações (M€)",
        "unidade": "M€",
        "cadencia": "Mensal",
        "dimensao": "Procura",
        "notas": "Banco de Portugal · BPStat · Crédito habitação · Novas operações"
    },
    "taxa_esforco": {
        "serie_id": "16895098",
        "desc": "Taxa de esforço — crédito habitação (%)",
        "unidade": "%",
        "cadencia": "Trimestral",
        "dimensao": "Procura",
        "notas": "Banco de Portugal · BPStat · Estabilidade Financeira"
    },
}

# ─── Euribor (BCE SDMX API) ──────────────────────────────────────────────────
# Euribor 12M: BCE → Statistical Data Warehouse → FM/M.U2.EUR.RT0.MM.EURIBOR1YD_.HSTA

ECB_EURIBOR_12M = {
    "url": "https://data-api.ecb.europa.eu/service/data/FM/M.U2.EUR.RT0.MM.EURIBOR1YD_.HSTA",
    "desc": "Euribor 12 meses (%)",
    "unidade": "%",
    "cadencia": "Mensal",
    "dimensao": "Procura",
    "notas": "Banco Central Europeu · Statistical Data Warehouse · SDMX REST API"
}


# ─── Funções de recolha ───────────────────────────────────────────────────────

def fetch_ine(varcd: str, geo: str = "PT", n_periods: int = 20) -> list[dict]:
    """
    Chama a API JSON do INE e devolve lista de {periodo, valor}.
    Endpoint: https://www.ine.pt/ine/json_indicador/pindica.jsp
    Parâmetros:
      op=2   → série temporal completa
      varcd  → código do indicador (indOcorrCod)
      lang   → PT
    """
    url = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
    params = {
        "op": "2",
        "varcd": varcd,
        "lang": "PT"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30,
                           headers={"User-Agent": "VP-RealEstateIntelligence/1.0"})
        resp.raise_for_status()
        data = resp.json()
        
        # Estrutura INE: lista de objectos com "Dados" → lista de {geocod, dim_*, valor}
        resultados = []
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            dados = item.get("Dados", {})
            
            # Dados é dict onde chaves são períodos (ex: "2024T4", "2026M03")
            for periodo, observacoes in dados.items():
                if isinstance(observacoes, list):
                    for obs in observacoes:
                        if obs.get("geocod") == geo:
                            valor_str = obs.get("valor", "")
                            try:
                                valor = float(valor_str.replace(",", "."))
                            except (ValueError, AttributeError):
                                valor = None
                            resultados.append({
                                "periodo": periodo,
                                "valor": valor,
                                "geocod": geo
                            })
                            break
        
        # Ordenar por período e devolver os mais recentes
        resultados.sort(key=lambda x: x["periodo"])
        return resultados[-n_periods:] if n_periods else resultados
        
    except requests.RequestException as e:
        print(f"  ⚠ Erro INE (varcd={varcd}): {e}")
        return []
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  ⚠ Erro parsing INE (varcd={varcd}): {e}")
        return []


def fetch_bpstat(serie_id: str, n_periods: int = 60) -> list[dict]:
    """
    Chama a API BPStat do Banco de Portugal.
    Endpoint: https://bpstat.bportugal.pt/data/v1/series/{id}/
    Documentação: https://bpstat.bportugal.pt/data/docs
    
    Nota: requer registo gratuito em bpstat.bportugal.pt para chave API.
    Sem chave, o endpoint devolve dados públicos com rate limiting.
    """
    url = f"https://bpstat.bportugal.pt/data/v1/series/{serie_id}/"
    
    # Se tiveres chave API, adiciona aqui:
    # headers = {"Authorization": "Bearer SEU_TOKEN_AQUI"}
    headers = {"Accept": "application/json",
               "User-Agent": "VP-RealEstateIntelligence/1.0"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        resultados = []
        obs_list = data.get("observations", data.get("data", []))
        
        for obs in obs_list:
            periodo = obs.get("date", obs.get("period", ""))
            valor_raw = obs.get("value", obs.get("val", None))
            try:
                valor = float(valor_raw) if valor_raw is not None else None
            except (ValueError, TypeError):
                valor = None
            if periodo:
                resultados.append({"periodo": periodo, "valor": valor})
        
        resultados.sort(key=lambda x: x["periodo"])
        return resultados[-n_periods:] if n_periods else resultados
        
    except requests.RequestException as e:
        print(f"  ⚠ Erro BPStat (serie={serie_id}): {e}")
        return []


def fetch_euribor_ecb() -> list[dict]:
    """
    Euribor 12M via BCE Statistical Data Warehouse (SDMX REST API).
    Público, sem autenticação.
    URL: https://data-api.ecb.europa.eu/service/data/FM/M.U2.EUR.RT0.MM.EURIBOR1YD_.HSTA
    """
    url = ECB_EURIBOR_12M["url"]
    params = {
        "format": "jsondata",
        "startPeriod": "2019-01",
        "detail": "dataonly"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30,
                           headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        
        # Estrutura SDMX JSON: dataSets[0].series → observations
        series_data = (data.get("dataSets", [{}])[0]
                           .get("series", {})
                           .get("0:0:0:0:0:0:0", {})
                           .get("observations", {}))
        
        # Datas no structure
        dates = (data.get("structure", {})
                     .get("dimensions", {})
                     .get("observation", [{}])[0]
                     .get("values", []))
        
        resultados = []
        for i, vals in series_data.items():
            try:
                periodo = dates[int(i)].get("id", "")
                valor = float(vals[0]) if vals[0] is not None else None
                resultados.append({"periodo": periodo, "valor": valor})
            except (IndexError, ValueError, TypeError):
                continue
        
        resultados.sort(key=lambda x: x["periodo"])
        return resultados
        
    except Exception as e:
        print(f"  ⚠ Erro BCE Euribor: {e}")
        return []


# ─── Cálculo IPA ─────────────────────────────────────────────────────────────

def calcular_ipa(dados: dict) -> dict:
    """
    Calcula os 3 rácios do IPA — Índice de Pressão de Acessibilidade.
    
    Rácio A: Prestação mensal estimada ÷ Rendimento líquido mensal
    Rácio B: Renda mediana mensal ÷ Rendimento líquido mensal (usando área típica)
    Rácio C: Divergência acumulada preços vs rendimentos (base 2019)
    
    Parâmetros de calibração (alinhados com 03·IPA do ficheiro):
      - Área típica: 88.65 m² (INE — divisões × superfície/divisão)
      - LTV: 80% (BdP)
      - Prazo: 30 anos
      - Spread bancário médio: 1.5%
    """
    # Parâmetros de calibração
    AREA_TIPICA = 88.65       # m²
    LTV = 0.80
    PRAZO_ANOS = 30
    SPREAD = 0.015            # 1.5%
    LIMIAR_BDP = 0.35         # 35%
    LIMIAR_VP = 0.45          # 45%
    
    resultado = {}
    
    # Extrair últimos valores disponíveis
    preco = dados.get("preco_mediano_ultimo")
    renda_m2 = dados.get("renda_mediana_ultimo")
    rendimento = dados.get("rendimento_liquido_ultimo")
    euribor = dados.get("euribor_12m_ultimo")
    
    # Valores base 2019 para Rácio C
    preco_2019 = dados.get("preco_mediano_2019")
    rendimento_2019 = dados.get("rendimento_liquido_2019")
    
    # Rácio A — Pressão de Compra
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
    
    # Rácio B — Pressão de Arrendamento
    if all(v is not None for v in [renda_m2, rendimento]):
        renda_mensal_total = renda_m2 * AREA_TIPICA
        racio_b = renda_mensal_total / rendimento
        resultado["ipa_racio_b"] = round(racio_b * 100, 1)
        resultado["ipa_racio_b_renda_total"] = round(renda_mensal_total, 0)
    
    # Rácio C — Divergência Salarial Acumulada (base 2019)
    if all(v is not None for v in [preco, rendimento, preco_2019, rendimento_2019]):
        var_preco = (preco / preco_2019 - 1) * 100
        var_rendimento = (rendimento / rendimento_2019 - 1) * 100
        divergencia = var_preco - var_rendimento
        resultado["ipa_racio_c"] = round(divergencia, 1)
        resultado["ipa_racio_c_var_preco"] = round(var_preco, 1)
        resultado["ipa_racio_c_var_rendimento"] = round(var_rendimento, 1)
    
    return resultado


# ─── Cálculo DPW (Di Pasquale-Wheaton) ───────────────────────────────────────

def calcular_dpw(dados: dict) -> dict:
    """
    Modelo de 4 Quadrantes Di Pasquale-Wheaton.
    Gera os pontos de equilíbrio e as curvas para cada quadrante.
    
    Q1 — Mercado de Uso:     R = f(S)    → Renda = Função(Stock)
    Q2 — Capitalização:       P = R/yield → Preço = Renda ÷ Yield
    Q3 — Oferta de Construção: NC = f(P)  → Nova Construção = Função(Preço)
    Q4 — Ajuste de Stock:     NC = δ × S  → Nova Construção = Depreciação × Stock
    
    Parâmetros alinhados com 06·DPW do ficheiro.
    """
    # Parâmetros de calibração (do 03·IPA)
    YIELD_BRUTO = 0.055           # 5.5%
    ELAST_RENDA_STOCK = -0.6      # elasticidade renda-stock
    ELAST_OFERTA_CONSTR = 0.3     # elasticidade oferta-construção
    TAXA_DEPRECIACAO = 0.015      # 1.5% anual
    STOCK_BASE_2021 = 5_972_449   # Censos 2021
    CRESC_STOCK = 0.005           # 0.5% anual
    ANO_REF_CENSOS = 2021
    AREA_TIPICA = 88.65           # m²
    
    ano_corrente = datetime.now().year
    
    # Stock corrente estimado
    anos_desde_censos = ano_corrente - ANO_REF_CENSOS
    stock_corrente = STOCK_BASE_2021 * (1 + CRESC_STOCK) ** anos_desde_censos
    
    # Valores observados
    preco_obs = dados.get("preco_mediano_ultimo")
    renda_obs_m2 = dados.get("renda_mediana_ultimo")
    fogos_concluidos = dados.get("fogos_concluidos_ultimo")
    
    if any(v is None for v in [preco_obs, renda_obs_m2]):
        return {"dpw_disponivel": False}
    
    renda_obs = renda_obs_m2  # €/m²/mês
    nc_anual = (fogos_concluidos or 6000) * 4  # trimestral → anual
    
    # Constante Q1: R_obs = A × S^ε₁  →  A = R_obs / S^ε₁
    A_q1 = renda_obs / (stock_corrente ** ELAST_RENDA_STOCK)
    
    # Constante Q3: NC_obs = B × P^ε₃  →  B = NC_obs / P^ε₃
    B_q3 = nc_anual / (preco_obs ** ELAST_OFERTA_CONSTR)
    
    # Geração de pontos para curvas (20 pontos por quadrante)
    n_pontos = 20
    
    # Q1: Stock → Renda
    s_min = stock_corrente * 0.5
    s_max = stock_corrente * 1.5
    q1_pontos = []
    for i in range(n_pontos):
        s = s_min + (s_max - s_min) * i / (n_pontos - 1)
        r = A_q1 * (s ** ELAST_RENDA_STOCK)
        q1_pontos.append({"stock": round(s, 0), "renda": round(r, 4)})
    
    # Q2: Renda → Preço (P = R × 12 / yield)
    r_min = min(p["renda"] for p in q1_pontos)
    r_max = max(p["renda"] for p in q1_pontos)
    q2_pontos = []
    for i in range(n_pontos):
        r = r_min + (r_max - r_min) * i / (n_pontos - 1)
        p = (r * 12) / YIELD_BRUTO
        q2_pontos.append({"renda": round(r, 4), "preco": round(p, 0)})
    
    # Q3: Preço → Nova Construção
    p_min = min(p["preco"] for p in q2_pontos)
    p_max = max(p["preco"] for p in q2_pontos)
    q3_pontos = []
    for i in range(n_pontos):
        p = p_min + (p_max - p_min) * i / (n_pontos - 1)
        nc = B_q3 * (p ** ELAST_OFERTA_CONSTR)
        q3_pontos.append({"preco": round(p, 0), "nc": round(nc, 0)})
    
    # Q4: Nova Construção → Stock (NC = δ × S → S = NC / δ)
    nc_min = min(p["nc"] for p in q3_pontos)
    nc_max = max(p["nc"] for p in q3_pontos)
    q4_pontos = []
    for i in range(n_pontos):
        nc = nc_min + (nc_max - nc_min) * i / (n_pontos - 1)
        s = nc / TAXA_DEPRECIACAO
        q4_pontos.append({"nc": round(nc, 0), "stock": round(s, 0)})
    
    # Ponto de equilíbrio (observado)
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
    """
    Escreve os dados recolhidos numa Google Sheet com 3 separadores:
      - VP_Indicadores       → tabela flat de todos os indicadores, 1 linha por período
      - VP_IPA               → painel IPA calculado
      - VP_DPW               → pontos das curvas para o modelo 4 quadrantes
    """
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
            cfg = {**INE_INDICATORS, **BPSTAT_SERIES}.get(nome, {})
            for obs in series:
                linhas_ind.append([
                    nome,
                    cfg.get("desc", nome),
                    cfg.get("dimensao", ""),
                    obs["periodo"],
                    obs["valor"],
                    cfg.get("unidade", ""),
                    "INE" if nome in INE_INDICATORS else "BdP/BPStat",
                    cfg.get("notas", ""),
                    timestamp
                ])
        
        # Euribor
        for obs in todos_dados.get("euribor", []):
            linhas_ind.append([
                "euribor_12m",
                ECB_EURIBOR_12M["desc"],
                ECB_EURIBOR_12M["dimensao"],
                obs["periodo"],
                obs["valor"],
                ECB_EURIBOR_12M["unidade"],
                "BCE",
                ECB_EURIBOR_12M["notas"],
                timestamp
            ])
        
        ws_ind.clear()
        ws_ind.update(linhas_ind, value_input_option="USER_ENTERED")
        print(f"  ✓ VP_Indicadores → {len(linhas_ind)-1} observações escritas")
        
        # ── Separador 2: IPA ──────────────────────────────────────────────────
        try:
            ws_ipa = sh.worksheet("VP_IPA")
        except gspread.WorksheetNotFound:
            ws_ipa = sh.add_worksheet("VP_IPA", rows=50, cols=5)
        
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
                ws_dpw = sh.add_worksheet("VP_DPW", rows=200, cols=12)
            
            linhas_dpw = [["Quadrante", "X", "Y", "Label_X", "Label_Y", "Actualizado_em"]]
            
            for pt in dpw["dpw_q1"]:
                linhas_dpw.append(["Q1_Uso", pt["stock"], pt["renda"], "Stock (fogos)", "Renda (€/m²/mês)", timestamp])
            for pt in dpw["dpw_q2"]:
                linhas_dpw.append(["Q2_Capitalizacao", pt["preco"], pt["renda"], "Preço (€/m²)", "Renda (€/m²/mês)", timestamp])
            for pt in dpw["dpw_q3"]:
                linhas_dpw.append(["Q3_Oferta", pt["preco"], pt["nc"], "Preço (€/m²)", "Nova Construção (anual)", timestamp])
            for pt in dpw["dpw_q4"]:
                linhas_dpw.append(["Q4_Stock", pt["nc"], pt["stock"], "Nova Construção (anual)", "Stock (fogos)", timestamp])
            
            # Ponto de equilíbrio
            linhas_dpw.append(["EQUILIBRIO", dpw["dpw_preco_equilibrio"], dpw["dpw_renda_equilibrio"], "Preço (€/m²)", "Renda (€/m²/mês)", timestamp])
            
            ws_dpw.clear()
            ws_dpw.update(linhas_dpw, value_input_option="USER_ENTERED")
            print(f"  ✓ VP_DPW → {len(linhas_dpw)-1} pontos escritos")
        
        print(f"\n  ✅ Google Sheet actualizada: https://docs.google.com/spreadsheets/d/{sheet_id}")
        
    except ImportError:
        print("  ⚠ gspread não instalado: pip install gspread google-auth")
    except FileNotFoundError:
        print(f"  ⚠ Ficheiro de credenciais não encontrado: {credentials_file}")
    except Exception as e:
        print(f"  ⚠ Erro ao escrever na Sheet: {e}")


def guardar_json_local(todos_dados: dict, ficheiro: str = "vp_dados.json"):
    """Guarda os dados num ficheiro JSON local (backup e debug)."""
    with open(ficheiro, "w", encoding="utf-8") as f:
        json.dump(todos_dados, f, ensure_ascii=False, indent=2, default=str)
    print(f"  ✓ Dados guardados em {ficheiro}")


# ─── Orquestrador principal ───────────────────────────────────────────────────

def extrair_ultimo_valor(series: list, ano_base: int = None) -> float | None:
    """
    De uma lista de {periodo, valor}, extrai o último não-nulo.
    Se ano_base for fornecido, extrai o valor do ano/período mais próximo desse ano.
    """
    if not series:
        return None
    
    series_validas = [s for s in series if s.get("valor") is not None]
    if not series_validas:
        return None
    
    if ano_base:
        # Encontrar o período mais próximo do ano base
        candidatos = [s for s in series_validas if str(ano_base) in s["periodo"]]
        if candidatos:
            return candidatos[0]["valor"]
        return None
    
    return series_validas[-1]["valor"]


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
        time.sleep(0.5)  # Respeitar rate limiting
    
    # ── 2. BPStat (Banco de Portugal) ─────────────────────────────────────────
    print("\n[2/4] BPStat — Recolha de séries BdP")
    for nome, cfg in BPSTAT_SERIES.items():
        print(f"  → {cfg['desc']} (série={cfg['serie_id']})")
        series = fetch_bpstat(cfg["serie_id"], n_periods=60)
        todos_dados["series"][nome] = series
        if series:
            ultimo = series[-1]
            print(f"     Último: {ultimo['periodo']} = {ultimo['valor']} {cfg['unidade']}")
        else:
            print(f"     ⚠ Sem dados")
        time.sleep(0.5)
    
    # ── 3. Euribor (BCE) ──────────────────────────────────────────────────────
    print("\n[3/4] BCE — Euribor 12M")
    euribor_series = fetch_euribor_ecb()
    todos_dados["euribor"] = euribor_series
    todos_dados["series"]["euribor_12m"] = euribor_series
    if euribor_series:
        ultimo = euribor_series[-1]
        print(f"  ✓ Último: {ultimo['periodo']} = {ultimo['valor']}%")
    
    # ── 4. Calcular IPA e DPW ─────────────────────────────────────────────────
    print("\n[4/4] Cálculo IPA e DPW")
    
    # Preparar inputs para cálculos
    inputs_calc = {
        "preco_mediano_ultimo": extrair_ultimo_valor(todos_dados["series"].get("preco_mediano", [])),
        "renda_mediana_ultimo": extrair_ultimo_valor(todos_dados["series"].get("renda_mediana", [])),
        "rendimento_liquido_ultimo": extrair_ultimo_valor(todos_dados["series"].get("rendimento_liquido", [])),
        "euribor_12m_ultimo": extrair_ultimo_valor(euribor_series),
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
        print(f"  DPW Equilíbrio: Preço {todos_dados['dpw']['dpw_preco_equilibrio']} €/m² · NC {todos_dados['dpw']['dpw_nc_equilibrio']:,.0f} fogos/ano")
    
    # ── 5. Guardar resultados ─────────────────────────────────────────────────
    print("\n[Saída] Guardar dados")
    guardar_json_local(todos_dados, "vp_dados.json")
    
    if WRITE_TO_SHEET and SHEET_ID != "SUBSTITUIR_PELO_ID_DA_TUA_GOOGLE_SHEET":
        if os.path.exists(CREDENTIALS_FILE):
            escrever_google_sheets(todos_dados, SHEET_ID, CREDENTIALS_FILE)
        else:
            print(f"  ⚠ credentials.json não encontrado. Dados guardados apenas em vp_dados.json")
            print(f"    Ver README.md para configurar Google Sheets.")
    else:
        print(f"  ℹ Escrita na Google Sheet desactivada ou SHEET_ID não configurado.")
        print(f"    Editar SHEET_ID e WRITE_TO_SHEET em vp_collect.py para activar.")
    
    print("\n" + "=" * 60)
    print(f"✅ Concluído: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    return todos_dados


if __name__ == "__main__":
    correr()
