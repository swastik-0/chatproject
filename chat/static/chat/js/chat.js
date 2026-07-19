(function () {
    const listEl = document.getElementById('message-list');
    const form = document.getElementById('message-form');
    const input = document.getElementById('message-input');
    const memberCountEl = document.getElementById('member-count');
    const memberCountLabelEl = document.getElementById('member-count-label');
    if (!listEl || !form) return;

    const pollUrl = listEl.dataset.pollUrl;
    const sendUrl = listEl.dataset.sendUrl;
    const csrfToken = window.CHAT_CONFIG.csrfToken;

    function lastMessageId() {
        const bubbles = listEl.querySelectorAll('.bubble');
        if (!bubbles.length) return 0;
        return bubbles[bubbles.length - 1].dataset.id || 0;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatTime(isoString) {
        const d = new Date(isoString);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function appendMessage(msg) {
        const bubble = document.createElement('div');
        bubble.className = 'bubble ' + (msg.is_self ? 'self' : 'other');
        bubble.dataset.id = msg.id;
        bubble.innerHTML =
            '<div class="bubble-meta">' + escapeHtml(msg.sender_username) + ' &middot; ' + formatTime(msg.timestamp) + '</div>' +
            '<div class="bubble-content"></div>';
        bubble.querySelector('.bubble-content').textContent = msg.content;
        listEl.appendChild(bubble);
    }

    function scrollToBottom() {
        listEl.scrollTop = listEl.scrollHeight;
    }

    function updateMemberCount(members) {
        if (!memberCountEl || !members) return;
        const count = members.length;
        memberCountEl.textContent = count;
        if (memberCountLabelEl) {
            memberCountLabelEl.textContent = count === 1 ? 'person' : 'people';
        }
    }

    scrollToBottom();

    async function poll() {
        try {
            const res = await fetch(pollUrl + '?after=' + lastMessageId());
            if (!res.ok) return;
            const data = await res.json();
            if (data.messages && data.messages.length) {
                data.messages.forEach(appendMessage);
                scrollToBottom();
            }
            updateMemberCount(data.members);
        } catch (err) {
            // Silently ignore transient network errors; next poll will retry.
        }
    }

    setInterval(poll, 2500);
    poll(); // also refresh the member count right away, not just after 2.5s

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const content = input.value.trim();
        if (!content) return;

        input.disabled = true;
        try {
            const res = await fetch(sendUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({ content }),
            });
            if (res.ok) {
                const msg = await res.json();
                appendMessage(msg);
                scrollToBottom();
                input.value = '';
            } else {
                const err = await res.json();
                alert(err.error || 'Could not send message.');
            }
        } catch (err) {
            alert('Network error while sending message.');
        } finally {
            input.disabled = false;
            input.focus();
        }
    });
})();