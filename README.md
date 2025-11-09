# 巴菲特風格多代理 MVP
本儲存庫實作一個可投入生產的、受巴菲特啟發的美股研究管線。系統使用 LangGraph 協作專職代理，完成輸入正規化、候選篩選、基本面蒐集、新聞整合、內在價值評估、風險評估，並輸出精簡的 Markdown 研究報告。
## 功能
- **LangGraph 編排**：決定性狀態機，按序在 InputSupervisor → CandidateScreener → FundamentalsAnalyst/NewsIntelligence（並行）→ ValuationModel → RiskAssessment → SummaryAgent → MarkdownReporter 之間傳遞結果。

### 流程步驟詳解

每個代理只負責單一職責；狀態鍵以增量方式合併，避免並行覆寫。

1. **InputSupervisor**（`agents/input_supervisor.py`）
    - 目的：正規化使用者輸入的 tickers（大小寫、去重），可套用 `max_candidates` 上限。
    - 輸入鍵：`params.tickers`、`params.max_candidates`
    - 輸出鍵：`candidates`（初始可能為空）
    - 邊界情況：未提供 tickers 時，保留空清單交由後續 Screener 處理。

2. **CandidateScreener**（`agents/candidate_screener.py`）
    - 目的：透過產業與關鍵字擴展候選（Yahoo Finance 搜尋 + 排行）。
    - 輸入鍵：`params.sector`、`params.query`、既有 `candidates`（種子）
    - 輸出鍵：`candidates`（排序且唯一）
    - 回退：若 API 無結果但有種子，則沿用種子。

3. **FundamentalsAnalyst**（`agents/fundamentals_analyst.py`）
    - 目的：抓取基本面與 1 年價格歷史；計算巴菲特指標（ROIC、毛利率、營益率、FCF CAGR、Debt/FCF）。
    - 輸入鍵：`candidates`
    - 輸出鍵：`fundamentals`（每檔含 `info`、`metrics`、`price_history`）
    - 健壯性：缺失數值時以 None 表示，避免拋錯。

4. **NewsIntelligence**（`agents/news_intelligence.py`）【與 Fundamentals 並行】
    - 目的：彙整近期新聞與關鍵字搜尋；去重、視窗篩選、摘要、情緒、主題、時間軸。
    - 輸入鍵：`candidates`、`params.query`、`params.news_window_days`、`params.max_news`
    - 輸出鍵：`news_bundle`（每檔含 bullets、sentiment、topics、timeline、sources）
    - 回退：若無項目，提供預設提示。

5. **ValuationModel**（`agents/valuation_model.py`）
    - 目的：結合 DCF 與倍數估值，得到區間與安全邊際（MOS）。
    - 輸入鍵：`fundamentals`
    - 輸出鍵：`valuation`（每檔含 price、intrinsic_value_range、margin_of_safety）
    - 假設：折現率 10%、終端增長 2%、終端倍數 15x。

6. **RiskAssessment**（`agents/risk_assessment.py`）
    - 目的：保守規則過濾（高槓桿 vs FCF、FCF 負增長）與倉位限制。
    - 輸入鍵：`fundamentals`、`valuation`
    - 輸出鍵：`risk`（flags、allowed、position_weight、margin_of_safety）
    - 政策：僅在 MOS > 0 且槓桿可接受時給予最大倉位（預設 10%）。

7. **SummaryAgent**（`agents/summary_agent.py`）
    - 目的：以單一 LLM（或啟發式回退）整合估值、風險與新聞資訊，輸出精簡的投資重點與追蹤建議。
    - 輸入鍵：`fundamentals`、`valuation`、`risk`、`news_bundle`
    - 輸出鍵：`summary_insight`（每檔含 summary）
    - 回退：無 OpenAI 金鑰時以啟發式組裝 3–5 條條列；仍保留 MOS、情緒、風險旗標。

8. **MarkdownReporter**（`agents/markdown_reporter.py`）
     - 目的：為每檔股票組裝最終 Markdown 報告。
     - 輸入鍵：前述所有輸出；若 `fundamentals` 缺失則以 `candidates` 骨架輸出。
     - 輸出鍵：`report_path`（最後產生的路徑）
     - 章節：Executive Summary、Snapshot、Business Summary、Economic Moat、Key Financials、Intrinsic Valuation、Risk Factors、News & Text Intelligence、Summary Insight。

### 資料流與 Join Gate
並行：FundamentalsAnalyst 與 NewsIntelligence 於 CandidateScreener 後並行執行。Join Gate 確保在進入 SummaryAgent 前，同時具備新聞與風險（風險需估值先完成）。SummaryAgent 取代過去的 Strategy / Narrative / Tool 三 LLM 節點，降低延遲與並行寫入衝突。最後交由 Reporter 輸出報告。

### 狀態鍵總覽
`params`、`candidates`、`fundamentals`、`news_bundle`、`valuation`、`risk`、`summary_insight`、`report_path`

所有節點只回傳增量（delta，更新子集），以避免並行寫入衝突。


## 架構（視覺化）

```mermaid
flowchart TD
    A[START] --> B[InputSupervisor]
    B --> C[CandidateScreener]
    C --> D[FundamentalsAnalyst]
    C --> E[NewsIntelligence]
    D --> F[ValuationModel]
    F --> G[RiskAssessment]
    E --> H[Join Gate]
    G --> H
    H --> I[SummaryAgent]
    I --> L[MarkdownReporter]
    L --> M[END]

    %% Notes
    classDef join fill:#f8f8f8,stroke:#999,stroke-dasharray: 3 3
    class H join
```

簡述：
- Screener 之後並行執行基本面與新聞管線，於 Join Gate 匯流後直接進入 SummaryAgent（單一 LLM / 啟發式）。
- Reporter 支援在缺基本面時以 candidates 輸出骨架報告（容錯）。

## 快速開始
1. 安裝相依套件：`pip install -r requirements.txt`
2. （選用）啟用 OpenAI LLM 多代理，在環境變數設定金鑰：

```bash
export OPENAI_API_KEY=sk-your-key
# optional: override model
export OPENAI_MODEL=gpt-4o-mini
```

3. 執行管線：

```bash
python main.py --tickers AAPL,MSFT --news-window 14 --max-news 30
```

4. 在 `reports/` 檢視輸出（例如 `reports/20251109_AAPL.md`）。
    - 若未設定 `OPENAI_API_KEY`，SummaryAgent 會回退為啟發式摘要（仍包含 MOS / 風險 / 情緒條列）。
## 測試

執行完整套件：

```bash
pytest
```

## 設定

環境變數：

- `REPORTS_DIR`：覆寫報告輸出目錄。

也可在呼叫 `graph.run_pipeline` 時，於輸入字典中直接提供這些值。

## 專案結構

```
README.md
requirements.txt
main.py
agents/
    input_supervisor.py
    candidate_screener.py
    fundamentals_analyst.py
    news_intelligence.py
    valuation_model.py
    risk_assessment.py
    summary_agent.py
    markdown_reporter.py
graph/
    orchestrator.py
tools/
    yfinance_client.py
    mcp_yfinance.py (compat shim)
valuation/
    dcf.py
    multiples.py
nlp/
    news_pipeline.py
reports/
    .gitkeep
tests/
    test_tools_news.py
    test_nlp_news.py
    test_valuation.py
    test_e2e.py
```
