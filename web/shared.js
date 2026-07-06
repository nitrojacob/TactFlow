const BACKEND_URL = 'http://localhost:8000';

// Global state
let sessionToken = localStorage.getItem('session_token') || '';
let isOnline = false;

// Intercept all fetch requests to handle Session not found / expired redirects
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const response = await originalFetch(...args);
    if (response.status === 401) {
        try {
            const clone = response.clone();
            const data = await clone.json();
            if (data && (
                data.detail === "Session not found" || 
                data.detail === "Session expired" || 
                data.detail === "Invalid session token checksum"
            )) {
                alert("Session expired or invalid. Logging out...");
                logout();
            }
        } catch (e) {
            // Non-JSON or parsing error, ignore
        }
    }
    return response;
};

// DOM Elements (if they exist on the page)
let connectionStatus, tokenBadgeContainer, activeTokenVal, requestInspector, responseInspector;

document.addEventListener('DOMContentLoaded', () => {
    connectionStatus = document.getElementById('connection-status');
    tokenBadgeContainer = document.getElementById('token-badge-container');
    activeTokenVal = document.getElementById('active-token-val');
    requestInspector = document.getElementById('json-request');
    responseInspector = document.getElementById('json-response');

    // Force redirection to login if token is missing (except on index.html itself)
    const isLoginPage = window.location.pathname.endsWith('index.html') || window.location.pathname === '/' || window.location.pathname.endsWith('/');
    if (!sessionToken && !isLoginPage) {
        window.location.href = 'index.html';
        return;
    }

    // Display active token
    if (sessionToken && activeTokenVal) {
        updateTokenDisplay(sessionToken);
    }

    // Bind Logout action if exists
    const btnLogout = document.getElementById('btn-logout');
    if (btnLogout) {
        btnLogout.addEventListener('click', () => {
            logout();
        });
    }

    // Start backend health check ping
    checkBackendHealth();
    setInterval(checkBackendHealth, 3000);
});

// Update session token UI
function updateTokenDisplay(token) {
    sessionToken = token;
    if (token) {
        localStorage.setItem('session_token', token);
        if (activeTokenVal) {
            activeTokenVal.textContent = token.substring(0, 15) + '...';
        }
        if (tokenBadgeContainer) {
            tokenBadgeContainer.classList.remove('hidden');
        }
    } else {
        localStorage.removeItem('session_token');
        if (activeTokenVal) {
            activeTokenVal.textContent = 'None';
        }
        if (tokenBadgeContainer) {
            tokenBadgeContainer.classList.add('hidden');
        }
    }
}

// Logout helper
function logout() {
    updateTokenDisplay('');
    window.location.href = 'index.html';
}

// Update JSON Request/Response Inspector
function updateInspector(request, response) {
    if (requestInspector) {
        requestInspector.textContent = JSON.stringify(request, null, 2);
    }
    if (responseInspector) {
        responseInspector.textContent = JSON.stringify(response, null, 2);
    }
}

// Check if Backend is running
async function checkBackendHealth() {
    if (!connectionStatus) return;
    const indicator = connectionStatus.querySelector('.status-indicator');
    const statusText = connectionStatus.querySelector('.status-text');
    
    try {
        const res = await fetch(`${BACKEND_URL}/docs`, {
            method: 'GET'
        });
        if (res.ok) {
            isOnline = true;
            indicator.className = 'status-indicator online';
            statusText.textContent = 'Backend Online';
        } else {
            throw new Error('Not OK');
        }
    } catch (e) {
        isOnline = false;
        indicator.className = 'status-indicator offline';
        statusText.textContent = 'Backend Offline';
    }
}

// Utility to handle button loading state
function setButtonLoading(btn, isLoading, loadingText = '') {
    if (!btn) return;
    if (isLoading) {
        btn.dataset.originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span> ${loadingText}`;
    } else {
        btn.disabled = false;
        if (btn.dataset.originalHtml) {
            btn.innerHTML = btn.dataset.originalHtml;
        }
    }
}

// Fetch Decrypted Profile Details and populate target div
async function fetchProfileDetails(contactId, targetDivId, containerIdToReveal = '') {
    if (!isOnline || !sessionToken) return;
    
    const payload = {
        session_token: sessionToken,
        contact_id: contactId
    };
    
    try {
        const res = await fetch(`${BACKEND_URL}/api/v1/profile/retrieve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        updateInspector(payload, data);
        
        if (res.ok) {
            const profile = data.profile;
            const targetDiv = document.getElementById(targetDivId);
            if (!targetDiv) return;
            
            targetDiv.innerHTML = `
                <div class="profile-card-sub" style="grid-column: span 2;">
                    <h4>Metadata & Stance (Active Version: ${data.current_version})</h4>
                    <div class="profile-desc-field" style="margin-bottom: 0.5rem;">
                        <strong>Name:</strong> ${profile.metadata.name} | 
                        <strong>Role:</strong> ${profile.metadata.role} | 
                        <strong>Last Updated:</strong> ${profile.metadata.last_updated}
                    </div>
                </div>
                
                <div class="profile-card-sub">
                    <h4>Behavioral Traits</h4>
                    <ul>
                        ${profile.behavioral_traits.map(t => `<li>${t}</li>`).join('')}
                    </ul>
                </div>
                
                <div class="profile-card-sub">
                    <h4>Viewpoints & Positions</h4>
                    <ul>
                        ${profile.viewpoints_and_positions.map(v => `<li>${v}</li>`).join('')}
                    </ul>
                </div>
                
                <div class="profile-card-sub">
                    <h4>Negotiation Style</h4>
                    <div class="profile-desc-field">
                        <strong>Primary Conflict Mode:</strong> ${profile.negotiation_style.primary_mode}<br>
                        <strong>Concession Response:</strong> ${profile.negotiation_style.concession_response}<br>
                        <strong>Behavior:</strong> ${profile.negotiation_style.description}
                    </div>
                </div>
                
                <div class="profile-card-sub">
                    <h4>Cognitive Style & Triggers</h4>
                    <div class="profile-desc-field">
                        <strong>Decision Processing:</strong> ${profile.decision_making_style.cognitive_mode} (${profile.decision_making_style.evaluation_type})<br>
                        <strong>Description:</strong> ${profile.decision_making_style.description}<br>
                        <strong>Key Triggers:</strong> ${profile.cognitive_biases_and_triggers.primary_triggers.join(', ')}<br>
                        <strong>Trigger Details:</strong> ${profile.cognitive_biases_and_triggers.details}
                    </div>
                </div>
                
                <div class="profile-card-sub" style="grid-column: span 2;">
                    <h4>Communication Preferences</h4>
                    <div class="profile-desc-field">
                        <strong>Preferred Channel:</strong> ${profile.interaction_preferences.preferred_channel} | 
                        <strong>Format Needed:</strong> ${profile.interaction_preferences.formatting} | 
                        <strong>Tone Sensitivity:</strong> ${profile.interaction_preferences.tone_sensitivity}
                    </div>
                </div>
            `;
            
            if (containerIdToReveal) {
                const revealContainer = document.getElementById(containerIdToReveal);
                if (revealContainer) revealContainer.classList.remove('hidden');
            }
        }
    } catch (e) {
        console.error('Failed to retrieve profile details:', e);
    }
}

// Sync Contact ID across pages
function initContactIdSync(inputId) {
    const inputEl = document.getElementById(inputId);
    if (!inputEl) return;
    
    // Load existing
    const cached = localStorage.getItem('active_contact_id');
    if (cached) {
        inputEl.value = cached;
    }
    
    // Save on change
    inputEl.addEventListener('input', (e) => {
        localStorage.setItem('active_contact_id', e.target.value);
    });
}

// Automatically clear placeholder on click (focus) and restore on blur if empty
document.addEventListener('focusin', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.target.placeholder) {
            e.target.dataset.tempPlaceholder = e.target.placeholder;
            e.target.placeholder = '';
        }
    }
});
document.addEventListener('focusout', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.target.dataset.tempPlaceholder) {
            e.target.placeholder = e.target.dataset.tempPlaceholder;
            delete e.target.dataset.tempPlaceholder;
        }
    }
});
