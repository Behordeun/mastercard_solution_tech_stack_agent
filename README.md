# 🧠 TSA145: Agentic AI Solution Architect

**TSA145** is an Agentic AI assistant that guides users through designing a context-aware, domain-aligned, and strategically justified tech stack — acting not just as an information provider, but a **trusted advisor**.

---

## 🚀 Key Features

- ✅ **4-Phase Advisory Flow**:
  1. **Program & Initiative Intake**
  2. **Requirement Gathering Across 23 Pillars**
  3. **Summary of User Requirements**
  4. **LLM-Powered Technology Stack Recommendation**

- ✅ **128-question CSV-driven checklist**
- ✅ **LangGraph + LangChain** based execution flow
- ✅ **FAISS-powered knowledge base retrieval**
- ✅ **PostgreSQL-backed context persistence**
- ✅ **Clear, empathetic, and structured user guidance**
- ✅ **LLM generates tailored stack + reasoning explanation**

---

## 📁 Project Structure

```text
.
├── __init__.py
├── about.md
├── alembic.ini
├── LICENSE
├── poetry.lock
├── pyproject.toml
├── README.md
└── src
    ├── api
    │   ├── data_model.py
    │   ├── logs_router.py
    │   └── route.py
    ├── config
    │   ├── appconfig.py
    │   ├── db_setup.py
    │   └── settings.py
    ├── database
    │   ├── pd_db.py
    │   └── schemas.py
    ├── error_trace
    │   └── errorlogger.py
    ├── logs
    │   ├── error.log
    │   ├── info.log
    │   └── warning.log
    ├── main.py
    ├── services
    │   ├── manager.py
    │   ├── model.py
    │   └── techstack_agent_module
    │       ├── agent.py
    │       ├── data
    │       │   └── Pillars and Key Questions-Final.csv
    │       ├── kb_vectorstore
    │       │   ├── index.faiss
    │       │   └── index.pkl
    │       ├── prompts
    │       │   ├── instruction-2.yaml
    │       │   ├── instruction-3.yaml
    │       │   ├── instruction.yaml
    │       │   └── instructions-4.yaml
    │       └── toolskit.py
    ├── templates
    │   └── index.html
    └── utilities
        ├── gen_mermaid.py
        ├── helpers.py
        ├── Printer.py
        └── vectorstore_builder.py
```

---

## 🧑‍💼 User Flow

1. **User says “Hello”**
2. TSA145 asks:
   - "🧭 What solution are you building?"
   - "🌍 What domain are you solving for? (e.g., Health, Education)"
3. TSA145 proceeds to ask **128 pillar questions** from the checklist (spread across 23 categories).
4. Once complete, TSA145 summarizes all the responses and asks:
   > “Does this capture your requirements accurately?”
5. Upon confirmation, TSA145 generates:
   - 📋 A markdown-formatted **technology stack**
   - 💡 Justifications for each decision (LLM-generated)

---

## 🧠 Core Technologies

| Tool        | Purpose                                  |
|-------------|------------------------------------------|
| LangChain   | LLM chaining, memory, and prompt logic   |
| LangGraph   | Agent state & node orchestration         |
| FAISS       | Local vector search for knowledge base   |
| OpenAI      | LLM (GPT-4 or GPT-3.5 Turbo)              |
| SQLAlchemy  | DB ORM                                   |
| Alembic     | Database migrations                      |
| FastAPI     | Backend API                    |
| PostgreSQL  | Persistent storage for user sessions     |

---

## 🛠️ Setup Instructions

### 1. Clone the Repo

```bash
git clone https://github.com/Behordeun/mastercard_solution_tech_stack_agent.git
cd mastercard_solution_tech_stack_agent
```

### 2. Install Dependencies

```bash
poetry install
```

### 3. Set Up Environment Variables

**Create a .env file:** copy the content of the .example.env file and replace the placeholder values with actual values.

```bash
cp .example.env .env
```

### 4. Set up the poetry environment

- Install poetry:

```bash
python3.12 -m install poetry
```

- Specify the desired python version (in our case we're using python3.12)

```bash
poetry env use python3.12
```

- Install the required libraries:

```bash
poetry install
```

### 4. Set Up the Database

- Initialize the database setup

```bash
poetry run alembic init migrations
```

- Commit the database changes

```bash
poetry run alembic revision --autogenerate -m "First Commit"
```

- Enforce the database actions

```bash
poetry run alembic upgrade head
```

### 5. Build the Vectorstore (only once)

```bash
poetry run python
```

```python
from src.utilities.vectorstore_builder import build_faiss_vectorstore
build_faiss_vectorstore("docs/kb.txt", persist_path="src/services/techstack_agent_module/kb_vectorstore")
```

### 6. Run the App (FastAPI)

```bash
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**NB:** Do not use `--reload` in production

⸻

## 🧪 Testing It

Once live at <http://localhost:8000>, use your frontend or Postman to test the /api/v1/chat-ai endpoint.

Example input:

{
  "roomId": "12345",
  "message": "Hello"
}

Expected response:

{
  "sender": "AI",
  "message": "Hello! I'm TSA145, your Solution Architect assistant..."
}

⸻

## 🧩 Extensibility Ideas

- 🔁 Add user authentication for multi-session support
- 💬 Integrate streaming responses via WebSockets or SSE
- 📄 Export summary + stack as downloadable PDF
- 📥 Let users upload docs to extend vectorstore
- 📊 Log analytics on common stack patterns across sectors

⸻

## 📜 License

This project is licensed under the MIT License.

⸻

## 🤝 Contributions

If you’d like to contribute pillar questions, domain-specific stack patterns, or extensions — feel free to open a PR or submit issues.

⸻

## ✨ Built With Purpose

TSA145 helps technical and non-technical users design thoughtful, impactful digital solutions that align with real-world goals — not buzzwords.

“Great architecture starts with great questions.” — TSA145
