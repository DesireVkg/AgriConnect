document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const messagesContainer = document.getElementById('messages');
    
    if (messageForm) {
        messageForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const message = messageInput.value.trim();
            const recipientId = messageForm.dataset.recipient;
            
            if (message) {
                socket.emit('send_message', {
                    recipient_id: recipientId,
                    content: message
                });
                messageInput.value = '';
            }
        });
    }
    
    socket.on('new_message', function(data) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.classList.add(data.sender_id === currentUserId ? 'sent' : 'received');
        messageElement.innerHTML = `
            <div class="message-content">
                <p>${data.content}</p>
                <small>${new Date(data.timestamp).toLocaleTimeString()}</small>
            </div>
        `;
        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    });
});
