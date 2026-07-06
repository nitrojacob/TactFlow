document.addEventListener('DOMContentLoaded', () => {
    // If already logged in, redirect directly to Nudge Generator page
    if (sessionToken) {
        window.location.href = 'nudge.html';
        return;
    }

    const btnLogin = document.getElementById('btn-login');

    btnLogin.addEventListener('click', async () => {
        if (!isOnline) {
            alert('Backend is offline. Please launch the FastAPI server first.');
            return;
        }

        const email = document.getElementById('login-email').value;
        const pwd = document.getElementById('login-password').value;
        const pass = document.getElementById('login-passphrase').value;

        const payload = {
            user_email: email,
            password_hash: pwd,
            encryption_key_passphrase: pass
        };

        updateInspector(payload, { status: 'loading...' });
        setButtonLoading(btnLogin, true, 'Initializing...');

        try {
            const res = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            updateInspector(payload, data);

            if (res.ok) {
                updateTokenDisplay(data.session_token);
                alert('Session initialized successfully! Redirecting to Nudge Generator...');
                window.location.href = 'nudge.html';
            } else {
                alert(`Login failed: ${data.detail}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setButtonLoading(btnLogin, false);
        }
    });
});
