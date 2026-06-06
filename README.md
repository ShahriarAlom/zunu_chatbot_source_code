# Junu AI Chatbot: Deliverables Package

Welcome to the Junu AI Chatbot deliverables package. This folder contains all the files, code, sitemaps, and documentation required to deploy and run the chatbot on your hosting environment.

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
*   **`support_admin_dashboard_mock_demo.html`:** A dummy mock dashboard showing how an admin takeover panel interfaces with the WebSocket admin endpoint (`/ws/admin`).

---

## 🖥️ System & Interface Basics

### A. The Chatbot Widget (`rdr_chatbot.js`)
*   Embedded at the bottom-right of the web page.
*   Handles live chatting, loads chat history on reconnect, and seamlessly switches UI styling when an admin takes over the session (styled in real-time as `.rdr-msg-admin` using JSON payloads).

### B. Admin Panel & Knowledge Base Updates (`/knowledge/update`)
*   **Plain Text Only (`TXT`):** The admin panel updates the knowledge base by hitting the backend endpoint `/knowledge/update` with a JSON payload containing the document ID and the raw text (`source_text`). 
*   **The backend only accepts plain text strings** for these updates. It splits the text into chunks, generates vector embeddings, and stores them directly in the MariaDB `kb_chunk_embeddings` table.
*   *Note: Local `.docx` files are automatically ingested and embedded in the background on container startup, or can be manually re-run via the `clean_and_reingest.py` CLI script.*

### C. Live Support Dashboard (`support_admin_dashboard_mock_demo.html`)
*   Lists active support sessions in a live queue.
*   Allows agents to view chat logs and click **"Accept Takeover"** to intercept a conversation, routing subsequent messages directly between the agent and customer.
