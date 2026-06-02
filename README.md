# VP · Real Estate Intelligence — Guia de Implementação

## Arquitectura da solução

```
INE API JSON  ──┐
BPStat API    ──┼──► vp_collect.py ──► Google Sheet ──► value-point.pt
BCE SDMX API  ──┘         ↑
                    GitHub Actions
                    (corre sozinho
                     trimestralmente)
```

**Custo total: zero.** GitHub Actions gratuito (2000 min/mês), Google Sheets gratuito.

---

## Fase 1 — Preparar o repositório GitHub

### 1.1 Criar repositório privado

1. Entrar em [github.com](https://github.com) com a tua conta
2. Clicar **New repository**
3. Nome: `vp-intelligence-data`
4. Seleccionar **Private**
5. Clicar **Create repository**

### 1.2 Carregar os ficheiros

```bash
# Na tua máquina, na pasta onde tens os ficheiros:
git init
git add vp_collect.py .github/
git commit -m "feat: VP Intelligence data pipeline"
git branch -M main
git remote add origin https://github.com/SEU_UTILIZADOR/vp-intelligence-data.git
git push -u origin main
```

---

## Fase 2 — Configurar Google Cloud e Google Sheets

### 2.1 Criar projecto no Google Cloud Console

1. Ir a [console.cloud.google.com](https://console.cloud.google.com)
2. Clicar no selector de projecto (topo) → **New Project**
3. Nome: `VP Intelligence`
4. Clicar **Create**

### 2.2 Activar as APIs necessárias

1. Menu → **APIs & Services** → **Library**
2. Pesquisar e activar:
   - **Google Sheets API**
   - **Google Drive API**

### 2.3 Criar Service Account

1. Menu → **APIs & Services** → **Credentials**
2. Clicar **Create Credentials** → **Service Account**
3. Nome: `vp-data-bot`
4. Clicar **Create and Continue** → **Done**
5. Clicar na Service Account criada
6. Separador **Keys** → **Add Key** → **Create new key** → **JSON**
7. Guardar o ficheiro `credentials.json` na mesma pasta do `vp_collect.py`

> ⚠️ Nunca colocar o `credentials.json` no repositório Git.  
> Adicionar ao `.gitignore`: `echo "credentials.json" >> .gitignore`

### 2.4 Criar a Google Sheet

1. Ir a [sheets.google.com](https://sheets.google.com)
2. Criar nova folha → Nome: `VP Market Intelligence`
3. Copiar o ID do URL:  
   `https://docs.google.com/spreadsheets/d/`**`1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`**`/edit`
4. Partilhar a folha com o email da Service Account:
   - Clicar **Partilhar** → colar o email (formato: `vp-data-bot@vp-intelligence.iam.gserviceaccount.com`)
   - Dar permissão **Editor**
5. Para o site conseguir ler: **Partilhar** → **Qualquer pessoa com o link** → **Visualizador**

### 2.5 Actualizar o SHEET_ID no script

Editar `vp_collect.py`, linha 19:
```python
SHEET_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"  # Substituir pelo teu ID
```

---

## Fase 3 — Configurar os Secrets do GitHub Actions

Os secrets guardam informação sensível fora do código.

1. No repositório GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Clicar **New repository secret** duas vezes:

| Nome | Valor |
|------|-------|
| `GOOGLE_CREDENTIALS_JSON` | Conteúdo completo do `credentials.json` (copiar e colar) |
| `VP_SHEET_ID` | ID da Google Sheet (ex: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`) |

---

## Fase 4 — Registar no BPStat (Banco de Portugal)

O BPStat tem uma API pública mas requer chave para acesso continuado.

1. Ir a [bpstat.bportugal.pt](https://bpstat.bportugal.pt)
2. Clicar **Área de utilizadores** → **Registo**
3. Preencher com dados da Win Win Lda ou pessoais
4. Após confirmação de email, ir a **O meu perfil** → **API Key**
5. Copiar a chave e editar `vp_collect.py`, linha ~115:
   ```python
   headers = {"Authorization": "Bearer TUA_CHAVE_AQUI", ...}
   ```
6. Adicionar a chave como Secret no GitHub: `BPSTAT_API_KEY`

---

## Fase 5 — Teste local

```bash
# Instalar dependências
pip install requests gspread google-auth pandas openpyxl

# Primeiro teste: apenas mostra dados no terminal, não escreve na Sheet
python vp_collect.py
# (alterar WRITE_TO_SHEET = False para dry-run)

# Teste completo com escrita na Sheet
# (garantir que SHEET_ID e credentials.json estão configurados)
python vp_collect.py
```

Se tudo correr bem, vês algo como:
```
============================================================
VP · Real Estate Intelligence — Recolha de Dados
Início: 2026-06-02 10:00:00
============================================================

[1/4] INE — Recolha de indicadores
  → Preço mediano habitação (varcd=0012234)
     Último: 2025T4 = 2076.0 €/m²
  → Renda mediana novos contratos (varcd=0012571)
     Último: 2025T1 = 8.22 €/m²/mês
  ...

[4/4] Cálculo IPA e DPW
  IPA Rácio A (Compra): 48.3% — Pressão crítica
  IPA Rácio B (Arrendamento): 54.6%
  IPA Rácio C (Divergência): +46.2 p.p.
  DPW Equilíbrio: Preço 1800 €/m² · NC 26400 fogos/ano

[Saída] Guardar dados
  ✓ Dados guardados em vp_dados.json
  ✓ VP_Indicadores → 847 observações escritas
  ✓ VP_IPA → 7 rácios escritos
  ✓ VP_DPW → 81 pontos escritos
  ✅ Google Sheet actualizada
```

---

## Fase 6 — Integrar no site Lovable

### 6.1 Activar Google Sheets API Key (só leitura, pública)

1. Google Cloud Console → **APIs & Services** → **Credentials**
2. **Create Credentials** → **API Key**
3. Clicar na chave criada → **API restrictions** → restringir a **Google Sheets API**
4. Copiar a chave

### 6.2 Configurar variável de ambiente no Lovable

No Lovable, ir a **Settings** → **Environment Variables**:

| Variável | Valor |
|----------|-------|
| `VITE_GOOGLE_API_KEY` | A chave de API só-leitura |
| `VITE_VP_SHEET_ID` | ID da Google Sheet |

### 6.3 Adicionar o componente

1. No editor Lovable, criar ficheiro `src/components/MarketIntelligence.jsx`
2. Colar o conteúdo do ficheiro `MarketIntelligence.jsx`
3. Na página onde queres o dashboard (ex: `src/pages/Intelligence.jsx`):

```jsx
import MarketIntelligence from "@/components/MarketIntelligence";

export default function IntelligencePage() {
  return (
    <div className="container mx-auto px-4 py-12">
      <MarketIntelligence 
        sheetId={import.meta.env.VITE_VP_SHEET_ID} 
      />
    </div>
  );
}
```

---

## Fase 7 — Executar o workflow manualmente

Para testar o GitHub Actions antes da data automática:

1. Repositório GitHub → **Actions**
2. **VP · Recolha Trimestral de Dados**
3. **Run workflow** → seleccionar `dry_run: false` → **Run workflow**
4. Verificar logs e confirmar que a Sheet foi actualizada

---

## Cadência automática

O workflow corre automaticamente no **1.º dia de Janeiro, Abril, Julho e Outubro** às 08:00 UTC.

Para mudar: editar `quarterly_update.yml`, linha do `cron`:
```yaml
# Exemplos:
- cron: "0 8 1 1,4,7,10 *"   # 1.º dia do trimestre
- cron: "0 8 15 1,4,7,10 *"  # Dia 15 do 1.º mês de cada trimestre
```

---

## Indicadores manuais (CI/RICS — fontes pagas)

Os 3-4 indicadores de fontes pagas (Confidencial Imobiliário, RICS Housing Survey) 
continuam a ser inseridos manualmente na Google Sheet, directamente nas colunas correctas 
do separador `VP_Indicadores`. O script detecta e não sobrescreve linhas com fonte `CI` ou `RICS`.

---

## Estrutura de ficheiros

```
vp-intelligence-data/
├── vp_collect.py              # Script principal de recolha
├── MarketIntelligence.jsx     # Componente React para o site
├── vp_dados.json              # Último output (gerado automaticamente)
├── credentials.json           # ⚠️ NÃO colocar no Git (.gitignore)
├── .gitignore
├── README.md
└── .github/
    └── workflows/
        └── quarterly_update.yml  # GitHub Actions
```

---

## Troubleshooting

**Erro 403 ao chamar INE API**  
→ O INE bloqueia User-Agents genéricos. O script usa `VP-RealEstateIntelligence/1.0`.  
→ Se continuar, adicionar header `Referer: https://value-point.pt`.

**Erro de autenticação Google Sheets**  
→ Confirmar que a Sheet está partilhada com o email da Service Account.  
→ Confirmar que o `credentials.json` é do projecto correcto.

**Dados não aparecem no site**  
→ Confirmar que a Sheet está partilhada publicamente (só leitura).  
→ Confirmar `VITE_GOOGLE_API_KEY` e `VITE_VP_SHEET_ID` no Lovable.

**Valores nulos para alguns indicadores**  
→ Os `varcd` do INE podem mudar quando o INE actualiza metodologias.  
→ Verificar em `smi.ine.pt` se o código ainda está activo.
