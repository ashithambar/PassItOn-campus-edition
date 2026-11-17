// PassItOn – Real-time Chat Polling and Auto-scroll

document.addEventListener('DOMContentLoaded', function () {
    const messagesContainer = document.getElementById('chat-messages-box');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-content-input');
    
    if (!messagesContainer || !chatForm) return;

    const convoId = chatForm.dataset.conversationId;
    if (!convoId) return;

    // Scroll to bottom helper
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    scrollToBottom();

    // Live Polling every 3.5 seconds
    let lastMessageCount = messagesContainer.querySelectorAll('.chat-bubble').length;

    function pollMessages() {
        fetch(`/chat/api/messages/${convoId}`)
            .then(res => res.json())
            .then(data => {
                if (data && data.messages && data.messages.length !== lastMessageCount) {
                    lastMessageCount = data.messages.length;
                    messagesContainer.innerHTML = '';
                    data.messages.forEach(msg => {
                        const bubble = document.createElement('div');
                        bubble.className = `chat-bubble ${msg.is_me ? 'mine' : 'other'}`;
                        bubble.innerHTML = `
                            <div class="fw-semibold small ${msg.is_me ? 'text-white-50' : 'text-muted'}">${msg.sender_name}</div>
                            <div>${escapeHTML(msg.content)}</div>
                            <div class="chat-bubble-time">${msg.created_at}</div>
                        `;
                        messagesContainer.appendChild(bubble);
                    });
                    scrollToBottom();
                }
            })
            .catch(err => console.error("Chat polling error:", err));
    }

    const pollInterval = setInterval(pollMessages, 3500);

    // Clean up on leave
    window.addEventListener('beforeunload', () => clearInterval(pollInterval));

    // Handle instant send via fetch
    chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const content = messageInput.value.trim();
        if (!content) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

        // Optimistic UI update
        const tempBubble = document.createElement('div');
        tempBubble.className = 'chat-bubble mine';
        tempBubble.innerHTML = `
            <div>${escapeHTML(content)}</div>
            <div class="chat-bubble-time">Sending...</div>
        `;
        messagesContainer.appendChild(tempBubble);
        scrollToBottom();
        messageInput.value = '';

        fetch(`/chat/send/${convoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || '',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ content: content })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                pollMessages();
            }
        })
        .catch(err => {
            console.error("Send message error:", err);
            tempBubble.classList.add('bg-danger');
        });
    });

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
});
