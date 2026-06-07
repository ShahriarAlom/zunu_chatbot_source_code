# Laravel Integration Files for Junu AI Chatbot

This folder contains the helper and layout files used to integrate secure JWT-based member authentication for the chatbot.

## File Map

1. **`app/Helpers/ChatbotHelper.php`**
   - The PHP helper class that generates and cryptographically signs user session tokens using the shared `JWT_SECRET` key.
   
2. **`resources/views/layouts/master.blade.php`**
   - Updated layout file for the main application pages. Includes the dynamic script tag that signs the visitor's `member_id` if logged in, and loads the chatbot widget script.

3. **`resources/views/layouts/master-help.blade.php`**
   - Updated layout file for the help center. Includes the identical dynamic script tag to authenticate the logged-in member.

## How it works

When a visitor is logged in, the layout template injects:
- `data-member-id="{{ Auth::id() }}"`
- `data-jwt-token="{{ App\Helpers\ChatbotHelper::generateToken(Auth::id()) }}"`

These attributes are read by `rdr_chatbot.js` and sent as query parameters during the WebSocket handshake. The FastAPI backend validates the token, preventing unauthorized users from accessing or hijacking other user sessions.
