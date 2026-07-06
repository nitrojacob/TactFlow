document.addEventListener('DOMContentLoaded', () => {
    // Initial Contact ID Sync across pages
    initContactIdSync('distill-contact-id');

    // Check for pending conversation data passed from nudge.html
    const pendingTranscript = sessionStorage.getItem('pending_transcript');
    if (pendingTranscript) {
        try {
            const turns = JSON.parse(pendingTranscript);
            if (turns && turns.length > 0) {
                // Clear default template rows
                const list = document.getElementById('distill-transcript-list');
                if (list) {
                    list.innerHTML = '';
                    // Populate rows
                    turns.forEach(turn => {
                        addHistoryRow('distill-transcript-list', turn.sender, turn.message);
                    });
                }
            }
        } catch (e) {
            console.error('Error parsing pending transcript:', e);
        } finally {
            sessionStorage.removeItem('pending_transcript');
        }
    }

    // Row management inside Distill list
    document.getElementById('btn-distill-add-row').addEventListener('click', () => {
        addHistoryRow('distill-transcript-list');
    });

    // Import Transcript File Handler
    const btnImport = document.getElementById('btn-import-transcript');
    const fileInput = document.getElementById('import-file-input');
    
    if (btnImport && fileInput) {
        btnImport.addEventListener('click', () => {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (event) => {
                const text = event.target.result;
                const lines = text.split('\n');
                const turns = [];
                
                lines.forEach(line => {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('User (You):')) {
                        const msg = trimmed.substring('User (You):'.length).trim();
                        turns.push({ sender: 'user', message: msg });
                    } else if (trimmed.startsWith('Counterpart:')) {
                        const msg = trimmed.substring('Counterpart:'.length).trim();
                        turns.push({ sender: 'counterpart', message: msg });
                    }
                });
                
                if (turns.length > 0) {
                    const list = document.getElementById('distill-transcript-list');
                    list.innerHTML = '';
                    turns.forEach(turn => {
                        addHistoryRow('distill-transcript-list', turn.sender, turn.message);
                    });
                    alert(`Successfully imported ${turns.length} turns from file!`);
                } else {
                    alert('Could not find any valid conversation turns in the file. Ensure it is a text file downloaded from the Nudge Generator.');
                }
                fileInput.value = '';
            };
            reader.readAsText(file);
        });
    }

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

    // Run Distillation Task
    const btnRunDistillation = document.getElementById('btn-run-distillation');
    btnRunDistillation.addEventListener('click', async () => {
        if (!isOnline) { alert('Backend is offline.'); return; }
        if (!sessionToken) { alert('Please login first.'); return; }

        const contactId = document.getElementById('distill-contact-id').value;
        const transcript = getTranscriptData('distill-transcript-list');

        const payload = {
            session_token: sessionToken,
            contact_id: contactId,
            raw_conversation_transcript: transcript
        };

        const outputContainer = document.getElementById('distill-output-container');
        outputContainer.classList.add('hidden');

        updateInspector(payload, { status: 'queueing distillation background task...' });
        setButtonLoading(btnRunDistillation, true, 'Distilling Persona...');

        try {
            const res = await fetch(`${BACKEND_URL}/api/v1/builder/distill`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            updateInspector(payload, data);

            if (res.ok) {
                document.getElementById('distill-task-id').textContent = data.job_id;
                document.getElementById('distill-task-status').textContent = 'Running';
                outputContainer.classList.remove('hidden');

                let progress = 0;
                const fill = document.getElementById('distill-progress-fill');
                fill.style.width = '0%';

                const interval = setInterval(async () => {
                    progress += 25;
                    fill.style.width = `${progress}%`;
                    if (progress >= 100) {
                        clearInterval(interval);
                        document.getElementById('distill-task-status').textContent = 'Completed';
                        fetchProfileDetails(contactId, 'profile-details-content');
                    }
                }, 1000);
            } else {
                alert(`Distillation error: ${data.detail}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setButtonLoading(btnRunDistillation, false);
        }
    });
});

// Helper: Add custom row to history list
function addHistoryRow(listId, sender = 'user', msg = '') {
    const list = document.getElementById(listId);
    const newRow = document.createElement('div');
    newRow.className = 'history-row';
    newRow.innerHTML = `
        <select class="history-sender">
            <option value="user" ${sender === 'user' ? 'selected' : ''}>User</option>
            <option value="counterpart" ${sender === 'counterpart' ? 'selected' : ''}>Counterpart</option>
        </select>
        <input type="text" class="history-msg" value="${msg}" placeholder="Message content">
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
