# 📝 System Context & Blueprint for Future AI Agents

This document contains the complete context, system architecture, database layouts, and codebase workflows for the Junu AI Chatbot project. **If you are a new AI agent resuming work on this codebase, read this document to instantly align on the system state.**

---

## 1. Core Architecture Overview

The Junu AI Chatbot (Junu) is built using a **FastAPI** backend, **MariaDB Vector** database, and a **Vanilla JS widget** embedded on a Laravel website:
*   **FastAPI Backend (Port 8000/8085):** Handles real-time communication via WebSockets (`/ws/chat` for users, `/ws/admin` for support agents) and exposes RAG updates via REST `/knowledge/update`.
*   **MariaDB Vector Database (`realdealride_ai` on Port 3307):** Stores chat sessions, query logs, escalations, daily analytics, and 3072-dimensional vector embeddings for policies.
*   **Laravel Website Database (`rdadmin_dev_realdealride` on Port 3308):** Read-only for inventory queries and bookings; write/update for support tickets, modifications, and cancellations.

---

## 2. Directory & Component Mapping

*   **`backend/` / `deliverables/backend/`**:
    *   `app.py`: Sets up FastAPI server, CORS, WebSocket routers, and the REST endpoints.
    *   `socket_manager.py`: Manages WebSockets, in-memory conversation history buffers (last 10 messages), and coordinates live human takeover routing.
    *   `ai_engine.py`: Defines the LangChain Google Generative AI agent, system prompts, and tools (car search, policy search, reservation checks, tickets).
    *   `rag_pipeline.py` & `retrieval.py`: Splitter logic and cosine similarity matching (`VEC_DISTANCE`) against MariaDB vector embeddings.
    *   `clean_and_reingest.py`: Deduplicates database docs and embeds missing policy `.docx` files.
*   **`frontend/` / `deliverables/frontend/`**:
    *   `rdr_chatbot.js`: Embedded JS widget. Handles standard text messages and custom JSON WebSocket payloads from admins.
*   **`demo/` / `deliverables/demo/`**:
    *   `test_widget.html`: Chat widget sandbox.
    *   `support_admin_dashboard_mock_demo.html`: Mock support dashboard connecting to the active `/ws/admin` endpoint for live takeover.

---

## 3. Database Schema Blueprint

### Chatbot Vector DB (`realdealride_ai`)
*   **`chat_sessions`**: `session_id` (PK, UUID), `member_id` (signed ID), `started_at`, `ended_at`, `was_escalated` (boolean).
*   **`query_log`**: Logs questions, answers, and metrics.
*   **`kb_documents`**: `document_id` (PK), `title`, `file_name`, `source_text` (LONGTEXT), `status` ('processing', 'active', 'error').
*   **`kb_chunk_embeddings`**: `chunk_id` (PK), `document_id` (FK), `chunk_text` (TEXT), `embedding` (**`vector(3072)`**).
    *   *Note: LangChain's Google GenAI `models/gemini-embedding-001` returns 3072-dimensional arrays. Ensure the database matches this dimension.*

### Website DB (`realdealride` / Laravel)
*   **`cars`**: Available listings, location coordinates, ratings.
*   **`car_bookings`**: Reservation details.
*   **`car_reviews`**: Ratings and user testimonials.
*   **`support_tickets`**: Customer help tickets.
*   **`reservation_modifications`**: Date modification requests (inserted as `'Pending'`).
*   **`booking_cancellations`**: Date cancellation requests (inserted as `'Pending'`).

---

## 4. Key Workflows & Code Logic

### A. Dynamic Guest Authentication & Security Separation
*   ** Handshake**: The WebSocket connection is initialized with a `member_id` query parameter (defaulting to `0` for guests, or set to a signed Laravel ID).
*   **Session Persistence**: At the start of `generate_bot_response` in `ai_engine.py`, the agent queries the database `ChatSession` table to load the current `member_id` for that `session_id`.
*   **Security Restrictions**:
    *   `is_securely_logged_in` is `True` **only** if the initial connect had `member_id > 0` ( Laravel session signed).
    *   Guests who dynamically verify their email in-session are marked `is_securely_logged_in = False`.
    *   Sensitive tools (`check_reservation_status_tool`, `request_reservation_modification_tool`, `request_booking_cancellation_tool`) check this flag. If False, the tool returns a security warning blocking access.
    *   Guests are allowed to create tickets using `create_support_ticket_tool`.

### B. In-Memory History & Session Merging
*   **Takeover Logging**: In `socket_manager.py`, messages sent between the support agent and user during human takeover are appended to `self.session_histories` so the AI maintains complete context if the agent leaves.
*   **Account Merging**: When a user logs in, the widget reconnects. `connect_user` in `socket_manager.py` automatically updates all prior guest `QueryLog` entries and reassigns guest support tickets to the permanent user's account.

### C. Rate Limit Protection during RAG Ingestion
*   **Deduplication**: `clean_and_reingest.py` groups documents in `kb_documents` by filename, keeps the best unique entry, deletes duplicates, and cascades removal of orphaned embeddings.
*   **Smart Skipping**: It queries `kb_chunk_embeddings` for each document. If `status == 'active'` and `chunk_count > 0`, it skips embedding it. This preserves the 1000 daily request free tier limit of the Gemini embedding API.

---

## 5. Live Takeover JSON Payloads
To render styled admin bubbles, messages from `/ws/admin` are routed to the user widget formatted as a JSON string:
```json
{
  "role": "admin",
  "content": "Hello! I am a support agent taking over this chat..."
}
```
`rdr_chatbot.js` parses incoming messages; if `role === 'admin'`, it styles the bubble using `.rdr-msg-admin`.
