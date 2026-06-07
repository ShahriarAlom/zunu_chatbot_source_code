# Junu AI Chatbot: Deliverables Package

Welcome to the Junu AI Chatbot deliverables package. This folder contains all the files, code, sitemaps, and documentation required to deploy and run the chatbot on your hosting environment.

---

## 🗺️ Plug-and-Play System Architecture Overview

The chatbot is designed with a **100% decoupled, plug-and-play architecture** that allows you to embed it on any website layout and integrate it with any administrative panel backend without sharing database connections or session tables.

![Junu Chatbot System Architecture Map](file:///J:/realdealride-chatbot/ai-chatbot-project/deliverables/docs/chatbot_architecture_sitemap.png)

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
*   **`support_admin_dashboard_mock_demo.html`:** A dummy mock dashboard showing how an admin takeover panel interfaces with the WebSocket admin endpoint (`/ws/admin`).

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
*   *Note: Local `.docx` files are automatically ingested and embedded in the background on container startup, or can be manually re-run via the `clean_and_reingest.py` CLI script.*

### C. Live Support Dashboard (`support_admin_dashboard_mock_demo.html`)
*   Lists active support sessions in a live queue.
*   Allows agents to view chat logs and click **"Accept Takeover"** to intercept a conversation, routing subsequent messages directly between the agent and customer.

### D. Zero-DB Stateless Handshake
*   **Zero Database Session Sharing:** The Laravel website and FastAPI chatbot require no shared database access, session tables, or Redis clusters for session handshake.
*   **Stateless Cryptography:** The website signs user details in-memory using HS256 JWT, and the chatbot verifies the identity in-memory, ensuring absolute portability and backend decoupling.
*   **Graceful Guest Fallback:** If a verification signature is invalid or expired, the connection falls back gracefully to a guest session instead of disconnecting the user.

