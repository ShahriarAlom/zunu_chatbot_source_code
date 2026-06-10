# Zunu AI Chatbot: Deliverables Package

Welcome to the Zunu AI Chatbot deliverables package. This folder contains all the files, code, sitemaps, and documentation required to deploy and run the chatbot on your hosting environment.

---

## 🗺️ Plug-and-Play System Architecture Overview

The chatbot is designed with a **100% decoupled, plug-and-play architecture** that allows you to embed it on any website layout and integrate it with any administrative panel backend without sharing database connections or session tables.

![Zunu Chatbot System Architecture Map](file:///J:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/chatbot_architecture_sitemap.png)

### Core Interfaces
1. **WebSocket Interface (`/ws/chat`)**: Routes all real-time client-to-bot chat interactions, loads historical chat logs on reconnect, and manages live customer support takeover messaging.
2. **REST API Interface (`/knowledge`)**: Exposes decoupled `GET`, `POST`, and `DELETE` endpoints for managing the knowledge base document records. Your admin dashboard can perform document operations directly over HTTP.

This decoupled layout isolates the databases, allowing the main site to remain completely unaffected by the chatbot's internal MariaDB structure.

---

## 📂 Deliverables Directory Map

This package is organized as follows:

### 1. 📄 Documentation & Sitemaps (`/docs`)
*   **[DEPLOYMENT_GUIDE.md](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/DEPLOYMENT_GUIDE.md):** Step-by-step instructions for production deployment, reverse proxy configurations, widget integration, and JWT authentication.
*   **[FEATURES_AND_TESTING_GUIDE.md](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/FEATURES_AND_TESTING_GUIDE.md):** Detailed overview of system design, database schemas, and copy-paste text scripts for QA verification.
*   **[chatbot_architecture_sitemap.png](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/chatbot_architecture_sitemap.png):** High-resolution system architecture diagram illustrating the backend layers, database interactions, and handoff flows.
*   **[sitemap.html](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/sitemap.html):** An interactive, visual HTML sitemap mapping the chatbot modules, routes, and data pipelines.

### 2. ⚙️ Orchestration & Schema (`/requirements`)
*   **`docker-compose.yml`:** Multi-container orchestration script defining the backend FastAPI service and the chatbot MariaDB database.
*   **`requirements/init-mariadb.sql`:** Database initialization SQL script provisioning tables and setting up `vector(3072)` columns for Gemini embeddings.
*   **`requirements/knowledge_Base_doc/`:** Folder containing the corporate policy documents (`.docx` format) used to build the initial chatbot knowledge base.

### 3. 🐍 Python FastAPI Backend (`/backend`)
*   **`app.py`:** Main ASGI web application defining REST endpoints and WebSockets (`/ws/chat`, `/ws/admin`).
*   **`database.py` & `operational_api.py`:** Handles asynchronous ORM models, URL-encoded database connections, and queries against the website's database.
*   **`rag_pipeline.py` & `retrieval.py`:** Implements text chunking, Google Gemini API embeddings, and native vector similarity searches.
*   **`clean_and_reingest.py`:** CLI utility to automatically clean duplicate database records, verify status, and embed missing policy documents.
*   **`Dockerfile` & `requirements.txt`:** Package dependencies and Docker build configurations.

### 4. 🌐 Frontend Assets (`/frontend`)
*   **`rdr_chatbot.js`:** The plug-and-play JavaScript file for embedding the chatbot widget on the Laravel website.

### 5. 🧪 Testing & Demos (`/demo`)
*   **`test_widget.html`:** A simple HTML sandbox file used to run, preview, and test the chat widget locally.
*   **`support_admin_dashboard_mock_demo.html`:** The fully-functional, production-ready admin panel dashboard, providing local preview capabilities for managing settings, prompts, categories/tags, and session takeover.

### 6. 🛠️ Website Code Alterations (`/laravel-scripts-changed-for-chatbot-deployment`)
*   **[README.md](file:///J:/realdealride-chatbot/ai-chatbot-project/deliverables/laravel-scripts-changed-for-chatbot-deployment/README.md):** Detailed tracking file mapping exactly which files and lines were modified or created inside the Laravel repository.
*   **`app/Helpers/ChatbotHelper.php`**: Reference PHP helper class generating JWT tokens.
*   **`resources/views/layouts/`**: Reference Blade layouts containing chatbot script injections and Dialogflow comment-outs.

---

## 🖥️ System & Interface Basics

### A. The Chatbot Widget (`rdr_chatbot.js`)
*   Embedded at the bottom-right of the web page.
*   Handles live chatting, loads chat history on reconnect, and seamlessly switches UI styling when an admin takes over the session (styled in real-time as `.rdr-msg-admin` using JSON payloads).

### B. Admin Panel & Knowledge Base CRUD (`/knowledge`)
*   **Fully Decoupled CRUD Endpoints:** The admin panel performs all document operations exclusively via standard HTTP endpoints on the FastAPI backend:
    *   `GET /knowledge`: Lists all documents and their status.
    *   `POST /knowledge`: Saves/edits a document and starts background chunking/embeddings.
    *   `DELETE /knowledge/{id}`: Deletes a document and cascade-purges vector chunks.
*   **Plain Text Only (`TXT`):** The API accepts plain text strings (`source_text`) for document updates, splits them, generates vector embeddings using the Gemini API, and stores them in MariaDB.
*   *Note: Local `.docx` and `.txt` files located inside `requirements/knowledge_Base_doc/` are automatically ingested and embedded in the background on container startup (or can be manually re-run via the `clean_and_reingest.py` CLI script). If you update a file on disk, the ingestion system compares the content with the database and automatically re-embeds the changes.*
*   **KB Export Utility (`export_kb_to_txt.py`):** A command-line utility to query the `/knowledge/export` REST API and save all policies locally as `.txt` files. These `.txt` files can be placed inside `requirements/knowledge_Base_doc/` to automatically repopulate the database on new container builds.

### C. Live Support Takeover (`/ws/admin` & `/api/support`)
*   **Active Support Queue:** `GET /api/support/sessions` retrieves a live list of active guest or member chat sessions.
*   **WebSocket Takeover Hook:** Admins can accept a chat takeover (`POST /api/support/sessions/{session_id}/takeover`) which shifts the session status in the socket manager.
*   **WebSocket Bridge:** When an admin connects via WebSocket (`/ws/admin?session_id=...`), their messages are routed directly to the customer, and the AI chatbot engine is temporarily disabled.
*   **Release Takeover:** Admins can release the session back to the AI chatbot at any time (`POST /api/support/sessions/{session_id}/release`).

### D. Support Tickets Queue REST API (`/api/tickets`)
*   **Laravel Database Integration:** The chatbot integrates support tickets directly with the Laravel website database (`rdadmin_dev_realdealride` / MySQL).
*   **Decoupled Ticket REST Endpoints:**
    *   `GET /api/tickets`: Lists support tickets with filtering options (status, category, priority, and text search) joined with customer account information.
    *   `POST /api/tickets`: Submits a new support ticket (used by guests or members).
    *   `POST /api/tickets/{ticket_id}/reply`: Appends agent reply strings directly to the `support_chats` database table.
    *   `PUT /api/tickets/{ticket_id}/status`: Updates ticket status metadata (Open, In-Progress, Completed/Resolved, Closed).
    *   `PUT /api/tickets/{ticket_id}/priority`: Updates ticket priority levels (Low, Medium, High, Urgent).

### E. AI Performance & Analytics Dashboard APIs (`/api/analytics`)
*   **Overview Metrics:** `GET /api/analytics/overview` dynamically aggregates key metrics from the MariaDB `query_log` and `chat_sessions` tables (Total Queries, Answered Rate, Average AI Confidence, Average Response Time, Active Document/Chunk Counts, and Average Customer Satisfaction).
*   **Query Volume Chart:** `GET /api/analytics/chart` aggregates and group-counts chatbot query volumes for the last 14 days, used to render query graphs.
*   **Top Unanswered Queries:** `GET /api/analytics/unanswered` queries the `v_top_unanswered` MariaDB view to retrieve queries with low confidence or fallback triggers.

### F. Sandbox Test Environment & AI Configuration (`/api/sandbox` & `/config/ai`)
*   **Test Sandbox Engine:** `POST /api/sandbox` allows admins to input test questions and receive real-time similarity matching details, cosine distances, confidence scores, and raw Gemini generative responses.
*   **AI Settings Manager:** `GET /config/ai` and `POST /config/ai` retrieve and persist system prompts, LLM model parameters, temperature settings, and similarity confidence thresholds directly to the MariaDB `ai_configuration` table.

### G. Zero-DB Stateless Handshake
*   **Zero Database Session Sharing:** The Laravel website and FastAPI chatbot require no shared database access, session tables, or Redis clusters for session handshake.
*   **Stateless Cryptography:** The website signs user details in-memory using HS256 JWT, and the chatbot verifies the identity in-memory, ensuring absolute portability and backend decoupling.
*   **Graceful Guest Fallback:** If a verification signature is invalid or expired, the connection falls back gracefully to a guest session instead of disconnecting the user.

---

## 🖥️ Production-Ready Admin Dashboard

A fully-functional, production-ready Admin Dashboard is provided in this deliverables package:
*   **Location:** [admin_dashboard.html](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/frontend/admin_dashboard.html)
*   **Overview:** Provides dynamic management of KB Categories and Tags, chatbot personality system prompts (including fallback/escalation prompts with historical rollback versions), native HNSW vector index settings, unanswered query tracking, and the RAG test query sandbox.
*   **Local Testing:** Open the HTML file in any modern browser. It connects out-of-the-box to your local FastAPI backend instance (`http://localhost:8085`) and dynamically interacts with the MariaDB vector database.

---

## 📚 API Documentation & Specifications

The chatbot exposes fully-documented REST APIs and real-time WebSocket streams. You can find their specifications here:
*   **Swagger OpenAPI JSON Schema:** [openapi.json](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/openapi.json) — Exposes Swagger REST API schemas for KB CRUD, settings, and analytics.
*   **AsyncAPI Specification:** [AsyncAPI.yaml](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/AsyncAPI.yaml) — Defines WebSocket connection streams for regular users (`/ws/chat`) and admin takeover (`/ws/admin`).

---

## 🔧 Production WebSocket & Stability Configuration

To ensure absolute stability when running in a production environment under continuous uptime, the chatbot backend incorporates the following optimizations:

### 1. Database Connection Recovery
* **Problem:** MariaDB drops idle database connections after a configured `wait_timeout` (typically 8 hours). When users re-connect, stale socket pools crash query executions.
* **Solution:** The async engines in [database.py](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/backend/database.py) and [operational_api.py](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/backend/operational_api.py) enforce pessimistic pinging (`pool_pre_ping=True`) and connection recycling (`pool_recycle=1800`), automatically recovering from idle timeout drops.

### 2. Single-Worker Memory State
* **Problem:** WebSocket connection registries and the takeover queue state are stored in the FastAPI application process memory. If Gunicorn spawns multiple worker processes, users and admins routed to different processes cannot communicate.
* **Solution:** The production `Dockerfile` CMD is configured to run Gunicorn with 1 worker (`--workers 1`), ensuring all WebSockets terminate in the same memory space. Uvicorn's asynchronous ASGI loop natively handles thousands of concurrent open WebSockets on a single process.




