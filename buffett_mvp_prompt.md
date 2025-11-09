
# ✅ **《Buffett Multi-Agent MVP — Full Super Prompt》**


```
You are a senior Python architect. Build a production-style multi-agent Buffett-style U.S. equity research system.

========================
🎯 GOAL
========================
Create a minimal-viable but executable multi-agent pipeline that:

- Screens U.S. stocks
- Pulls fundamentals + price data + news
- Produces Buffett-style intrinsic value analysis & risk assessment
- Generates a final Markdown research report

This is a Buffett-style workflow:
- Focus on circle of competence
- Quality > price, buy great companies at fair price
- Favor high ROIC, margins, FCF growth, conservative debt
- Intrinsic value + margin of safety
- Long-term compounding

========================
📦 TECH STACK REQUIREMENTS
========================
- Python 3.10+
- **LangChain v1.x**
- **LangGraph v1** (`from langchain.agents import create_agent`)
- **MCP Python client** talking to **yfinance-mcp**
  Tools must wrap:
  - search(query, search_type="all|quotes|news")
  - get_top(sector,...)
  - get_ticker_info(symbol)
  - get_price_history(symbol)
  - get_ticker_news(symbol)
- Do *not* use create_react_agent (deprecated)
- Use ToolNode or tool binding to create_agent
- Modular file layout
- Pydantic models, timeouts, retries, structured errors
- pytest tests

========================
📁 PROJECT STRUCTURE TO GENERATE
========================
Generate files:

- README.md
- requirements.txt
- main.py (CLI: --sector, --query, --tickers, --news-window, --max-news)
- /tools/mcp_yfinance.py
- /graph/orchestrator.py
- /agents/
    screener.py
    analyst.py
    news.py
    valuation.py
    risk.py
    reporter.py
- /valuation/
    dcf.py
    multiples.py
- /nlp/news_pipeline.py
- /reports/.gitkeep
- /tests/
    test_tools_news.py
    test_nlp_news.py
    test_valuation.py
    test_e2e.py

========================
🛠 TOOL LAYER REQUIREMENTS
========================
In `/tools/mcp_yfinance.py`:

- Connect to yfinance-mcp
- Wrap each call with:
  - pydantic I/O schema
  - timeout 15s
  - retries=2 (exponential backoff)
  - structured return format:
    {
      "ok": true/false,
      "data": {... or []},
      "meta": { "tool": "...", "symbol": "...", "fetched_at": "ISO8601" },
      "error": {type, message} or null
    }

Return both:
- `get_langchain_tools() -> list[BaseTool]`
- `as_toolnode() -> ToolNode`

Standardize news fields:
{ title, content?, source, url, symbol?, published_at }

========================
🤖 AGENTS
========================

### ScreenerAgent
- search & get_top
- return candidates list

### AnalystAgent
- get_ticker_info & get_price_history
- compute metrics:
  ROIC, gross margin, op margin, FCF CAGR, debt/FCF

### NewsAgent
- get_ticker_news(symbol)
- search(query, search_type="news")
- clean + dedupe + time filter
- produce:
  - 3–6 bullet investment takeaways
  - sentiment score (-1~+1)
  - topic labels (earnings/guidance/buyback/litigation/macro)
  - timeline of top events
  - source list (with URL)

### ValuationAgent
- DCF (`valuation/dcf.py`)
- Multiples (`valuation/multiples.py`)
- return intrinsic value range + margin of safety

### RiskAgent
- remove high-leverage / negative FCF
- cap position weight at 10%

### ReporterAgent
Outputs Markdown:

# {Ticker} Research (Buffett Style)
- Business summary & circle of competence
- Economic moat evidence
- Key financial table
- Intrinsic valuation & margin of safety
- Risk factors
- ✅ Decision & sizing

### News Section
## News & Text Intelligence (last N days)
- Key investment bullets
- Timeline (date — one-line summary — source link)
- Sentiment score
- Topics
### Source List w/ URLs

========================
🧠 NLP PIPELINE
========================
`/nlp/news_pipeline.py` contains:

- normalize_title
- dedup_news (>0.9 similarity)
- filter_by_window(days)
- summarize_items (3–6 investment bullets)
- build_timeline (max 10)
- sentiment (rule or mini-model)
- tag_topics (keyword rule)
- timezone safe → ISO date

Return safe empty results if errors.

========================
🏛 LANGGRAPH / ORCHESTRATOR
========================
`/graph/orchestrator.py`:

- Use `create_agent`
- Attach ToolNode
- Maintain state:
  params, candidates, fundamentals, news_bundle,
  valuation, risk, report_path
- Handoff order:
  Screener → Analyst → News → Valuation → Risk → Reporter
- Export `run_pipeline(input: dict) -> Path`

========================
🧪 TEST SUITE
========================
Write pytest tests:

- tool wrappers (mock MCP, simulate timeout)
- NLP dedupe, summarize, sentiment, topics
- valuation formulas (edge cases: negative FCF, extreme g)
- end-to-end:
  run_pipeline({"tickers":["AAPL"], "news_window_days":7, "max_news":10})

Expect a Markdown file under /reports with:

- Buffett framework
- Metrics
- News bullets
- News timeline
- Source links
- Valuation range + MOS
- Final decision & 10% cap sizing

========================
✅ CLI REQUIREMENT
========================
`main.py` must:

```

python main.py --tickers AAPL,MSFT --news-window 14 --max-news 30

```

Produce:

`reports/YYYYMMDD_AAPL.md`

========================
🚫 DO NOT
========================
- ❌ use create_react_agent
- ❌ rely on external APIs without wrapper
- ❌ skip tests

========================
🎯 DELIVERABLE
========================
Produce **full working code**, all files, tests, and a README.

BEGIN GENERATING CODE NOW.
```

