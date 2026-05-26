# Junu AI Chatbot: Features & Testing Guide

This document is divided into two parts: **Part 1: Features & System Design** (how the chatbot works and interacts with the databases) and **Part 2: QA Testing Guide** (how to test the features).

---

# Part 1: Features & System Design

The Junu AI Chatbot is built using **FastAPI** (Python backend), **LangGraph** (agent logic), and a lightweight **ReactJS widget** (embedded in the Laravel frontend). 

## 1. Core Chatbot Features

### A. Dynamic Inventory Search
*   **How it works:** Users can search for cars by asking about location, vehicle type (SUV, Sedan, etc.), and price budget (e.g. *"Show me SUVs in Germantown under $70 a day"*).
*   **Database Interaction:** 
    *   Queries the website's `cars` table in the Laravel database.
    *   If exact matches are found, it generates a responsive HTML grid showing car images, daily prices, ratings, trip counts, and a direct **"Book"** link.
    *   **Smart Recommendation Fallback:** If a user requests a price that is too low or a type that doesn't exist, the chatbot automatically drops the strict filters and recommends alternative cars available in that city.

### B. Policy Knowledge Base QA (Vector RAG)
*   **How it works:** Users can ask questions about rental policies (minimum age, deposit rules, cancellation policies, etc.).
*   **Database Interaction:**
    *   PDF policy documents are split into text chunks, embedded into 768-dimensional float arrays via Google's `gemini-embedding-001` model, and stored in the chatbot's `kb_chunk_embeddings` table.
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
*   `query_log`: Logs every user message, AI answer, confidence score, and a 768-dimensional `question_embedding` vector.
*   `kb_chunk_embeddings`: Stores text chunks and their 768-dimensional `embedding` vectors.
*   `kb_documents`: Tracks uploaded policy files, versions, and sizes.
*   `escalations`: Records escalated sessions and waiting times.
*   `daily_metrics`: Stores daily analytics (total queries, response times, satisfaction scores).

---

# Part 2: QA Testing Guide

Follow these step-by-step instructions to test all features.

### Setup Before Testing
1.  Open the local chatbot widget sandbox by opening **`demo/test_widget.html`** in your browser.
2.  Open the Support Admin Dashboard Mock Demo by opening **`demo/support_admin_dashboard_mock_demo.html`** in another browser window to monitor takeover and ticket events.

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
*   **Expected Behavior:* The chatbot enters "Human Takeover" mode. Future messages sent from the widget are routed directly to the admin console instead of the AI, allowing direct real-time agent chatting.
