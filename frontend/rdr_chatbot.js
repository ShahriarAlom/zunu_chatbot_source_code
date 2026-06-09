(function() {
    // RealDealRide Chatbot Widget - Vanilla JS, No Dependencies
    const CHATBOT_URL = window.location.origin + '/chat-api';
    
    function generateUUID() {
        try {
            return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
                (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
            );
        } catch (e) {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
    }
    
    const scriptEl = document.currentScript;
    const memberId = scriptEl ? scriptEl.getAttribute('data-member-id') : null;
    const jwtToken = scriptEl ? scriptEl.getAttribute('data-jwt-token') : null;
    let currentSessionId = localStorage.getItem('rdr_chat_session_id');
    let guestSessionIds = JSON.parse(localStorage.getItem('rdr_guest_session_ids') || '[]');
    
    if (!currentSessionId) {
        currentSessionId = generateUUID();
        localStorage.setItem('rdr_chat_session_id', currentSessionId);
        if (!memberId) {
            guestSessionIds.push(currentSessionId);
            localStorage.setItem('rdr_guest_session_ids', JSON.stringify(guestSessionIds));
        }
    }

    // Inject Styles
    const style = document.createElement('style');
    style.innerHTML = `
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

        :root {
            --rdr-navy: #0f172a;
            --rdr-teal: #ff240d;
            --rdr-teal-hover: #e01b07;
            --rdr-bg: #f8fafc;
            --rdr-text: #334155;
            --rdr-border: rgba(226, 232, 240, 0.8);
            --rdr-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
            --rdr-glass-bg: rgba(255, 255, 255, 0.92);
            --rdr-header-grad: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            --rdr-btn-grad: linear-gradient(135deg, #ff240d 0%, #d81600 100%);
        }
        
        #rdr-chat-widget {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 999999;
            font-family: 'Outfit', 'Inter', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }

        #rdr-chat-button {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: var(--rdr-btn-grad);
            color: white;
            border: none;
            box-shadow: 0 8px 24px rgba(255, 36, 13, 0.3);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        #rdr-chat-button:hover {
            transform: scale(1.06) translateY(-2px);
            box-shadow: 0 12px 30px rgba(255, 36, 13, 0.4);
        }

        #rdr-chat-button svg {
            width: 28px;
            height: 28px;
            fill: currentColor;
            transition: transform 0.3s;
        }
        
        #rdr-chat-button.open svg {
            transform: rotate(90deg) scale(0);
        }

        #rdr-chat-window {
            position: absolute;
            bottom: 84px;
            right: 0;
            width: 380px;
            height: 600px;
            max-height: calc(100vh - 120px);
            background: var(--rdr-glass-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-radius: 24px;
            box-shadow: var(--rdr-shadow);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            opacity: 0;
            pointer-events: none;
            transform: translateY(24px) scale(0.96);
            transform-origin: bottom right;
            transition: width 0.45s cubic-bezier(0.19, 1, 0.22, 1), height 0.45s cubic-bezier(0.19, 1, 0.22, 1), opacity 0.3s, transform 0.3s cubic-bezier(0.19, 1, 0.22, 1);
            border: 1px solid rgba(255, 255, 255, 0.6);
        }

        #rdr-chat-window.expanded {
            width: 820px;
            height: 700px;
        }

        .rdr-car-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-top: 14px;
            width: 100%;
        }
        .rdr-car-card {
            background: #fff;
            border: 1px solid var(--rdr-border);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .rdr-car-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
        }
        .rdr-car-card h4 { 
            margin: 0 0 6px 0; 
            font-size: 17px; 
            font-weight: 600;
            color: var(--rdr-navy); 
        }
        .rdr-car-type { 
            margin: 0 0 12px 0; 
            font-size: 11px; 
            font-weight: 500;
            color: #64748b; 
            text-transform: uppercase; 
            letter-spacing: 0.5px;
        }
        .rdr-car-details { 
            margin: 4px 0; 
            font-size: 13.5px; 
            display: flex; 
            flex-direction: column; 
            gap: 6px; 
            color: var(--rdr-text); 
        }
        .rdr-book-btn { 
            margin-top: 16px; 
            display: inline-block; 
            background: var(--rdr-teal); 
            color: white; 
            text-align: center; 
            padding: 10px; 
            border-radius: 8px; 
            text-decoration: none; 
            font-weight: 600;
            font-size: 14px;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(255, 36, 13, 0.15);
        }
        .rdr-book-btn:hover { 
            background: var(--rdr-teal-hover); 
            color: white; 
            box-shadow: 0 6px 16px rgba(255, 36, 13, 0.25);
            transform: translateY(-1px);
        }

        #rdr-chat-window.open {
            opacity: 1;
            pointer-events: all;
            transform: translateY(0) scale(1);
        }

        #rdr-chat-header {
            background: var(--rdr-header-grad);
            color: white;
            padding: 20px 24px;
            display: flex;
            align-items: center;
            gap: 14px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        #rdr-chat-header img {
            height: 26px;
            object-fit: contain;
        }

        #rdr-chat-header-info {
            flex-grow: 1;
        }

        #rdr-chat-header-title {
            font-size: 17px;
            font-weight: 600;
            margin: 0;
            line-height: 1.2;
            letter-spacing: -0.2px;
            color: #ffffff;
        }

        #rdr-chat-header-status {
            font-size: 11.5px;
            color: #94a3b8;
            display: flex;
            align-items: center;
            gap: 5px;
            margin-top: 3px;
        }
        
        .rdr-dot {
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
        }

        #rdr-chat-messages {
            flex-grow: 1;
            background: var(--rdr-bg);
            padding: 24px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        .rdr-msg {
            max-width: 82%;
            padding: 12px 18px;
            font-size: 14.5px;
            line-height: 1.5;
            border-radius: 20px;
            box-sizing: border-box;
            animation: rdr-fade-in 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .rdr-msg-bot {
            align-self: flex-start;
            background: white;
            color: var(--rdr-text);
            border-bottom-left-radius: 6px;
            box-shadow: 0 4px 10px rgba(15, 23, 42, 0.02);
            border: 1px solid var(--rdr-border);
        }

        .rdr-msg-user {
            align-self: flex-end;
            background: var(--rdr-teal);
            color: white;
            border-bottom-right-radius: 6px;
            box-shadow: 0 4px 14px rgba(255, 36, 13, 0.15);
        }

        .rdr-msg-admin {
            align-self: flex-start;
            background: #1e293b;
            color: white;
            border-bottom-left-radius: 6px;
        }

        #rdr-chat-input-area {
            padding: 18px 24px;
            background: white;
            border-top: 1px solid var(--rdr-border);
            display: flex;
            gap: 12px;
            align-items: center;
        }

        #rdr-chat-input {
            flex-grow: 1;
            border: 1px solid var(--rdr-border);
            border-radius: 30px;
            padding: 12px 20px;
            font-size: 14.5px;
            outline: none;
            transition: all 0.2s ease;
            background: #f8fafc;
            color: var(--rdr-navy);
            font-family: inherit;
        }

        #rdr-chat-input:focus {
            border-color: rgba(255, 36, 13, 0.6);
            background: white;
            box-shadow: 0 0 0 3px rgba(255, 36, 13, 0.08);
        }

        #rdr-chat-send {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: var(--rdr-teal);
            color: white;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(255, 36, 13, 0.15);
        }

        #rdr-chat-send:hover {
            background: var(--rdr-teal-hover);
            transform: scale(1.05);
            box-shadow: 0 6px 16px rgba(255, 36, 13, 0.25);
        }

        @keyframes rdr-fade-in {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 820px) {
            #rdr-chat-window.expanded {
                width: calc(100vw - 32px);
                height: calc(100vh - 100px);
            }
        }

        @media (max-width: 480px) {
            #rdr-chat-window {
                width: calc(100vw - 32px);
                height: calc(100vh - 100px);
                bottom: 80px;
                right: -8px;
            }
        }

        /* --- Chat History Panel --- */
        #rdr-chat-history-panel {
            position: absolute;
            top: 75px;
            left: 0;
            width: 100%;
            height: calc(100% - 75px);
            background: white;
            z-index: 100;
            display: flex;
            flex-direction: column;
            transform: translateX(-100%);
            transition: transform 0.35s cubic-bezier(0.19, 1, 0.22, 1);
            border-top: 1px solid var(--rdr-border);
        }
        #rdr-chat-history-panel.open {
            transform: translateX(0);
        }
        .rdr-history-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--rdr-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
            color: var(--rdr-navy);
            font-size: 15px;
        }
        .rdr-history-list {
            flex-grow: 1;
            overflow-y: auto;
            padding: 10px 0;
        }
        .rdr-history-item {
            padding: 14px 20px;
            border-bottom: 1px solid rgba(226, 232, 240, 0.5);
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .rdr-history-item:hover {
            background: #f1f5f9;
        }
        .rdr-history-item-date {
            font-size: 11px;
            color: #94a3b8;
        }
        .rdr-history-item-preview {
            font-size: 13.5px;
            color: var(--rdr-text);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-weight: 500;
        }

        /* --- CSS Spinner Utility --- */
        .spinner-border {
            display: inline-block;
            width: 1rem;
            height: 1rem;
            vertical-align: text-bottom;
            border: .15em solid currentColor;
            border-right-color: transparent;
            border-radius: 50%;
            animation: spinner-border .75s linear infinite;
        }
        @keyframes spinner-border {
            to { transform: rotate(360deg); }
        }
    `;
    document.head.appendChild(style);

    // Inject HTML Structure
    const widget = document.createElement('div');
    widget.id = 'rdr-chat-widget';
    widget.innerHTML = `
        <div id="rdr-chat-window">
            <div id="rdr-chat-header">
                <img src="https://realdealride.com/public/frontend/images/logo-light.png" onerror="this.style.display='none'" alt="RDR Logo" style="height: 24px; object-fit: contain;">
                <div id="rdr-chat-header-info">
                    <h4 id="rdr-chat-header-title">Zunu</h4>
                    <div id="rdr-chat-header-status"><span class="rdr-dot"></span> Replies instantly</div>
                </div>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <button id="rdr-chat-new" title="New Conversation" style="background: none; border: none; color: white; cursor: pointer; padding: 4px; display: flex; align-items: center; justify-content: center; opacity: 0.85; transition: opacity 0.2s;">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    </button>
                    <button id="rdr-chat-history-btn" title="Chat History" style="background: none; border: none; color: white; cursor: pointer; padding: 4px; display: flex; align-items: center; justify-content: center; opacity: 0.85; transition: opacity 0.2s;">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                    </button>
                </div>
            </div>
            
            <!-- History Overlay Panel -->
            <div id="rdr-chat-history-panel">
                <div class="rdr-history-header">
                    <span>Conversations</span>
                    <button id="rdr-chat-history-close" style="background: none; border: none; font-size: 20px; cursor: pointer; color: #64748b; font-weight: bold; line-height: 1;">&times;</button>
                </div>
                <div class="rdr-history-list" id="rdr-chat-history-list"></div>
            </div>

            <div id="rdr-chat-messages">
                <div class="rdr-msg rdr-msg-bot">Hi there! 👋 I'm Zunu, your RealDealRide AI Assistant. How can I help you with your booking today?</div>
            </div>
            <div id="rdr-chat-input-area">
                <input type="text" id="rdr-chat-input" placeholder="Type your message..." autocomplete="off">
                <button id="rdr-chat-send">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            </div>
        </div>
        <button id="rdr-chat-button">
            <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>
        </button>
    `;
    document.body.appendChild(widget);

    // Logic
    const button = document.getElementById('rdr-chat-button');
    const windowEl = document.getElementById('rdr-chat-window');
    const input = document.getElementById('rdr-chat-input');
    const sendBtn = document.getElementById('rdr-chat-send');
    const messages = document.getElementById('rdr-chat-messages');
    const historyPanel = document.getElementById('rdr-chat-history-panel');
    const historyBtn = document.getElementById('rdr-chat-history-btn');
    const historyClose = document.getElementById('rdr-chat-history-close');
    const newChatBtn = document.getElementById('rdr-chat-new');

    let isOpen = false;
    let ws = null; // WebSocket connection to FastAPI

    button.addEventListener('click', () => {
        isOpen = !isOpen;
        if (isOpen) {
            windowEl.classList.add('open');
            button.classList.add('open');
            button.innerHTML = '<svg viewBox="0 0 24 24" style="transform: rotate(0) scale(1)"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
            input.focus();
            if(!ws) connectWebSocket();
        } else {
            windowEl.classList.remove('open');
            button.classList.remove('open');
            button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>';
            historyPanel.classList.remove('open');
        }
    });

    // History Actions
    historyBtn.addEventListener('click', () => {
        historyPanel.classList.toggle('open');
        if (historyPanel.classList.contains('open')) {
            loadHistoryList();
        }
    });

    historyClose.addEventListener('click', () => {
        historyPanel.classList.remove('open');
    });

    newChatBtn.addEventListener('click', () => {
        // Generate new session ID
        currentSessionId = generateUUID();
        localStorage.setItem('rdr_chat_session_id', currentSessionId);
        
        // Save to guest sessions list if not logged in
        if (!memberId) {
            if (!guestSessionIds.includes(currentSessionId)) {
                guestSessionIds.push(currentSessionId);
                localStorage.setItem('rdr_guest_session_ids', JSON.stringify(guestSessionIds));
            }
        }
        
        // Clear screen and show default message
        messages.innerHTML = '<div class="rdr-msg rdr-msg-bot">Hi there! 👋 I\'m Zunu, your RealDealRide AI Assistant. How can I help you with your booking today?</div>';
        historyPanel.classList.remove('open');
        windowEl.classList.remove('expanded');
        
        // Reconnect WebSocket
        reconnectWebSocket();
    });

    // Expanded window state helper is updated on message render and cleared on session reset.

    function addMessage(text, sender) {
        if (sender === 'assistant') sender = 'bot';
        const msg = document.createElement('div');
        msg.className = `rdr-msg rdr-msg-${sender}`;
        
        // If it's pure text, format newlines. If it's HTML (like our grid), render directly.
        if(!text.trim().startsWith('<')) {
            // Bold text
            text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            // Bullet points
            text = text.replace(/(?:^|\n)\s*[\*\-]\s+(.*?)(?=\n|$)/g, '<li style="margin-left:20px; margin-bottom:5px;">$1</li>');
            if (text.includes('<li>')) {
                text = text.replace(/(<li.*<\/li>)/s, '<ul style="margin: 5px 0; padding-left: 0;">$1</ul>');
            }
            // Newlines
            text = text.replace(/\\n/g, '<br>');
            text = text.replace(/\n/g, '<br>');
        }
        msg.innerHTML = text;
        
        // If the message contains a grid, remove the standard chat bubble styling
        // so the cards can expand to full width and we remove the ugly secondary background!
        if (text.includes('rdr-car-grid')) {
            windowEl.classList.add('expanded');
            msg.style.maxWidth = '100%';
            msg.style.width = '100%';
            msg.style.background = 'transparent';
            msg.style.border = 'none';
            msg.style.boxShadow = 'none';
            msg.style.padding = '0';
            
            // Re-style the paragraph inside the grid wrapper so it looks good
            const p = msg.querySelector('p');
            if(p) {
                p.style.background = 'white';
                p.style.display = 'inline-block';
                p.style.padding = '12px 16px';
                p.style.borderRadius = '16px';
                p.style.borderBottomLeftRadius = '4px';
                p.style.border = '1px solid var(--rdr-border)';
                p.style.boxShadow = '0 2px 4px rgba(0,0,0,0.02)';
                p.style.marginBottom = '0';
            }
        }
        
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }

    async function loadHistoryList() {
        const listEl = document.getElementById('rdr-chat-history-list');
        listEl.innerHTML = '<div style="padding: 20px; text-align: center; color: #64748b; font-size: 14px;"><div class="spinner-border spinner-border-sm text-info mr-2"></div> Loading sessions...</div>';
        
        let url = `${CHATBOT_URL}/chat/sessions`;
        if (jwtToken) {
            url += `?token=${jwtToken}`;
        } else if (memberId) {
            url += `?member_id=${memberId}`;
        } else if (guestSessionIds.length > 0) {
            url += `?session_ids=${guestSessionIds.join(',')}`;
        } else {
            listEl.innerHTML = '<div style="padding: 20px; text-align: center; color: #64748b; font-size: 14px;">No previous conversations found.</div>';
            return;
        }
        
        try {
            const res = await fetch(url);
            const data = await res.json();
            
            if (data.length === 0) {
                listEl.innerHTML = '<div style="padding: 20px; text-align: center; color: #64748b; font-size: 14px;">No previous conversations found.</div>';
                return;
            }
            
            listEl.innerHTML = '';
            data.forEach(sess => {
                const date = new Date(sess.started_at);
                const formattedDate = date.toLocaleDateString(undefined, {month: 'short', day: 'numeric'}) + ' at ' + date.toLocaleTimeString(undefined, {hour: '2-digit', minute:'2-digit'});
                
                const item = document.createElement('div');
                item.className = 'rdr-history-item';
                item.innerHTML = `
                    <span class="rdr-history-item-date">${formattedDate}</span>
                    <span class="rdr-history-item-preview">${sess.preview}</span>
                `;
                item.addEventListener('click', () => {
                    selectSession(sess.session_id);
                });
                listEl.appendChild(item);
            });
        } catch (e) {
            console.error("Error loading sessions list", e);
            listEl.innerHTML = '<div style="padding: 20px; text-align: center; color: #ef4444; font-size: 14px;">Failed to load chat history.</div>';
        }
    }

    async function selectSession(sessionId) {
        windowEl.classList.remove('expanded');
        historyPanel.classList.remove('open');
        currentSessionId = sessionId;
        localStorage.setItem('rdr_chat_session_id', currentSessionId);
        
        messages.innerHTML = '';
        addMessage("<div class='spinner-border spinner-border-sm text-info'></div> Loading conversation...", 'bot');
        
        try {
            let url = `${CHATBOT_URL}/chat/history?session_id=${sessionId}`;
            if (jwtToken) {
                url += `&token=${jwtToken}`;
            }
            const res = await fetch(url);
            const historyMessages = await res.json();
            
            messages.innerHTML = '';
            if (historyMessages.length === 0) {
                addMessage("Welcome back! 👋 I'm Zunu. Let's continue our conversation.", 'bot');
            } else {
                historyMessages.forEach(msg => {
                    addMessage(msg.content, msg.role);
                });
            }
        } catch (e) {
            console.error("Error loading chat history messages", e);
            messages.innerHTML = '';
            addMessage("Welcome back! 👋 I'm Zunu. I was unable to load some past messages, but feel free to continue talking.", 'bot');
        }
        
        reconnectWebSocket();
    }

    function reconnectWebSocket() {
        if (ws) {
            ws.onclose = null;
            ws.close();
        }
        connectWebSocket();
    }

    function connectWebSocket() {
        const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let host = window.location.host || 'localhost:8085';
        let wsProtoLocal = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let wsUrl = wsProtoLocal + '//' + host + '/ws/chat?session_id=' + currentSessionId;
        if (jwtToken) {
            wsUrl += '&token=' + jwtToken;
        }
        if (memberId) {
            wsUrl += '&member_id=' + memberId;
            const lastGuestId = localStorage.getItem('rdr_last_guest_session_id');
            if (lastGuestId) {
                wsUrl += '&guest_session_id=' + lastGuestId;
                localStorage.removeItem('rdr_last_guest_session_id');
            }
        } else {
            localStorage.setItem('rdr_last_guest_session_id', currentSessionId);
        }

        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log("Connected to Chatbot Server");
        };
        
        ws.onmessage = (event) => { 
            const lastMsg = messages.lastChild;
            if (lastMsg && lastMsg.innerHTML.includes('Thinking...')) {
                lastMsg.remove();
            }
            try {
                const payload = JSON.parse(event.data);
                if (payload.role === 'admin') {
                    addMessage(payload.content, 'admin');
                } else if (payload.role === 'system') {
                    addMessage(payload.content, 'bot');
                } else {
                    addMessage(payload.content, 'bot');
                }
            } catch (e) {
                addMessage(event.data, 'bot');
            }
        };
        ws.onclose = (event) => {
            console.log("Disconnected from Chatbot Server. Close code:", event.code);
            if (event.code === 4001) {
                console.warn("WebSocket closed due to authentication policy violation. Reconnection stopped.");
                addMessage("Chat connection closed: Authentication failed. Please verify your credentials or log in again.", "bot");
                return;
            }
            console.log("Trying to reconnect in 3s...");
            setTimeout(connectWebSocket, 3000);
        };
    }


    function sendMessage() {
        const text = input.value.trim();
        if (!text) return;
        
        addMessage(text, 'user');
        input.value = '';
        
        if(ws && ws.readyState === WebSocket.OPEN) {
            ws.send(text);
            addMessage("<div class='spinner-border spinner-border-sm text-info'></div> Thinking...", 'bot');
        } else {
            addMessage("The connection to the server is lost. Please refresh the page.", 'bot');
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

})();
