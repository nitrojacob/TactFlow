document.addEventListener('DOMContentLoaded', () => {
    // Initial Contact ID Sync across pages
    initContactIdSync('suggest-contact-id');

    // Initial sync of Nudge inputs with Outcome inputs
    const suggestContact = document.getElementById('suggest-contact-id');
    const outcomeContact = document.getElementById('outcome-contact-id');
    if (suggestContact && outcomeContact) {
        outcomeContact.value = suggestContact.value;
    }

    // Sync suggest contact ID with outcome fields automatically
    document.getElementById('suggest-contact-id').addEventListener('input', (e) => {
        document.getElementById('outcome-contact-id').value = e.target.value;
    });

    // Row management inside Nudge list
    document.getElementById('btn-suggest-add-row').addEventListener('click', () => {
        addHistoryRow('suggest-history-list');
    });

    // Global row delete delegate
    document.body.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-delete-row')) {
            const list = e.target.closest('.history-list');
            if (list.querySelectorAll('.history-row').length > 1) {
                e.target.closest('.history-row').remove();
            } else {
                alert('You must provide at least one turn.');
            }
        }
    });

    // Suggest Nudges execution
    const btnGetSuggestions = document.getElementById('btn-get-suggestions');
    btnGetSuggestions.addEventListener('click', async () => {
        if (!isOnline) { alert('Backend is offline.'); return; }
        if (!sessionToken) { alert('Please login first.'); return; }

        const contactId = document.getElementById('suggest-contact-id').value;
        const targetGoal = document.getElementById('suggest-target-goal').value;
        const history = getTranscriptData('suggest-history-list');

        const payload = {
            session_token: sessionToken,
            contact_id: contactId,
            target_goal: targetGoal,
            conversation_history: history
        };

        const outputContainer = document.getElementById('suggest-output-container');
        outputContainer.classList.add('hidden');

        updateInspector(payload, { status: 'generating strategic suggestions...' });
        setButtonLoading(btnGetSuggestions, true, 'Generating Nudges...');

        try {
            const res = await fetch(`${BACKEND_URL}/api/v1/assistant/suggest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            updateInspector(payload, data);

            if (res.ok) {
                document.getElementById('suggest-mood-val').textContent = data.recipient_mood_analysis;

                const collab = data.suggestions.find(s => s.tone_label.toLowerCase().includes('collaborative')) || data.suggestions[0];
                const firm = data.suggestions.find(s => s.tone_label.toLowerCase().includes('firm')) || data.suggestions[1] || data.suggestions[0];

                document.getElementById('nudge-collab-text').textContent = collab.suggested_text;
                document.getElementById('nudge-collab-ratio').textContent = collab.rationalization;

                document.getElementById('nudge-firm-text').textContent = firm.suggested_text;
                document.getElementById('nudge-firm-ratio').textContent = firm.rationalization;

                outputContainer.classList.remove('hidden');
            } else {
                alert(`Suggestions error: ${data.detail}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setButtonLoading(btnGetSuggestions, false);
        }
    });

    // Record Outcome execution
    const btnRecordOutcome = document.getElementById('btn-record-outcome');
    btnRecordOutcome.addEventListener('click', async () => {
        if (!isOnline) { alert('Backend is offline.'); return; }
        if (!sessionToken) { alert('Please login first.'); return; }

        const contactId = document.getElementById('outcome-contact-id').value;
        const goal = document.getElementById('suggest-target-goal').value;
        const status = document.getElementById('outcome-status').value;
        const notes = document.getElementById('outcome-notes').value;

        const payload = {
            session_token: sessionToken,
            contact_id: contactId,
            goal_statement: goal,
            outcome: status,
            user_notes: notes
        };

        updateInspector(payload, { status: 'recording negotiation outcome...' });
        setButtonLoading(btnRecordOutcome, true, 'Recording...');

        try {
            const res = await fetch(`${BACKEND_URL}/api/v1/negotiation/outcome`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            updateInspector(payload, data);

            if (res.ok) {
                document.getElementById('outcome-status-val').textContent = `Outcome successfully recorded! Session ID: ${data.session_id}`;
                document.getElementById('outcome-output-container').classList.remove('hidden');
            } else {
                alert(`Outcome error: ${data.detail}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setButtonLoading(btnRecordOutcome, false);
        }
    });

    // Interactive clickable suggestion nudges
    document.querySelector('.nudge-collab').addEventListener('click', () => {
        const text = document.getElementById('nudge-collab-text').textContent;
        if (text && text !== '...') {
            appendTurnToHistory('user', text);
            appendTurnToHistory('counterpart', '');
        }
    });

    document.querySelector('.nudge-firm').addEventListener('click', () => {
        const text = document.getElementById('nudge-firm-text').textContent;
        if (text && text !== '...') {
            appendTurnToHistory('user', text);
            appendTurnToHistory('counterpart', '');
        }
    });

    // Download conversation history as a text file
    document.getElementById('btn-download-chat').addEventListener('click', () => {
        const history = getTranscriptData('suggest-history-list');
        if (history.length === 0) {
            alert('No conversation turns to download.');
            return;
        }
        let content = '';
        history.forEach(turn => {
            const sender = turn.sender === 'user' ? 'User (You)' : 'Counterpart';
            content += `${sender}: ${turn.message}\n`;
        });
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'negotiation_transcript.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // Update persona using this conversation (pass turns to distill.html via sessionStorage)
    document.getElementById('btn-update-persona-go').addEventListener('click', () => {
        const history = getTranscriptData('suggest-history-list');
        if (history.length === 0) {
            alert('No conversation turns to update persona.');
            return;
        }
        sessionStorage.setItem('pending_transcript', JSON.stringify(history));
        alert('Conversation stored. Redirecting to Persona Distiller...');
        window.location.href = 'distill.html';
    });
});

// Helper: Add custom row to history list
function addHistoryRow(listId) {
    const list = document.getElementById(listId);
    const newRow = document.createElement('div');
    newRow.className = 'history-row';
    newRow.innerHTML = `
        <select class="history-sender">
            <option value="user">User (You)</option>
            <option value="counterpart">Counterpart</option>
        </select>
        <input type="text" class="history-msg" placeholder="Message content">
        <button class="btn btn-danger btn-sm btn-delete-row">×</button>
    `;
    list.appendChild(newRow);
}

// Helper: Extract data from dynamic history list
function getTranscriptData(listId) {
    const list = document.getElementById(listId);
    const rows = list.querySelectorAll('.history-row');
    const data = [];
    rows.forEach(row => {
        const sender = row.querySelector('.history-sender').value;
        const msg = row.querySelector('.history-msg').value.trim();
        if (msg) {
            data.push({ sender: sender, message: msg });
        }
    });
    return data;
}

// Helper: Append a turn dynamically to history
function appendTurnToHistory(sender, text) {
    const list = document.getElementById('suggest-history-list');
    const newRow = document.createElement('div');
    newRow.className = 'history-row';
    newRow.innerHTML = `
        <select class="history-sender">
            <option value="user" ${sender === 'user' ? 'selected' : ''}>User (You)</option>
            <option value="counterpart" ${sender === 'counterpart' ? 'selected' : ''}>Counterpart</option>
        </select>
        <input type="text" class="history-msg" value="${text}" placeholder="Message content">
        <button class="btn btn-danger btn-sm btn-delete-row">×</button>
    `;
    list.appendChild(newRow);
    newRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
