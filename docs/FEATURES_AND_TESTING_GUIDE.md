# Zunu AI Chatbot: Features & Testing Guide

This document is divided into two parts: **Part 1: Features & System Design** (how the chatbot works and interacts with the databases) and **Part 2: QA Testing Guide** (how to test the features).

---

# Part 1: Features & System Design

The Zunu AI Chatbot is built using **FastAPI** (Python backend), **LangGraph** (agent logic), and a lightweight **ReactJS widget** (embedded in the Laravel frontend). 

## 1. Core Chatbot Features

### A. Dynamic Inventory Search
*   **How it works:** Users can search for cars by asking about location, vehicle type (SUV, Sedan, etc.), and price budget (e.g. *"Show me SUVs in Germantown under $70 a day"*).
*   **Database Interaction:** 
    *   Queries the website's `cars` table in the Laravel database.
    *   If exact matches are found, it generates a responsive HTML grid showing car images, daily prices, ratings, trip counts, and a direct **"Book"** link.
    *   **Smart Recommendation Fallback:** If a user requests a price that is too low or a type that doesn't exist, the chatbot automatically drops the strict filters and recommends alternative cars available in that city.

### B. Policy Knowledge Base QA (Vector RAG)
*   **How it works:** Users can ask questions about rental policies (minimum age, deposit rules, cancellation policies, etc.).
*   **Decoupled Administration (REST API):**
    *   Administrative CRUD operations (listing, creating, updating, and deleting policy documents) are performed exclusively over standard HTTP endpoints (`GET`, `POST`, `DELETE` `/knowledge`) exposed by the FastAPI backend, decoupling the website from the chatbot database.
*   **Database Interaction:**
    *   PDF/TXT policy documents are split into text chunks, embedded into 3072-dimensional arrays via Google's `gemini-embedding-001` model, and stored in the chatbot's `kb_chunk_embeddings` table.
    *   When a user asks a question, the chatbot embeds the query and runs a vector cosine similarity search (`VEC_DISTANCE`) directly inside MariaDB:
        ```sql
        SELECT chunk_text, VEC_DISTANCE(embedding, VEC_FromText(:query_vec)) AS distance 
        FROM kb_chunk_embeddings 
        ORDER BY distance ASC LIMIT :top_k
        ```
    *   The matched text chunks are sent to the Gemini LLM to write a natural, accurate response.

### C. Car Reviews & Discount Lookup
*   **How it works:** Users can check active discounts and reviews for specific cars.
*   **Database Interaction:**
    *   Reviews are fetched by querying the website's `car_reviews` table (joined with `users` for reviewer names).
    *   Discounts are retrieved from the website's `car_price_discounts` table.

### D. Reservation Inquiries & Modifications
*   **How it works:** Registered users can check their booking status, modify trip dates, or request cancellation.
*   **Database Interaction:**
    *   **Retrieve Booking:** Queries the `car_bookings` table in the website's database.
    *   **Reservation Modification:** Inserts a request record into `reservation_modifications` with a status of **`'Pending'`**.
    *   **Booking Cancellation:** Calculates the refund from the `payments` table and inserts a cancellation request into `booking_cancellations` with a status of **`'Pending'`**.
    *   *Note: The chatbot never cancels or modifies bookings directly; it only inserts pending requests for administrators to approve/reject.*

### E. Guest Email Verification & Security Restrictions
*   **How it works:** Unlogged-in users (guests) can authenticate dynamically in-session by providing their email.
*   **Security Separation Policy:**
    *   **Securely Logged-in Users:** Connect with a signed `member_id` via WebSocket handshake (authenticated via Laravel site session). They have full access to view booking status, request date modifications, or request cancellations.
    *   **Dynamically Verified Email Guests:** When a guest provides their email, the chatbot queries the `users` table to authenticate them dynamically. However, they are restricted from calling sensitive tools (checking booking statuses, modifying bookings, or cancelling bookings) due to the lack of a secure, signed website session token. They are only authorized to submit support tickets.
    *   **Merging:** If they log in later, the widget reconnects the WebSocket with a secure `member_id` and automatically merges the guest chat history and support tickets into their permanent account.

### F. Live Handoff & Admin Takeover
*   **How it works:** If a user gets frustrated, requests a human, or the chatbot has low confidence, the chat escalates to a live support agent.
*   **Database Interaction:**
    *   Inserts a ticket directly into the website's `support_tickets` table (creating a default category in `support_categories` if empty).
    *   Inserts an escalation record into the chatbot's `escalations` table.
    *   Connects the administrator to the session via a WebSocket (`/ws/admin`), routing future client messages directly to the admin terminal instead of the AI.

---

## 2. Database Table Architecture

The system utilizes two database structures:

### Database 1: Website Database (`realdealride`)
The chatbot reads and writes directly to these Laravel tables:
*   `cars` (Read-Only: listings, pricing, locations)
*   `car_bookings` (Read-Only: user reservation details)
*   `car_price_discounts` (Read-Only: promotional rates)
*   `car_reviews` (Read-Only: guest ratings and feedback)
*   `users` (Read-Only: email verification and customer details)
*   `support_tickets` & `support_categories` (Write-Only: creates ticket requests)
*   `reservation_modifications` (Write-Only: inserts date change requests with `'Pending'` status)
*   `booking_cancellations` (Write-Only: inserts cancellation requests with `'Pending'` status)

### Database 2: Chatbot Database (`realdealride_ai`)
A dedicated MariaDB instance containing:
*   `chat_sessions`: Tracks active sessions, user IDs, platforms, and handoff states.
*   `query_log`: Logs every user message, AI answer, confidence score, and a 3072-dimensional `question_embedding` vector.
*   `kb_chunk_embeddings`: Stores text chunks and their 3072-dimensional `embedding` vectors.
*   `kb_documents`: Tracks uploaded policy files, versions, and sizes.
*   `escalations`: Records escalated sessions and waiting times.
*   `daily_metrics`: Stores daily analytics (total queries, response times, satisfaction scores).

> [!NOTE]
> **Complete Database Isolation**: The Laravel administration panel does NOT connect directly to `realdealride_ai`. All document additions, updates, listings, and deletions are performed via HTTP requests to the decoupled FastAPI REST API, which manages Database 2 internally.

---

# Part 2: QA Testing Guide

Follow these step-by-step instructions to test all features.

### Setup Before Testing
1.  **Open the local chatbot widget sandbox:** Open **`demo/test_widget.html`** in your browser.
2.  **Open the Support Admin Dashboard Mock Demo:** Open **`demo/support_admin_dashboard_mock_demo.html`** in another browser window to monitor takeover and ticket events.
3.  **Simulate a Logged-in User Session (Testing Token):**
    To test member-restricted features (like checking reservation status, cancellations, or modifications) without setting up a JWT token signer on your site, append the following query parameters to your browser's address bar when opening `test_widget.html`:
    `?member_id=22&jwt_token=jwt_bypass_demo_token_realdealride_enterprise_testing_secret_key_12345`
    *   **How it works:** The backend automatically recognizes this bypass token and logs you in as Member ID `22`, granting full access to member queries. Guests who connect without a token are treated as guest sessions and restricted from booking modifications.

---

### Test 1: Dynamic Inventory Search (Live Database)
*   **Question to paste:** `Are there any cars available in Germantown?`
    *   *Expected Behavior:* Renders a grid of available vehicles in Germantown, displaying daily rates, ratings, and a clickable "Book" button.
*   **Question to paste:** `Show me SUVs in Germantown under $70 a day`
    *   *Expected Behavior:* Filters the result grid to only display SUVs within that price range.
*   **Question to paste:** `Show me sedans in Germantown under $20 a day`
    *   *Expected Behavior:* No cars match this budget. The chatbot explains that no exact matches exist and returns alternative recommendations in Germantown.

---

### Test 2: Policy Knowledge Base QA (RAG Search)
*   **Question to paste:** `What is the minimum age to rent a car?`
    *   *Expected Behavior:* The bot retrieves chunks from your policy document and explains that the minimum age is 21 (with young driver fees for ages 21-24).
*   **Question to paste:** `Do you accept debit cards for reservations?`
    *   *Expected Behavior:* States that credit cards are required for security deposits and outlines the pre-authorization rules.
*   **Question to paste:** `What is your cancellation policy?`
    *   *Expected Behavior:* Outlines the cancellation windows (e.g. free cancellation up to 24/48 hours before pickup) and penalties.

---

### Test 3: Car Reviews & Discount Lookup
*   **Question to paste:** `What do customers say about the Nissan Rogue?`
    *   *Expected Behavior:* Pulls ratings and comments for the Nissan Rogue from the database.
*   **Question to paste:** `Are there any active discounts or promotions for Car ID 52?`
    *   *Expected Behavior:* Queries the discounts table and returns active rental discounts for that vehicle.

---

### Test 4: Reservation inquiries & modifications
*   **Setup:** Log in as a registered user (e.g., Member ID `1` / email `customer@example.com`).
*   **Question to paste:** `Can you show me my reservation status?`
    *   *Expected Behavior:* Lists active and past reservations as structured cards.
*   **Question to paste:** `I want to cancel reservation 2503724608`
    *   *Expected Behavior:* Calculates the estimated refund from the payments table and inserts a cancellation request into the website database. It returns a card saying: *"Cancellation Request Submitted - Pending Approval"*.
*   **Question to paste:** `I want to change my reservation dates for booking 2503724608`
    *   *Expected Behavior:* Prompts you for new dates. Once dates are provided, it submits a date modification request with `'Pending'` status.

---

### Test 5: Guest Authentication, Security Restrictions, and Ticket Creation
*   **Setup:** Clear browser cookies or open an incognito window so you are treated as an unauthenticated guest.
*   **Question to paste:** `I want to check my reservation details`
    *   *Expected Behavior:* The chatbot states you are not logged in and requests your email address.
*   **Step:** Type a registered email (e.g., `customer@example.com`).
    *   *Expected Behavior:* The chatbot invokes `lookup_user_by_email_tool`, registers/authenticates the guest in-session, and says they are now verified.
*   **Question to paste:** `Check the status of my booking 2503724608`
    *   *Expected Behavior:* The chatbot blocks the request and outputs the security warning: *"For security reasons, you must be logged in to your RealDealRide account to view reservation details. Please log in to the website and try again."*
*   **Question to paste:** `I want to open a support ticket about a billing issue`
    *   *Expected Behavior:* The chatbot allows the request, asks for details, calls `create_support_ticket_tool`, and successfully files the ticket under the customer's account!

---

### Test 6: Human Handoff & Live Takeover
*   **Question to paste:** `I want to speak with a human support agent`
    *   *Expected Behavior:* Creates a support ticket in the database and shows a confirmation message. On the Admin Console dashboard, this session will appear in the active queue.
*   **Step on Admin Console:** Click **"Accept Takeover"** on the admin console dashboard for this session.
    *   *Expected Behavior:* The chatbot enters "Human Takeover" mode. Future messages sent from the widget are routed directly to the admin console instead of the AI, allowing direct real-time agent chatting.

---

### Test 7: JWT Security & Connection Policy Verification (Bypass Token Demo)

* **Setup**: Ensure `JWT_SECRET` is set in the chatbot backend `.env` file and the backend container is running.
* **Test 7.1: Guest Fallback for Unauthenticated Member Claims**
    * **Action**: Open `test_widget.html` with query parameters `?member_id=22` (simulating a member connection attempt without a valid token).
    * **Expected Behavior**: The connection succeeds. However, because no valid token is provided, the backend downgrades the connection to a guest session (`member_id = 0`). The user can chat and search general policies, but is restricted from checking booking status or initiating cancellations.
* **Test 7.2: Verify Guest Access Without Tokens**
    * **Action**: Open `test_widget.html` with no query parameters (guest visitor).
    * **Expected Behavior**: The connection succeeds immediately. The bot greets you: *"Hi there! 👋 I'm Zunu..."* Guests can chat and ask general questions without a token.
* **Test 7.3: Authenticated User Login (Bypass Token)**
    * **Action**: Open `test_widget.html` with query parameters `?member_id=22&jwt_token=jwt_bypass_demo_token_realdealride_enterprise_testing_secret_key_12345` (simulating a successful Laravel site login).
    * **Expected Behavior**: The connection succeeds immediately. The bot loads past conversations for member `22` and welcomes you. You have full access to reservation status and booking modifications.
* **Test 7.4: Guest Session Merging**
    * **Action**: Start a new chat as a guest. Ask a policy question (e.g. `What is the minimum age to rent?`). Then, log in by simulating a redirect page update or refreshing the URL with the bypass token: `?member_id=22&jwt_token=jwt_bypass_demo_token_realdealride_enterprise_testing_secret_key_12345`.
    * **Expected Behavior**: The chatbot reconnects under Member ID `22`, automatically merges the guest chat history and queries in the database, and loads the previous visitor queries into your logged-in screen.
* **Test 7.5: Session Hijack Protection & Isolation**
    * **Action**: Access another member's active session ID (e.g. `?session_id=member_session_abc` where session `member_session_abc` is owned in the database by member `22`) without providing a valid JWT token.
    * **Expected Behavior**: The connection succeeds. However, since the client has no proof of ownership, the backend automatically generates a brand-new random `session_id` to isolate the connection. This prevents the visitor from viewing the member's private chat logs, while still allowing them to chat safely as an anonymous guest.

---

### Test 8: Inspecting WebSocket Handshakes and JSON Data via Browser DevTools

To verify that the Laravel JSON responses, JWT claims, and WebSocket messages conform exactly to the defined schemas:

#### Step 1: Open Browser Developer Tools
1. Open your browser (Google Chrome, Microsoft Edge, or Mozilla Firefox).
2. Right-click anywhere on the page and select **Inspect**, or press `F12` (`Ctrl + Shift + I` / `Cmd + Option + I`).
3. Click on the **Network** tab at the top of the developer pane.

---

#### Step 2: Inspect WebSocket Handshakes & Parameters
1. Inside the Network tab, look for the sub-tab filter row (e.g. All, Fetch/XHR, JS, CSS, WS). Click on **WS** (WebSockets) to hide other traffic.
2. Open the page `test_widget.html?member_id=22&jwt_token=jwt_bypass_demo_token_realdealride_enterprise_testing_secret_key_12345`.
3. In the Network log list, click on the connection named **`chat?session_id=...`**.
4. In the detailed panel on the right:
   * Select the **Headers** tab.
   * Look at the **Request URL**. Verify that it contains:
     * `session_id`: The auto-generated UUIDv4.
     * `token`: The bypass token string.
     * `member_id`: `22`.
   * Verify that the HTTP status of the handshake is **`101 Switching Protocols`**, confirming a successful connection!
5. Now, refresh the page with `?member_id=22` (without a token).
   * Verify that the connection named `chat?session_id=...` fails immediately.
   * Look at the **Headers** tab. The HTTP status code should be **`403 Forbidden`** (Starlette rejects the handshake because the token is missing and `member_id` is set), and the connection will close with status code `4001`.

---

#### Step 3: Inspect Real-Time Chat & Handoff Frames
1. Connect successfully using the bypass token.
2. In the Network pane for the **`chat?session_id=...`** connection, select the **Messages** tab (in Chrome/Edge) or **Frames** tab (in Firefox).
3. Type a message in the widget (e.g., `Hello`) and press Enter.
4. You will see a list of sent and received packets:
   * **Outgoing frame (green arrow up):** Look at the content. It is a raw text string: `"Hello"`.
   * **Incoming frame (red arrow down):** When the bot answers, a text frame is received. Look at the content. It is a raw text string of the bot response.
5. In another window, open the Live Support Admin Dashboard mock: `demo/support_admin_dashboard_mock_demo.html`.
6. Click **"Accept Takeover"** for the active session.
7. Switch back to your chat widget window and look at the WebSockets **Messages/Frames** tab:
   * You will see a new incoming frame containing a JSON string.
   * **JSON structure:**
     ```json
     {
       "role": "system",
       "content": "System: A customer support agent has joined the chat and taken over."
     }
     ```
   * Verify that the widget has updated its status and displayed the alert in the chat area.
8. Have the admin type a message (e.g. `How can I help you?`) from the dashboard:
   * You will see another incoming frame.
   * **JSON structure:**
     ```json
     {
       "role": "admin",
       "content": "How can I help you?"
     }
     ```
   * Verify that the widget displays this message in slate color aligned to the left.

---

#### Step 4: Inspect AJAX History & Session REST Endpoints
1. Click the **History** button in the chat widget header.
2. In the Developer Tools Network tab, switch back to the **All** or **Fetch/XHR** filter.
3. You will see a GET request to `/chat/sessions?token=...`.
   * Click on it and select the **Response** tab.
   * Verify that it returns a JSON array of sessions.
4. Click on one of the past sessions to load history:
   * You will see a GET request to `/chat/history?session_id=...&token=...`.
   * Click on it and select the **Response** tab.
   * Verify that it returns a chronological JSON array of messages.

---

### Test 9: Decoupled REST API CRUD Operations (Knowledge Base)

To verify that the administrative REST API is working correctly and allows full decoupled CRUD operations:

#### Step 1: Run the Automated Validation Script
1. Connect to the VPS via SSH.
2. Execute the verification script inside the `rdr_fastapi_backend` container:
   ```bash
   sudo docker exec rdr_fastapi_backend python /app/test_vps_api_crud.py
   ```

#### Step 2: Verify the Test Logs and Output
Ensure that the stdout logs display successful responses for all CRUD steps:
* **GET /knowledge (List)**: Returns list of active policy documents.
* **POST /knowledge (Create)**: Saves a new test document, returns `status: "processing"`, and initiates background embedding.
* **GET /knowledge (Status check)**: Successfully polls the status and waits until it becomes `active`.
* **DELETE /knowledge/{id} (Delete)**: Removes the document from the database, returning `status: "success"`.
* **GET /knowledge (Verification check)**: Verifies the document has been completely deleted.

---

### Test 10: Knowledge Base Plain Text Export & Container Repopulation

To verify that the backup export script works and new/updated `.txt` files are automatically ingested and embedded in the database:

#### Step 1: Run the Export Script
1. Navigate to the deliverables directory and run:
   ```bash
   python export_kb_to_txt.py
   ```
2. Enter the backend URL (e.g. `http://localhost:8085` or your production URL).
3. Verify that the script successfully downloads all policy documents and creates `.txt` files inside the `exported_kb_txt/` directory.
4. Open one of the exported `.txt` files (e.g. `cancellation_policy.txt`) to verify the plain text format is correct.

#### Step 2: Test Automatic Ingestion & Diff-Based Updates
1. Copy one of the exported `.txt` files or create a new test file named `Knowledge Base Document Test Policy.txt` containing:
   ```text
   This is a temporary test policy for Zunu AI Chatbot. 
   RealDealRide offers a 100% discount on all bookings made during testing.
   ```
2. Place this file inside the `requirements/knowledge_Base_doc/` directory of the chatbot.
3. Force a manual ingestion run (or rebuild/restart the container):
   ```bash
   docker exec -it rdr_fastapi_backend python clean_and_reingest.py
   ```
4. Verify from the container stdout logs that it prints:
   `New document found: 'Test Policy'. Inserting...` and `Successfully embedded 'Test Policy'`.
5. Run a semantic search in the chatbot widget sandbox (`test_widget.html`):
   * Type: `What is the discount during testing?`
   * *Expected Behavior:* The bot should answer about the 100% discount, citing the "Test Policy" document.
6. Now, modify the content of `Knowledge Base Document Test Policy.txt` on disk:
   ```text
   This is a temporary test policy for Zunu AI Chatbot. 
   RealDealRide offers a 50% discount on all bookings made during testing.
   ```
7. Re-run the ingestion command:
   ```bash
   docker exec -it rdr_fastapi_backend python clean_and_reingest.py
   ```
8. Verify from the log output that the script detects the change:
   `Re-processing 'Test Policy': Content changed` and `Successfully embedded 'Test Policy'`.
9. Ask the bot again: `What is the discount during testing?`
   * *Expected Behavior:* The bot should now correctly answer that the discount is 50%.
10. Delete the file `Knowledge Base Document Test Policy.txt` from the disk folder.

