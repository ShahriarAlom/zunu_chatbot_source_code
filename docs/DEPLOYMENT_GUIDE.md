# Junu AI Chatbot: Production Deployment Guide

This guide describes how to deploy the Junu AI Chatbot (Junu) system in your hosting environment.
---

## 1. System Architecture

The chatbot runs as a standalone service inside a Docker container:
*   **FastAPI Backend (Port 8000 / 8085):** Handles WebSocket chat connections and database queries.
*   **MariaDB Vector Database (Port 3307):** Stores chatbot data, session logs, metrics, and document search embeddings.
*   **Website Database (MySQL):** The chatbot queries your existing Laravel database directly for inventory, bookings, reviews, and inserts pending support, modification, and cancellation requests.

---

## 2. Database & Schema Configuration

To run successfully, the chatbot needs connections to two databases: the new **Chatbot Database** (`realdealride_ai`) and your existing **Website Database** (`realdealride`).

### A. Website Database Permissions
The database user credentials provided to the chatbot backend must have the following permissions on your website database:
*   **`SELECT`** on tables: `cars`, `car_bookings`, `car_price_discounts`, `car_reviews`, `users`, `faqs`, `payments`.
*   **`INSERT` & `UPDATE`** on tables: `support_tickets`, `support_categories`, `reservation_modifications`, `booking_cancellations`.

### B. Chatbot Vector Database Initialization
The chatbot database requires a special schema with vector support to run semantic searches on policy files:
1.  On first startup, the Docker container automatically runs the schema script located at [deliverables/requirements/init-mariadb.sql](file:///j:/realdealride-chatbot/ai-chatbot-project/deliverables/requirements/init-mariadb.sql).
2.  **Vector Dimensions:** The vector columns (`kb_chunk_embeddings.embedding` and `query_log.question_embedding`) are configured with **`VECTOR(3072)`**. While the standard `gemini-embedding-001` specifies a smaller output size, the production environment's LangChain integration generates high-quality **3072-dimensional** embedding vectors. The database auto-healing schema checks automatically ensure that columns are configured with `VECTOR(3072)`.
3.  **Mock Vector Data:** The 8-dimensional mock vector inserts have been removed from the init script to prevent any database crash during startup. The knowledge base is dynamically ingested using the actual model in **Step 2.5**.

---

## 3. Deployment Steps

### Step 1: Configure Environment Variables (`.env`)
1.  Navigate to the `backend/` directory in your deliverables folder.
2.  Rename `.env.example` to `.env`.
3.  Add the shared secret key for guest session authentication:
    *   **`JWT_SECRET`**: Add a secure, randomly generated string key. This **must match** the `JWT_SECRET` configured in your Laravel website's `.env` file to sign and verify secure login tokens.
4.  Choose **one** of the two database connection methods below:

#### Method A: Easy Laravel Style (Recommended)
If your database passwords contain special characters (like `;`, `!`, `}`, `@`), SQLAlchemy connection string parsers might crash. To prevent this, you can copy your website's database credentials directly into the `.env` file. The backend will automatically and securely URL-encode the password:
```env
# Google Gemini API Key
GEMINI_API_KEY=AIzaSyBxsVD5Rx-44FRjyA4tjJ5oxdfECNzD2UQ

# Token secret for session authentication (Must match Laravel's key)
JWT_SECRET=YourSecretTokenSigningKeyHere

# Website Database (Laravel) Credentials
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USERNAME=rdadmin_dev
DB_PASSWORD=b!vq;N}NjFJ1
DB_DATABASE=rdadmin_dev_realdealride

# Chatbot Database Credentials
CHATBOT_DB_HOST=127.0.0.1
CHATBOT_DB_PORT=3307
CHATBOT_DB_USERNAME=root
CHATBOT_DB_PASSWORD=password
CHATBOT_DB_DATABASE=realdealride_ai
```

#### Method B: Direct Connection URIs
Alternatively, you can provide the complete connection URIs directly. Note that any special characters in passwords must be URL-encoded manually:
```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
JWT_SECRET=YourSecretTokenSigningKeyHere
MARIADB_URI=mysql+aiomysql://root:password@localhost:3307/realdealride_ai
LARAVEL_DB_URI=mysql+aiomysql://rdadmin_dev:b%21vq%3BN%7DNjFJ1@localhost:3306/rdadmin_dev_realdealride
```

---

### Step 2: Spin Up the Containers
Build and start the services in the background using Docker Compose:
```bash
docker-compose up --build -d
```
Verify that both the backend and database containers are healthy:
```bash
docker ps
```

---

### Step 2.5: Automatic Database Auto-Healing & Knowledge Base Ingestion
To make deployment as smooth as possible, the backend container automatically handles database schema checks and document ingestion on startup:
1.  **Automatic Schema Healing:** When the FastAPI container starts, it connects to MariaDB and checks the structure of the `kb_chunk_embeddings` and `query_log` tables. If it finds that they exist but are configured with outdated vector dimensions (e.g. `VECTOR(768)` or `VECTOR(8)`), it automatically runs `ALTER TABLE` commands to update the columns to `VECTOR(3072)` to match the Gemini model's outputs. This preserves existing tables and prevents database connection errors.
2.  **Automated Ingestion:** Immediately after verifying the database, the container launches the `clean_and_reingest.py` script in the background. It automatically scans the `/app/knowledge_Base_doc/` directory, checks for new or modified files, cleans duplicate entries, and embeds any missing documents using the Gemini API.
3.  **Manual Trigger (Optional):** If you ever need to manually force a cleanup and re-ingest cycle without restarting your containers, you can run:
    ```bash
    docker exec -it rdr_fastapi_backend python clean_and_reingest.py
    ```
4.  **Free Tier Daily Quota:** The Google Gemini API key free tier limits embedding requests to 1000 requests per day. The automated ingestion script automatically handles and retries rate limit exceptions. If you exceed the 1000 daily limit, the remaining documents will fail with quota errors. The database retains the active ones, and you can safely restart the container or rerun the manual command tomorrow to pick up exactly where you left off.

---

### Step 3: Configure Your Reverse Proxy (Nginx)
WebSockets require Nginx to upgrade the connection header. Add this server block to your site's Nginx configuration (usually in `/etc/nginx/sites-available/default`):

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Chatbot Backend API Endpoints
    location / {
        proxy_pass http://127.0.0.1:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Route (For Chat & Admin Takeover)
    location /ws/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        
        # Prevent connection timeouts for long-lived sockets
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```
Reload Nginx to apply changes:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

### Step 4: Embed the Chat Widget on the Website

#### 1. Placing the Widget File
Copy the JavaScript file **`rdr_chatbot.js`** from `deliverables/frontend/` and place it inside your website's public assets directory.
*   **Recommended location:** `realdealride.com/public/frontend/js/rdr_chatbot.js`

#### 2. Adding the Script Tag
Integrate the widget into your website templates (e.g. Laravel blade templates or WordPress themes) by adding this single script tag. If you are placing it inside the `<head>` of your page, **you must include the `defer` attribute** to ensure the DOM is fully parsed and `document.body` exists when the script runs:

```html
<!-- RealDealRide Junu Chatbot Integration -->
<script 
  src="https://yourdomain.com/frontend/js/rdr_chatbot.js"
  id="rdr-chatbot-script"
  data-websocket-url="wss://yourdomain.com/ws/chat"
  data-member-id="0" 
  data-jwt-token=""
  data-guest-session-id=""
  defer>
</script>
```

#### Script Tag Attributes (In Plain English):
*   **`id="rdr-chatbot-script"`**: Required. A label that tells the chatbot where it is on your page so it can load its settings.
*   **`data-websocket-url`**: The digital address where the chatbot backend is hosting the live conversation (use `wss://` for secure SSL).
*   **`data-member-id`**: Tells the chatbot if the visitor is logged in. Bind this dynamically to the customer's account number (e.g. `{{ Auth::check() ? Auth::user()->id : 0 }}`). If they are just visiting, it stays `0`.
*   **`data-jwt-token`**: A secure electronic badge created by your website. Pass the signed JWT token here when a user logs in. This proves the customer is who they say they are so no one can spy on other people's chats.
*   **`data-guest-session-id`**: Helps merge a visitor's guest chat history into their permanent account once they decide to log in.


---

## 4. Secure Authentication & Session Merging

To securely merge guest chats into a registered user account after login:
1.  **Token Generation:** When a user logs in, the Laravel website generates a signed JSON Web Token (JWT) containing the `member_id` and the `guest_session_id`. This token must be signed using the shared `JWT_SECRET` key.
2.  **Sending Token:** This token is passed securely to the chatbot when the user connects.
3.  **Verification:** The chatbot backend validates the signature using the shared `JWT_SECRET` key loaded from its `.env` file. Once verified, the chatbot merges the guest session history with the authenticated user ID. This ensures users cannot fake their identity.

---

## 5. Data Schemas, JSON Formats, and Handshakes

This section defines the exact structure and fields of all data payloads, handshakes, and communication frames exchanged between the Laravel website, the chat widget, and the FastAPI chatbot backend.

### 5.1 Laravel Login JSON Response Schema
When a user logs in via AJAX or retrieves their active session details from the Laravel website, the Laravel backend returns a JSON payload containing the authenticated user info, the signed JWT token, and the client's guest session identifier.

**Example Payload:**
```json
{
  "status": "success",
  "message": "User authenticated successfully",
  "data": {
    "user": {
      "id": 22,
      "name": "Jane Doe",
      "email": "customer@example.com"
    },
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJtZW1iZXJfaWQiOjIyLCJndWVzdF9zZXNzaW9uX2lkIjoiODllZjY3MzEtOTJmYS00Y2I1LWI1ZjctNjQwYmUwNDVmMmFkIiwiaWF0IjoxNzE3NjYwODAwLCJleHAiOjE3MTc3NDcyMDB9.SignatureValue...",
    "guest_session_id": "89ef6731-92fa-4cb5-b5f7-640be045f2ad"
  }
}
```

**Field-by-Field Definition (Plain English):**
*   **`status`** (String): Tells the frontend if the request succeeded. Always `"success"` for a successful login.
*   **`message`** (String): A short, human-friendly summary of the request outcome.
*   **`data`** (Object): The container for the actual login payload.
    *   **`data.user`** (Object): Contains the user's primary details.
        *   **`data.user.id`** (Integer): The customer's unique ID (`member_id`) from your database.
        *   **`data.user.name`** (String): The display name of the customer.
        *   **`data.user.email`** (String): The email address used for login.
    *   **`data.token`** (String): The signed JSON Web Token (JWT) created by the Laravel server. The frontend widget reads this token and sends it during the WebSocket handshake to verify the member's identity.
    *   **`data.guest_session_id`** (String / null): A unique session ID generated by the frontend widget when the user was chatting anonymously as a guest before logging in. If there was no guest session, this can be `null`.

---

### 5.2 JSON Web Token (JWT) Claim Details
The JWT token is a cryptographically secured badge that proves the user's identity. It is signed on the Laravel website using the shared `JWT_SECRET` key and verified on the FastAPI backend.

**Decoded JWT Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Decoded JWT Payload (Claims):**
```json
{
  "member_id": 22,
  "guest_session_id": "89ef6731-92fa-4cb5-b5f7-640be045f2ad",
  "iat": 1717660800,
  "exp": 1717747200
}
```

**Field-by-Field Definition (Plain English):**
*   **`member_id`** (Integer - Required): The customer's database user ID. This is how the chatbot maps the chat session to a real user account in the database.
*   **`guest_session_id`** (String - Optional): The UUID of the guest session that was active on the client *before* logging in. When present, the chatbot backend automatically finds the chat logs and support tickets from this guest session and merges them into this member's permanent history.
*   **`iat`** (Integer - Required): "Issued At" UNIX timestamp. Represents the exact second the token was generated by Laravel.
*   **`exp`** (Integer - Required): "Expiration" UNIX timestamp. Represents when the token will become invalid. Typically set to 24 hours after issuance to prevent old, intercepted tokens from being used indefinitely.

---

### 5.3 WebSocket Handshake & Query Parameters
When the frontend widget establishes a connection to the chatbot backend at `ws://localhost:8085/ws/chat`, it appends query parameters to the URL to authenticate the connection.

**Handshake Connection URL Example:**
```
ws://localhost:8085/ws/chat?session_id=verification_session_99&token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...&member_id=22&guest_session_id=89ef6731-92fa-4cb5-b5f7-640be045f2ad
```

**Parameter Definitions (Plain English):**
*   **`session_id`** (String - Required): A unique UUIDv4 identifying the active conversation session. If the client does not send one, the chatbot backend generates one automatically.
*   **`token`** (String - Optional): The signed JWT token from Laravel.
    *   *If the visitor is an anonymous guest:* This parameter is omitted or left empty.
    *   *If the visitor is a logged-in member:* This parameter **must** be sent. The backend decodes and verifies the signature using the shared secret. If invalid, the connection is instantly rejected with Close Code `4001`.
*   **`member_id`** (Integer - Optional): The member's ID. Only checked if `token` is missing.
    *   *Security Policy:* If the backend has a `JWT_SECRET` configured, any handshake with `member_id > 0` that lacks a valid signed `token` is rejected with Close Code `4001`. This prevents malicious visitors from faking a member login.
*   **`guest_session_id`** (String - Optional): Passed when a guest has just logged in. Triggers the backend to merge their guest history into their new permanent profile.

---

### 5.4 WebSocket Message & Handoff Payloads
Once the WebSocket connection is open, the client and server exchange text messages. Depending on the state of the conversation, the message content may be a raw string or a JSON payload.

#### A. Client-to-Server User Messages
*   **Format:** Raw Text String
*   **Example:** `"Show me my reservation status"`
*   *Why we skipped JSON wrappers:* Sending user messages as plain text strings keeps the integration simple, reduces network overhead, and allows developers to test the socket using standard shell tools (e.g. `wscat` or custom python scripts).

#### B. Server-to-Client Chatbot Responses
*   **Format:** Raw Text String (can contain Markdown or HTML blocks)
*   **Example:**
    ```html
    <div class="rdr-car-grid">
      <div class="rdr-car-card">
        <h4>Nissan Rogue</h4>
        ...
      </div>
    </div>
    ```
*   *Why we did this:* Standard bot answers are sent as strings. If the bot returns a structured grid (e.g. for car inventory), it returns a custom HTML template. The frontend widget detects this HTML and dynamically expands the chat window to render a rich recommendation layout.

#### C. Server-to-Client System & Admin Takeover Frames
*   **Format:** JSON String (parsed on the client side)
*   *Why we added this:* When a human support agent takes over a session, the chatbot needs to notify the widget to change its UI layout, display a system warning, or route the text bubbles to a slate-colored "Admin" style instead of the standard white "Bot" style.

##### 1. System Alert Frame (Handoff Transition)
Sent when the conversation moves from the AI to a human agent, or back to the AI.
```json
{
  "role": "system",
  "content": "System: A customer support agent has joined the chat and taken over."
}
```
*   **`role`** (String): Set to `"system"`. Tells the widget that this is a system-generated alert, not a chat message.
*   **`content`** (String): The text explanation displayed inside the chat interface.

##### 2. Admin Chat Frame
Sent when a live support agent types a message to the user from the admin console.
```json
{
  "role": "admin",
  "content": "Hello! I am checking your reservation details now. One moment."
}
```
*   **`role`** (String): Set to `"admin"`. Tells the widget to style the bubble with a slate-colored theme and align it to the left to denote a human agent response.
*   **`content`** (String): The text typed by the support agent.

---

### 5.5 HTTP REST API Endpoint Payloads
The chatbot backend provides three REST API endpoints for session tracking, chat history loading, and knowledge base syncs.

#### A. GET `/chat/sessions`
Used by the widget to retrieve a history of past chat sessions.
*   **Request URL:** `/chat/sessions?token=<token>&member_id=<id>&session_ids=<ids>`
*   **Response JSON:**
    ```json
    [
      {
        "session_id": "9aef4531-12fa-4cb5-b5f7-640be045f2ad",
        "member_id": 22,
        "started_at": "2026-06-06T08:15:30Z",
        "preview": "Are there any cars available in Germantown?",
        "was_escalated": false
      }
    ]
    ```
*   **Keys Explained:**
    *   `session_id` (String): The session identifier.
    *   `member_id` (Integer): Owner of the session.
    *   `started_at` (String): ISO timestamp of session start.
    *   `preview` (String): The first question asked in this session, used as a preview title in the history panel.
    *   `was_escalated` (Boolean): Flag indicating if this session was escalated to a human agent.

#### B. GET `/chat/history`
Used by the widget to load the full transcript of a specific session when a user clicks on it in the history panel.
*   **Request URL:** `/chat/history?session_id=<session_id>&token=<token>`
*   **Response JSON:**
    ```json
    [
      {
        "role": "user",
        "content": "What is the minimum age to rent a car?",
        "created_at": "2026-06-06T08:15:30Z"
      },
      {
        "role": "assistant",
        "content": "The minimum age to rent a car on RealDealRide is 21...",
        "created_at": "2026-06-06T08:15:32Z"
      }
    ]
    ```
*   **Keys Explained:**
    *   `role` (String): The sender of the message (`"user"`, `"assistant"`, or `"admin"`).
    *   `content` (String): The text content of the message.
    *   `created_at` (String): ISO timestamp.

#### C. POST `/knowledge/update`
Triggered by the Laravel admin dashboard to update the chatbot's knowledge base.
*   **Request JSON:**
    ```json
    {
      "document_id": 15,
      "source_text": "This is the updated corporate cancellation policy..."
    }
    ```
*   **Response JSON:**
    ```json
    {
      "status": "processing",
      "document_id": 15,
      "message": "Document chunking and embedding started in background."
    }
    ```
*   **Keys Explained:**
    *   `document_id` (Integer): Primary key of the document record.
    *   `source_text` (String): The plain text content to chunk, embed, and store.
    *   `status` (String): Always `"processing"` since embedding runs asynchronously in the background.

---

### 5.6 Architectural Design Rationales

#### A. Why We Chose JWT-Based Authentication Separated Services
The website runs on PHP (Laravel) while the chatbot runs on Python (FastAPI). 
*   **Decoupling:** Using JSON Web Tokens (JWT) allows the FastAPI backend to verify the customer's identity statelessly without querying the Laravel application or sharing session stores.
*   **Security Isolation:** The shared `JWT_SECRET` signed signature guarantees that a user cannot connect to the chatbot WebSocket and fake their `member_id` because they cannot forge the signature.
*   **Performance:** FastAPI validates the token signature in-memory in less than a millisecond, completely bypassing any external database calls or session lookups.

#### B. Why We Skipped Shared Session Cookies or Laravel Session Stores
*   **Complexity:** Laravel session cookie encryption is proprietary to PHP and changes between versions. Re-implementing Laravel session decrypters in Python is fragile and prone to breaking during Laravel framework updates.
*   **Cross-Domain Issues:** If the chatbot is hosted on a different subdomain (e.g. `chatbot.realdealride.com`), sharing session cookies introduces cross-domain tracking policies that modern browsers block by default.
*   **Scalability:** Reading Laravel's database or Redis session store directly from FastAPI would create tight database coupling, increasing load and creating database locks during high traffic.

#### C. Why Guest Email Verification Restrictions Were Added (Why We Skipped Write Tools)
*   **Mitigation of Identity Theft:** When an unauthenticated guest types in their email to chat, the chatbot queries the `users` table to identify them. However, because there is no cryptographic proof (JWT token), we **skip enabling** reservation modification or cancellation tools for this guest. 
*   **Explanation:** Enabling write tools for unverified email claims would allow any anonymous visitor to cancel or modify other members' bookings simply by typing in their email. They are restricted to general Q&A and support ticket creation.

#### D. Why Takeover Uses WebSocket Frames Rather Than HTTP Long Polling
*   **Real-time Response:** Support agents require immediate, low-latency messaging. Long polling introduces a 1-2 second delay, making real-time customer support frustrating.
*   **Server Overhead:** Long polling causes hundreds of HTTP connections per minute, overloading the server. WebSockets maintain a single persistent connection, reducing resource utilization.

---

## 6. Laravel Admin Panel: Knowledge Base Integration Guide

This section outlines how to implement the chatbot administration features inside the Laravel Admin Panel to display, edit, upload, or delete knowledge base documents.

### 6.1 Database Connection Configuration
Since the chatbot's database is hosted on the same VPS, the Laravel application can query the static tables directly.

1. Add a new database connection configuration inside your Laravel `config/database.php` file under the `connections` array:
   ```php
   'chatbot_db' => [
       'driver' => 'mysql',
       'host' => env('CHATBOT_DB_HOST', '127.0.0.1'),
       'port' => env('CHATBOT_DB_PORT', '3307'),
       'database' => env('CHATBOT_DB_DATABASE', 'realdealride_ai'),
       'username' => env('CHATBOT_DB_USERNAME', 'root'),
       'password' => env('CHATBOT_DB_PASSWORD', 'password'),
       'charset' => 'utf8mb4',
       'collation' => 'utf8mb4_unicode_ci',
       'prefix' => '',
       'strict' => true,
       'engine' => null,
   ],
   ```
2. Configure these variables inside your Laravel `.env` file (pointing to the chatbot container's port, e.g., 3307 or 3306 depending on setup).

### 6.2 Reading and Displaying Documents
To show a list of all current knowledge base documents inside the Admin Panel, you do **not** need to make HTTP API calls. You can query the database directly.

**Example Laravel Eloquent Query:**
```php
// Retrieve all static documents to list on the dashboard
$documents = DB::connection('chatbot_db')
    ->table('kb_documents')
    ->select('document_id', 'title', 'file_name', 'file_size_bytes', 'version', 'status', 'updated_at')
    ->get();
```
Render this list in your Laravel Blade template so that admins can view document metadata, edit, or delete them.

### 6.3 Modifying / Uploading Documents (The HTTP Sync Hook)
When an administrator edits the text of an existing policy page or uploads a new plain text file, the static database must be updated, and the vector search database must recalculate its embeddings.

1. **Perform Static Update**: Update the static document row in the database table.
2. **Trigger Vector Rebuild**: Send a single HTTP POST request from Laravel to the FastAPI `/knowledge/update` endpoint to chunk and embed.

**Example Laravel Controller Integration:**
```php
use Illuminate\Support\Facades\Http;

public function savePolicyDocument(Request $request, $id)
{
    $title = $request->input('title');
    $text = $request->input('source_text');

    // 1. Update the static row in the chatbot database
    DB::connection('chatbot_db')
        ->table('kb_documents')
        ->where('document_id', $id)
        ->update([
            'title' => $title,
            'source_text' => $text,
            'status' => 'processing',
            'updated_at' => now(),
        ]);

    // 2. Trigger the FastAPI background task to regenerate vector chunks
    $response = Http::post('https://yourdomain.com/chat-api/knowledge/update', [
        'document_id' => (int)$id,
        'source_text' => $text
    ]);

    if ($response->successful()) {
        return redirect()->back()->with('success', 'Document updated and vector embeddings regeneration started.');
    } else {
        return redirect()->back()->with('error', 'Document saved, but failed to sync with vector database.');
    }
}
```

### 6.4 Deleting Documents (Cascade Sync)
When a document is deleted, the static plain-text record must be removed, and all of its associated vector search chunks must be cleaned up to remove the document from the chatbot's memory.

The database tables are configured with a foreign key constraint:
`FOREIGN KEY (document_id) REFERENCES kb_documents(document_id) ON DELETE CASCADE`

Because of this cascading relationship, **no HTTP calls are needed** to delete vector chunks. When Laravel deletes the parent document from the database, MariaDB automatically cleans up all associated vector chunks.

**Example Laravel Deletion Controller:**
```php
public function deletePolicyDocument($id)
{
    // Deleting the document here automatically triggers MariaDB to CASCADE delete
    // all corresponding vector embeddings inside 'kb_chunk_embeddings'
    DB::connection('chatbot_db')
        ->table('kb_documents')
        ->where('document_id', $id)
        ->delete();

    return redirect()->route('admin.chatbot.index')->with('success', 'Document and all vector search memories deleted.');
}
```
