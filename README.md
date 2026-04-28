# 🧠 BrainRoot: AI-Powered "Second Brain"

BrainRoot is a sophisticated personal knowledge management platform designed to help you capture, connect, and recall information using state-of-the-art AI. It transforms flat notes into a living, interactive knowledge graph.

**Institution**: GL Bajaj Institute of Technology & Management  
**Team**: Sanyam Garg & Team  
**Supervisor**: Ms. Akanksha  
**Status**: 🚀 Production Ready

---

## ✨ Core Features

### 🕸️ Neural Knowledge Graph
- **Interactive D3-Force Layout**: Experience your ideas as an organic, self-organizing neural network.
- **Relationship Mapping**: Automatically visualizes connections between ideas and tags with high-fidelity curved edges and pulse effects.
- **Deep Context Panel**: Select any node to reveal full metadata, content previews, and temporal data.

### 🔍 Semantic Intelligence
- **Neural Vector Search**: Go beyond keywords. Search for *concepts* using high-dimensional vector embeddings powered by `pgvector`.
- **AI Analyst (RAG)**: Ask questions directly to your knowledge base. The built-in analyst uses Retrieval-Augmented Generation to provide insights from your own notes.
- **Auto-Tagging**: Integrated NLP heuristics automatically categorize your data as you import it.

### 🔌 Seamless Integrations
- **Google Drive**: Import shared documents and folders directly.
- **GitHub**: Sync repositories, READMEs, and Gists into your brain.
- **Web Scraper**: High-fidelity web content extraction with boilerplate removal and automatic structure optimization.
- **Local Uploads**: Direct support for PDF, DOCX, and Text files.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Lucide |
| **Visualization** | D3.js (Force-Directed Graph), React Flow |
| **Backend** | FastAPI (Python 3.11+), Pydantic v2 |
| **Database** | PostgreSQL 16 + `pgvector` extension |
| **AI/ML** | Local Neural Hashing, OpenAI GPT (Optional), BeautifulSoup4 |
| **DevOps** | Docker, Docker Compose, Nginx |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Docker & Docker Compose**: Essential for containerized deployment.
- **Memory**: Minimum 4GB RAM recommended for smooth graph simulations.

### 2. Launch the System
Navigate to the project root and run:

```bash
# Start all services (Database, API, Frontend)
docker-compose -f docker-compose.dev.yml up -d --build
```

### 3. Access Points
- **Web Interface**: [http://localhost:3000](http://localhost:3000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database Access**: `localhost:5432` (sb/sbpass)

---

## 📁 Project Architecture

```bash
BrainRoot/
├── apps/
│   ├── api-gateway/          # FastAPI Neural Engine
│   │   ├── app/
│   │   │   ├── api/v1/       # Neural endpoints (Analyst, Graph, Integrations)
│   │   │   ├── services/     # Business logic & Scraping engines
│   │   │   └── core/         # Security & Vector Config
│   └── frontend/             # High-Fidelity React UI
│       ├── src/
│       │   ├── pages/        # Interactive GraphView, Dashboard, Integrations
│       │   └── components/   # Modern UI components (NoteCard, DetailsPanel)
├── infra/
│   └── postgres/             # Persistence Layer
│       └── init/             # Auto-migrations (Vector Setup, Schemas)
└── docker-compose.dev.yml    # Full Stack Orchestration
```

---

## 🔧 Configuration & Tuning

### Environment Variables
Located in `docker-compose.dev.yml` (for Docker) or local `.env` files:
- `SECRET_KEY`: Used for JWT security.
- `OPENAI_API_KEY`: (Optional) If provided, the AI Analyst uses GPT-4 for deeper insights. Otherwise, it uses a local heuristic analyzer.

### Database Initialization
The system automatically initializes the following on first boot:
- **pgvector**: Enables high-dimensional vector math.
- **HNSW Indexes**: Optimized for sub-millisecond similarity searches across thousands of notes.

---

## 🧪 Development Workflow

### Adding New Features
1. **API**: Add routes in `apps/api-gateway/app/api/v1/`.
2. **Logic**: Implement handlers in `apps/api-gateway/app/services/`.
3. **UI**: Create components in `apps/frontend/src/components/`.

### Rebuilding After Changes
```bash
docker-compose -f docker-compose.dev.yml up -d --build api frontend
```

---

## 🛡️ Security
- **JWT Isolation**: Every user's knowledge base is logically isolated at the database level.
- **Encrypted Persistence**: Passwords hashed with Bcrypt; tokens use HS256.
- **CORS & Rate Limiting**: Production-grade protection against common web threats.

---

**BrainRoot** — *Turn your scattered information into a structured universe of knowledge.*
