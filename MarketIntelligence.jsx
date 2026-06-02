/**
 * VP · Real Estate Intelligence — Dashboard Component
 * Para usar no Lovable (React SPA em value-point.pt)
 *
 * Lê dados de uma Google Sheet pública (apenas leitura, sem chave de API).
 * A Sheet tem 3 separadores: VP_Indicadores, VP_IPA, VP_DPW
 *
 * Instalação no Lovable:
 *   1. Criar ficheiro src/components/MarketIntelligence.jsx
 *   2. Colar este código
 *   3. Importar na página: import MarketIntelligence from "@/components/MarketIntelligence"
 *   4. Usar: <MarketIntelligence sheetId="SEU_SHEET_ID" />
 */

import { useState, useEffect, useCallback } from "react";

// ─── Configuração ─────────────────────────────────────────────────────────────

// ID da Google Sheet (mesmo ID do script Python)
// A Sheet deve estar partilhada como "Qualquer pessoa com o link pode ver"
const DEFAULT_SHEET_ID = "SUBSTITUIR_PELO_ID_DA_SHEET";

// Cores da marca VP
const VP = {
  copper: "#b87333",
  copperLight: "#e8d5c4",
  copperDark: "#7a4d22",
  teal: "#1d9e75",
  blue: "#378add",
  coral: "#d85a30",
  amber: "#ef9f27",
  gray: "#888780",
};

// ─── Utilitários ─────────────────────────────────────────────────────────────

function fmt(val, decimais = 0) {
  if (val === null || val === undefined) return "—";
  return Number(val).toLocaleString("pt-PT", {
    minimumFractionDigits: decimais,
    maximumFractionDigits: decimais,
  });
}

function fmtPct(val, decimais = 1) {
  if (val === null || val === undefined) return "—";
  return `${Number(val).toFixed(decimais)}%`;
}

// ─── Hook: carrega dados da Google Sheet ─────────────────────────────────────

function useSheetData(sheetId) {
  const [indicadores, setIndicadores] = useState([]);
  const [ipa, setIpa] = useState([]);
  const [dpw, setDpw] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(null);
  const [dataActualizacao, setDataActualizacao] = useState(null);

  const BASE = `https://sheets.googleapis.com/v4/spreadsheets/${sheetId}/values`;

  const carregarAba = useCallback(
    async (aba) => {
      const url = `${BASE}/${encodeURIComponent(aba)}?key=${import.meta.env.VITE_GOOGLE_API_KEY}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`Erro ${resp.status} ao carregar ${aba}`);
      const data = await resp.json();
      const [cabecalho, ...linhas] = data.values || [];
      return linhas.map((linha) =>
        Object.fromEntries(
          (cabecalho || []).map((col, i) => [col, linha[i] ?? null])
        )
      );
    },
    [BASE]
  );

  useEffect(() => {
    if (!sheetId || sheetId === DEFAULT_SHEET_ID) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setErro(null);

    Promise.all([
      carregarAba("VP_Indicadores"),
      carregarAba("VP_IPA"),
      carregarAba("VP_DPW"),
    ])
      .then(([ind, ipa, dpw]) => {
        setIndicadores(ind);
        setIpa(ipa);
        setDpw(dpw);
        if (ind.length > 0) {
          setDataActualizacao(ind[0]["Actualizado_em"]);
        }
        setLoading(false);
      })
      .catch((err) => {
        setErro(err.message);
        setLoading(false);
      });
  }, [sheetId, carregarAba]);

  return { indicadores, ipa, dpw, loading, erro, dataActualizacao };
}

// ─── Componentes auxiliares ──────────────────────────────────────────────────

function KpiCard({ label, valor, unidade, delta, cor }) {
  return (
    <div
      style={{
        background: "#f8f6f2",
        borderRadius: 8,
        padding: "14px 16px",
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "#888",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 500,
          color: cor || "#1a1a1a",
          lineHeight: 1.1,
        }}
      >
        {valor}
        {unidade && (
          <span style={{ fontSize: 12, color: "#888", marginLeft: 3 }}>
            {unidade}
          </span>
        )}
      </div>
      {delta && (
        <div style={{ fontSize: 11, color: "#888", marginTop: 3 }}>{delta}</div>
      )}
    </div>
  );
}

function SecHeader({ children }) {
  return (
    <div
      style={{
        fontSize: 13,
        fontWeight: 500,
        color: "#1a1a1a",
        borderBottom: `2px solid ${VP.copper}`,
        paddingBottom: 6,
        marginBottom: 16,
        marginTop: 28,
      }}
    >
      {children}
    </div>
  );
}

// ─── Modelo DPW — 4 Quadrantes (SVG puro, sem dependências) ──────────────────

function DPWChart({ dpwData }) {
  if (!dpwData || dpwData.length === 0) {
    return (
      <div
        style={{
          height: 400,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#888",
          fontSize: 13,
        }}
      >
        Dados DPW não disponíveis
      </div>
    );
  }

  // Separar pontos por quadrante
  const q1 = dpwData.filter((d) => d.Quadrante === "Q1_Uso");
  const q2 = dpwData.filter((d) => d.Quadrante === "Q2_Capitalizacao");
  const q3 = dpwData.filter((d) => d.Quadrante === "Q3_Oferta");
  const q4 = dpwData.filter((d) => d.Quadrante === "Q4_Stock");
  const eq = dpwData.filter((d) => d.Quadrante === "EQUILIBRIO");

  // Dimensões SVG
  const W = 600;
  const H = 600;
  const PAD = 50;
  const MEIO = W / 2;

  // Helper: normalizar para coordenadas SVG
  function norm(val, min, max, svgMin, svgMax) {
    if (max === min) return (svgMin + svgMax) / 2;
    return svgMin + ((val - min) / (max - min)) * (svgMax - svgMin);
  }

  // Extrair ranges
  const q1StockVals = q1.map((d) => parseFloat(d.X)).filter(Boolean);
  const q1RendaVals = q1.map((d) => parseFloat(d.Y)).filter(Boolean);
  const q3PrecoVals = q3.map((d) => parseFloat(d.X)).filter(Boolean);
  const q3NcVals = q3.map((d) => parseFloat(d.Y)).filter(Boolean);
  const q2PrecoVals = q2.map((d) => parseFloat(d.X)).filter(Boolean);
  const q4NcVals = q4.map((d) => parseFloat(d.Y)).filter(Boolean);

  if (
    q1StockVals.length === 0 ||
    q3NcVals.length === 0
  ) {
    return null;
  }

  const sMin = Math.min(...q1StockVals);
  const sMax = Math.max(...q1StockVals);
  const rMin = Math.min(...q1RendaVals);
  const rMax = Math.max(...q1RendaVals);
  const pMin = Math.min(...q3PrecoVals);
  const pMax = Math.max(...q3PrecoVals);
  const ncMin = Math.min(...q3NcVals);
  const ncMax = Math.max(...q3NcVals);

  // Coordenadas por quadrante:
  // Q1: canto sup-esq → X=stock (direita→esquerda), Y=renda (cima→baixo)
  // Q2: canto sup-dir → X=preço (esq→dir), Y=renda (cima→baixo) [espelhado de Q1]
  // Q3: canto inf-dir → X=preço (esq→dir), Y=NC (baixo→cima)
  // Q4: canto inf-esq → X=NC (dir→esq), Y=stock (baixo→cima) [espelhado de Q3]

  function ptQ1(stock, renda) {
    return {
      x: norm(stock, sMin, sMax, MEIO - PAD, PAD),
      y: norm(renda, rMin, rMax, PAD, MEIO - PAD),
    };
  }
  function ptQ2(preco, renda) {
    return {
      x: norm(preco, pMin, pMax, MEIO + PAD, W - PAD),
      y: norm(renda, rMin, rMax, PAD, MEIO - PAD),
    };
  }
  function ptQ3(preco, nc) {
    return {
      x: norm(preco, pMin, pMax, MEIO + PAD, W - PAD),
      y: norm(nc, ncMin, ncMax, H - PAD, MEIO + PAD),
    };
  }
  function ptQ4(nc, stock) {
    return {
      x: norm(nc, ncMin, ncMax, MEIO - PAD, PAD),
      y: norm(stock, sMin, sMax, H - PAD, MEIO + PAD),
    };
  }

  function pontoPath(pontos) {
    if (!pontos || pontos.length === 0) return "";
    return (
      "M " +
      pontos
        .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
        .join(" L ")
    );
  }

  const pathQ1 = pontoPath(
    q1.map((d) => ptQ1(parseFloat(d.X), parseFloat(d.Y)))
  );
  const pathQ2 = pontoPath(
    q2.map((d) => ptQ2(parseFloat(d.X), parseFloat(d.Y)))
  );
  const pathQ3 = pontoPath(
    q3.map((d) => ptQ3(parseFloat(d.X), parseFloat(d.Y)))
  );
  const pathQ4 = pontoPath(
    q4.map((d) => ptQ4(parseFloat(d.X), parseFloat(d.Y)))
  );

  // Ponto de equilíbrio
  let eqPt = null;
  if (eq.length > 0) {
    const eqX = parseFloat(eq[0].X);
    const eqY = parseFloat(eq[0].Y);
    // Equilíbrio está em Q2 (preço vs renda)
    eqPt = ptQ2(eqX, eqY);
  }

  const textStyle = { fontSize: 10, fill: "#888", fontFamily: "sans-serif" };
  const labelStyle = {
    fontSize: 11,
    fontWeight: "bold",
    fontFamily: "sans-serif",
  };

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      style={{ maxHeight: 500 }}
      role="img"
      aria-label="Modelo Di Pasquale-Wheaton — 4 quadrantes do mercado imobiliário português"
    >
      {/* Fundo dos quadrantes */}
      <rect x={PAD} y={PAD} width={MEIO - PAD * 1.5} height={MEIO - PAD * 1.5} fill="#f0ede8" rx="4" />
      <rect x={MEIO + PAD / 2} y={PAD} width={MEIO - PAD * 1.5} height={MEIO - PAD * 1.5} fill="#eaf3f0" rx="4" />
      <rect x={MEIO + PAD / 2} y={MEIO + PAD / 2} width={MEIO - PAD * 1.5} height={MEIO - PAD * 1.5} fill="#e8f0f8" rx="4" />
      <rect x={PAD} y={MEIO + PAD / 2} width={MEIO - PAD * 1.5} height={MEIO - PAD * 1.5} fill="#faf4ec" rx="4" />

      {/* Eixos centrais */}
      <line x1={MEIO} y1={PAD - 10} x2={MEIO} y2={H - PAD + 10} stroke="#ccc" strokeWidth={1} />
      <line x1={PAD - 10} y1={MEIO} x2={W - PAD + 10} y2={MEIO} stroke="#ccc" strokeWidth={1} />

      {/* Labels dos quadrantes */}
      <text x={PAD + 8} y={PAD + 16} style={{ ...labelStyle, fill: VP.copperDark }}>
        Q1 · Mercado de Uso
      </text>
      <text x={PAD + 8} y={PAD + 28} style={{ ...textStyle }}>
        Stock → Renda
      </text>

      <text x={MEIO + PAD * 0.8} y={PAD + 16} style={{ ...labelStyle, fill: VP.teal }}>
        Q2 · Capitalização
      </text>
      <text x={MEIO + PAD * 0.8} y={PAD + 28} style={textStyle}>
        Renda → Preço
      </text>

      <text x={MEIO + PAD * 0.8} y={MEIO + PAD * 0.8 + 12} style={{ ...labelStyle, fill: VP.blue }}>
        Q3 · Oferta
      </text>
      <text x={MEIO + PAD * 0.8} y={MEIO + PAD * 0.8 + 24} style={textStyle}>
        Preço → Nova Constr.
      </text>

      <text x={PAD + 8} y={MEIO + PAD * 0.8 + 12} style={{ ...labelStyle, fill: VP.amber }}>
        Q4 · Ajuste de Stock
      </text>
      <text x={PAD + 8} y={MEIO + PAD * 0.8 + 24} style={textStyle}>
        Nova Constr. → Stock
      </text>

      {/* Curvas */}
      <path d={pathQ1} fill="none" stroke={VP.copper} strokeWidth={2} />
      <path d={pathQ2} fill="none" stroke={VP.teal} strokeWidth={2} />
      <path d={pathQ3} fill="none" stroke={VP.blue} strokeWidth={2} />
      <path d={pathQ4} fill="none" stroke={VP.amber} strokeWidth={2} />

      {/* Ponto de equilíbrio */}
      {eqPt && (
        <g>
          <circle cx={eqPt.x} cy={eqPt.y} r={7} fill={VP.coral} opacity={0.85} />
          <circle cx={eqPt.x} cy={eqPt.y} r={3} fill="white" />
          <text
            x={eqPt.x + 10}
            y={eqPt.y - 8}
            style={{ fontSize: 10, fill: VP.coral, fontFamily: "sans-serif", fontWeight: "bold" }}
          >
            Equilíbrio
          </text>
        </g>
      )}

      {/* Seta indicando sentido de leitura */}
      <text x={MEIO - 20} y={MEIO + 5} style={{ fontSize: 9, fill: "#aaa", fontFamily: "sans-serif" }}>
        ↻
      </text>
    </svg>
  );
}

// ─── Painel IPA ───────────────────────────────────────────────────────────────

function IPAPanel({ ipaData }) {
  const get = (racio) => {
    const row = ipaData.find((r) => r["Rácio"] === racio);
    return row ? parseFloat(row["Valor"]) : null;
  };

  const racioA = get("A_pressao_compra");
  const racioB = get("B_pressao_arrendamento");
  const racioC = get("C_divergencia");
  const estado = ipaData.find((r) => r["Rácio"] === "A_pressao_compra")?.["Estado"];

  function corRacio(val, tipo = "ab") {
    if (val === null) return VP.gray;
    if (tipo === "ab") {
      if (val > 45) return VP.coral;
      if (val > 35) return VP.amber;
      if (val > 25) return "#f0c040";
      return VP.teal;
    }
    // Tipo C (divergência)
    if (val > 40) return VP.coral;
    if (val > 20) return VP.amber;
    return VP.teal;
  }

  function barWidth(val, max = 60) {
    if (val === null) return 0;
    return Math.min((val / max) * 100, 100);
  }

  const BarStyle = (val, tipo) => ({
    height: 5,
    borderRadius: 3,
    background: corRacio(val, tipo),
    width: `${barWidth(val)}%`,
    transition: "width 0.4s ease",
  });

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 12,
        marginBottom: 20,
      }}
    >
      {[
        {
          id: "A",
          label: "A · Compra",
          val: racioA,
          fmt: fmtPct,
          desc: "Prestação / Rendimento",
          tipo: "ab",
        },
        {
          id: "B",
          label: "B · Arrendamento",
          val: racioB,
          fmt: fmtPct,
          desc: "Renda total / Rendimento",
          tipo: "ab",
        },
        {
          id: "C",
          label: "C · Divergência",
          val: racioC,
          fmt: (v) => (v !== null ? `+${v.toFixed(1)} p.p.` : "—"),
          desc: "Preços vs rendimentos (base 2019)",
          tipo: "c",
        },
      ].map((r) => (
        <div
          key={r.id}
          style={{
            background: "#fff",
            border: "0.5px solid #e0ddd8",
            borderRadius: 12,
            padding: "14px 16px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 500,
              color: "#888",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 8,
            }}
          >
            {r.label}
          </div>
          <div
            style={{
              fontSize: 26,
              fontWeight: 500,
              color: corRacio(r.val, r.tipo),
              marginBottom: 4,
            }}
          >
            {r.fmt(r.val)}
          </div>
          <div
            style={{
              height: 5,
              background: "#eee",
              borderRadius: 3,
              margin: "8px 0 6px",
              overflow: "hidden",
            }}
          >
            <div style={BarStyle(r.val, r.tipo)} />
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#888",
              lineHeight: 1.4,
            }}
          >
            {r.desc}
            {r.id === "A" && estado && (
              <>
                <br />
                <strong style={{ color: corRacio(racioA, "ab") }}>
                  {estado}
                </strong>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function MarketIntelligence({
  sheetId = DEFAULT_SHEET_ID,
}) {
  const { indicadores, ipa, dpw, loading, erro, dataActualizacao } =
    useSheetData(sheetId);

  const [tabActiva, setTabActiva] = useState("visao");

  // Extrair KPIs principais
  function ultimoValor(nomeIndicador) {
    const series = indicadores
      .filter((r) => r["Indicador"] === nomeIndicador && r["Valor"])
      .sort((a, b) => b["Período"].localeCompare(a["Período"]));
    return series[0] || null;
  }

  const precoUlt = ultimoValor("preco_mediano");
  const rendaUlt = ultimoValor("renda_mediana");
  const iphUlt = ultimoValor("iph_variacao");
  const creditoUlt = ultimoValor("credito_habitacao");
  const euriborUlt = ultimoValor("euribor_12m");
  const transUlt = ultimoValor("transaccoes_total");

  const tabs = [
    { id: "visao", label: "Visão Geral" },
    { id: "ipa", label: "IPA" },
    { id: "dpw", label: "Modelo DPW" },
    { id: "mercado", label: "Mercado" },
    { id: "oferta", label: "Oferta" },
    { id: "macro", label: "Macro" },
  ];

  if (loading) {
    return (
      <div
        style={{
          padding: "40px 0",
          textAlign: "center",
          color: "#888",
          fontSize: 13,
        }}
      >
        <div
          style={{
            width: 20,
            height: 20,
            border: `2px solid ${VP.copper}`,
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
            margin: "0 auto 12px",
          }}
        />
        A carregar dados…
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (erro) {
    return (
      <div
        style={{
          padding: "20px",
          background: "#fef2f0",
          border: "0.5px solid #f0c0b8",
          borderRadius: 8,
          color: "#c0392b",
          fontSize: 13,
        }}
      >
        Erro ao carregar dados: {erro}
      </div>
    );
  }

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", maxWidth: 900, margin: "0 auto" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 12,
          paddingBottom: 12,
          borderBottom: "0.5px solid #e0ddd8",
          marginBottom: 20,
        }}
      >
        <span style={{ fontSize: 15, fontWeight: 500 }}>
          Value Point{" "}
          <span style={{ color: VP.copper }}>Market Intelligence</span>
        </span>
        <span
          style={{
            fontSize: 11,
            color: "#888",
            background: "#f5f3ef",
            border: "0.5px solid #e0ddd8",
            borderRadius: 6,
            padding: "2px 8px",
          }}
        >
          PAI/2024/0053
        </span>
        {dataActualizacao && (
          <span
            style={{
              fontSize: 11,
              color: "#888",
              marginLeft: "auto",
            }}
          >
            Actualizado {dataActualizacao}
          </span>
        )}
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          borderBottom: "0.5px solid #e0ddd8",
          marginBottom: 20,
          overflowX: "auto",
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTabActiva(t.id)}
            style={{
              padding: "6px 14px",
              fontSize: 13,
              color: tabActiva === t.id ? VP.copper : "#888",
              fontWeight: tabActiva === t.id ? 500 : 400,
              borderBottom: `2px solid ${tabActiva === t.id ? VP.copper : "transparent"}`,
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tabActiva === t.id ? VP.copper : "transparent"}`,
              cursor: "pointer",
              whiteSpace: "nowrap",
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Visão Geral */}
      {tabActiva === "visao" && (
        <div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 10,
              marginBottom: 20,
            }}
          >
            <KpiCard
              label="Preço mediano"
              valor={precoUlt ? fmt(precoUlt.Valor) : "—"}
              unidade="€/m²"
              delta={precoUlt?.Período}
            />
            <KpiCard
              label="Renda mediana"
              valor={rendaUlt ? fmt(parseFloat(rendaUlt.Valor), 2) : "—"}
              unidade="€/m²/mês"
              delta={rendaUlt?.Período}
            />
            <KpiCard
              label="IPH var. anual"
              valor={iphUlt ? fmtPct(iphUlt.Valor) : "—"}
              delta={iphUlt?.Período}
              cor={VP.coral}
            />
            <KpiCard
              label="Novo crédito"
              valor={creditoUlt ? fmt(creditoUlt.Valor) : "—"}
              unidade="M€"
              delta={creditoUlt?.Período}
            />
            <KpiCard
              label="Euribor 12M"
              valor={euriborUlt ? fmtPct(euriborUlt.Valor) : "—"}
              delta={euriborUlt?.Período}
            />
            <KpiCard
              label="Transacções"
              valor={transUlt ? fmt(transUlt.Valor) : "—"}
              unidade="fogos"
              delta={transUlt?.Período}
            />
          </div>

          {/* IPA resumo na visão geral */}
          {ipa.length > 0 && (
            <>
              <SecHeader>IPA — Índice de Pressão de Acessibilidade</SecHeader>
              <IPAPanel ipaData={ipa} />
            </>
          )}
        </div>
      )}

      {/* Tab: IPA */}
      {tabActiva === "ipa" && (
        <div>
          <div
            style={{
              fontSize: 12,
              color: "#888",
              lineHeight: 1.6,
              marginBottom: 20,
              padding: "12px 14px",
              background: "#f8f6f2",
              borderRadius: 8,
            }}
          >
            <strong style={{ color: "#1a1a1a" }}>
              IPA — Índice de Pressão de Acessibilidade.
            </strong>{" "}
            Painel de três rácios independentes. Número sintético único quando a
            metodologia estiver calibrada por comparação com dados BdP.
          </div>
          <IPAPanel ipaData={ipa} />
        </div>
      )}

      {/* Tab: Modelo DPW */}
      {tabActiva === "dpw" && (
        <div>
          <div
            style={{
              fontSize: 12,
              color: "#888",
              lineHeight: 1.6,
              marginBottom: 20,
              padding: "12px 14px",
              background: "#f8f6f2",
              borderRadius: 8,
            }}
          >
            <strong style={{ color: "#1a1a1a" }}>
              Modelo Di Pasquale-Wheaton — 4 Quadrantes.
            </strong>{" "}
            Representa o equilíbrio estrutural do mercado residencial em quatro
            dimensões interdependentes: mercado de uso (renda), capitalização
            (preço), nova construção e ajuste de stock. O ponto laranja é o
            equilíbrio observado com os dados mais recentes.
          </div>
          <div
            style={{
              background: "#fff",
              border: "0.5px solid #e0ddd8",
              borderRadius: 12,
              padding: "16px",
            }}
          >
            <DPWChart dpwData={dpw} />
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: 8,
              marginTop: 12,
              fontSize: 11,
              color: "#888",
            }}
          >
            {[
              { cor: VP.copper, label: "Q1 · Mercado de Uso", desc: "Stock → Renda" },
              { cor: VP.teal, label: "Q2 · Capitalização", desc: "Renda → Preço" },
              { cor: VP.blue, label: "Q3 · Oferta de Construção", desc: "Preço → Nova Construção" },
              { cor: VP.amber, label: "Q4 · Ajuste de Stock", desc: "Nova Construção → Stock" },
            ].map((l) => (
              <div
                key={l.label}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <div
                  style={{
                    width: 14,
                    height: 3,
                    background: l.cor,
                    borderRadius: 2,
                    flexShrink: 0,
                  }}
                />
                <span>
                  <strong style={{ color: "#555" }}>{l.label}</strong> — {l.desc}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rodapé */}
      <div
        style={{
          marginTop: 28,
          paddingTop: 12,
          borderTop: "0.5px solid #e0ddd8",
          fontSize: 11,
          color: "#aaa",
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        {["INE", "Banco de Portugal", "BCE", "Censos 2021"].map((s) => (
          <span
            key={s}
            style={{
              background: "#f5f3ef",
              border: "0.5px solid #e0ddd8",
              borderRadius: 100,
              padding: "2px 8px",
            }}
          >
            {s}
          </span>
        ))}
        <span style={{ marginLeft: "auto" }}>
          Value Point · PAI/2024/0053 · Sem ruído. Com dados.
        </span>
      </div>
    </div>
  );
}
