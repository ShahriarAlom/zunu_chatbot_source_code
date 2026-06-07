# Laravel Integration: Modified Reference Scripts

This folder contains copies of the helper and layout files that were modified or created inside the Laravel website codebase to integrate the secure chatbot handshake.

---

## 📂 File Modification Track

### 1. `app/Helpers/ChatbotHelper.php`
* **Status**: `[NEW]` (Entirely new helper class created)
* **Lines**: `1` to `28`
* **Purpose**: Provides a cryptographic token generator. It takes the logged-in customer's database ID and signs it into a secure `HS256` JWT token using the shared `JWT_SECRET` key, verifying their identity to the chatbot without database session sharing.

---

### 2. `resources/views/layouts/master.blade.php`
* **Status**: `[MODIFY]` (Modified template layout)
* **Changes**:
  * **Lines 25–48**: Commented out the legacy Dialogflow messenger container (`<df-messenger>`) to disable the old chatbot widget.
  * **Lines 50–59**: Added the dynamic Javascript script injection tag:
    * If the customer is logged in (`Auth::check()`), it injects the chatbot widget script `rdr_chatbot.js` passing the user's `data-member-id` and the signed JWT token generated dynamically by `ChatbotHelper::generateToken(Auth::id())`.
    * If the visitor is a guest, it injects the chatbot script tag cleanly without authentication attributes, defaulting them to a guest session.
  * **Lines 61–73**: Commented out the legacy Dialogflow styling overrides.

---

### 3. `resources/views/layouts/master-help.blade.php`
* **Status**: `[MODIFY]` (Modified template layout for help center)
* **Changes**:
  * **Lines 369–392**: Commented out the legacy Dialogflow messenger container.
  * **Lines 394–403**: Added the dynamic Javascript script injection tag mapping `rdr_chatbot.js` and signing tokens for logged-in users, matching the behavior of the main master template.
  * **Lines 405–417**: Commented out the legacy Dialogflow styling overrides.
