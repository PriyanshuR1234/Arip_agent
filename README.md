# 🤖 ARIP: Autonomous AI Resource Intelligence Platform

![tag:asi1-llm-agent](https://img.shields.io/badge/asi1-3D8BD3)
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

ARIP is an autonomous **AI Resource Intelligence Agent** natively discoverable through **ASI:One**. It continuously analyzes a developer's AI ecosystem, predicts future usage, optimizes model selection, and autonomously executes cost-efficient AI workflows through a collaborative internal multi-agent system.

Rather than just another token tracking dashboard, ARIP acts as a proactive **AI Decision-Making Agent** integrated directly into the chat ecosystem.

---

## 🌟 Why ARIP?

As developers increasingly rely on AI platforms, tracking usage across multiple ecosystems (VSCode, browser, etc.) becomes chaotic. **ARIP eliminates the need for an external website.** You communicate with ARIP directly via **ASI:One**. 

When you ask:
> *"How can I reduce my AI costs?"* or *"I have a $20 monthly budget, which AI should I use for today's work?"*

ARIP doesn't just reply with a static chart. It dynamically:
1. **Reads** previous usage telemetry.
2. **Predicts** today's token consumption.
3. **Simulates** multiple routing strategies (e.g., using Gemini Flash for code vs. GPT-4o for reasoning).
4. **Calculates** when your budget will be exhausted.
5. **Returns** a definitive, actionable cost-saving strategy directly inside the ASI chat.

---

## 🏗️ System Architecture: The "Agent of Agents"

ARIP leverages true **Multi-Agent Orchestration**. While registered as a single main agent on Agentverse (for seamless discovery), internally it orchestrates a specialized crew of LangGraph/CrewAI agents:

User ➔ **ASI:One Chat** ➔ **ARIP Agent** ➔ **Internal Multi-Agent System** ➔ Result ➔ **ASI:One Chat**

### The Internal Crew:
- 👁️ **Observer Agent:** Ingests raw telemetry and usage data.
- 🧠 **Memory Agent:** Stores and retrieves historical usage patterns.
- 🔮 **Prediction Agent:** Forecasts token burn rates and budget trajectories.
- ⚖️ **Evaluation & Optimization Agent:** Analyzes waste and calculates alternative routing costs.
- 🔀 **Routing Agent:** Executes the optimal model routing strategy.

---

## 🧰 Tool Execution

To make ARIP infinitely extensible, the traditional user interfaces (Browser Extensions, IDE Extensions) and internal engines are transformed into **TOOLS** that the agent can autonomously execute.

When ASI asks ARIP to optimize costs, ARIP executes tools such as:
- `analyze_usage()`
- `predict_cost()`
- `optimize_tokens()`
- `recommend_model()`
- `generate_report()`
- `forecast_budget()`

*Example: Your VSCode IDE Extension is no longer just a plugin; it is a live telemetry **Tool** that feeds structural data straight to ARIP.*

---

## 🚀 Hackathon Fit (ASI One Special Track)

ARIP was engineered from the ground up to match the core criteria of the ASI One Challenge:
- ✅ **Discoverable through Agentverse:** Registered with comprehensive agent metadata.
- ✅ **Usable directly from ASI:One chat:** Zero external websites required for the primary workflow.
- ✅ **Tool Execution:** Treats browser/IDE extensions and backend engines as callable tools.
- ✅ **Multi-Agent Orchestration:** Complex internal planning across specialized sub-agents.
- ✅ **Real-world Developer Problem:** Fixes the chaotic, unpredictable nature of AI spending.

---

## 📦 Local Development

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment Configuration (.env):**
   ```ini
   ASI_API_KEY=your_agentverse_mailbox_api_key
   GEMINI_API_KEY=your_gemini_api_key
   SUPABASE_KEY=your_supabase_anon_public_key
   SEED_PHASE=your_agent_seed_phrase
   ILABS_AGENTVERSE_API_KEY=your_agentverse_api_key
   ```
3. **Run the Agent:**
   ```bash
   python3 Arip_agent.py
   ```
   *Note: Upon startup, the agent will automatically register its manifesto with Agentverse using `ILABS_AGENTVERSE_API_KEY`.*
# Arip_agent
