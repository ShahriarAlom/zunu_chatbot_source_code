# Junu AI Chatbot: Production Deployment Guide

This guide describes how to deploy the Junu AI Chatbot (Junu) system in your hosting environment. It is written in simple English to make it easy for developers to follow.

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
2.  **Vector Dimensions:** The vector columns (`kb_chunk_embeddings.embedding` and `query_log.question_embedding`) are configured with **`VECTOR(768)`**. This matches the exact output size of Google's `gemini-embedding-001` model. Do not change this dimension size, or the vector database will fail to save embeddings.
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

### Step 2.5: Automated Knowledge Base Ingestion & Deduplication
Instead of manually copying and pasting policy text one file at a time inside the admin dashboard, you can ingest all corporate policy documents in one command:
1.  Make sure the policy DOCX files are placed in the `requirements/knowledge_Base_doc/` directory.
2.  Run the following script command inside the running backend container to automatically clean duplicate entries, verify status, and embed any missing policy files:
    ```bash
    docker exec -it rdr_fastapi_backend python clean_and_reingest.py
    ```
3.  **Free Tier Daily Quota:** Google Gemini API key free tier limits embedding requests to 1000 requests per day. The script automatically handles and retries rate limit exceptions. If you exceed the 1000 daily limit, the remaining documents will fail with quota errors. The database retains the active ones, and you can safely rerun the same command tomorrow to pick up exactly where you left off.

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
Integrate the widget into your website templates (e.g. Laravel blade templates or WordPress themes) by adding this single script tag right before the closing `</body>` tag:

```html
<!-- RealDealRide Junu Chatbot Integration -->
<script 
  src="https://yourdomain.com/frontend/js/rdr_chatbot.js"
  id="rdr-chatbot-script"
  data-websocket-url="wss://yourdomain.com/ws/chat"
  data-member-id="0" 
  data-guest-session-id="">
</script>
```

#### Widget Attributes:
*   **`data-websocket-url`:** Set to your secure WebSocket domain path (use `wss://` for SSL).
*   **`data-member-id`:** Bind this dynamically using your PHP authentication state. For example:
    `data-member-id="{{ Auth::check() ? Auth::user()->id : 0 }}"`
*   **`data-guest-session-id`:** Keeps track of guest sessions. If a user is not logged in but has a session active, pass the session ID to keep their chat history intact.

---

## 4. Secure Authentication & Session Merging

To securely merge guest chats into a registered user account after login:
1.  **Token Generation:** When a user logs in, the Laravel website generates a signed JSON Web Token (JWT) containing the `member_id` and the `guest_session_id`. This token must be signed using the shared `JWT_SECRET` key.
2.  **Sending Token:** This token is passed securely to the chatbot when the user connects.
3.  **Verification:** The chatbot backend validates the signature using the shared `JWT_SECRET` key loaded from its `.env` file. Once verified, the chatbot merges the guest session history with the authenticated user ID. This ensures users cannot fake their identity.
