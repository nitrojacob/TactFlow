document.addEventListener('DOMContentLoaded', () => {
    // Initial Contact ID Sync across pages
    initContactIdSync('rollback-contact-id');

    // View Profile Handler
    const btnViewProfile = document.getElementById('btn-view-profile');
    btnViewProfile.addEventListener('click', async () => {
        const contactId = document.getElementById('rollback-contact-id').value;
        document.getElementById('rollback-output-container').classList.add('hidden');
        setButtonLoading(btnViewProfile, true, 'Retrieving...');
        try {
            await fetchProfileDetails(contactId, 'rollback-profile-details', 'rollback-output-container');
        } finally {
            setButtonLoading(btnViewProfile, false);
        }
    });

    // Rollback Profile Handler
    const btnRollbackProfile = document.getElementById('btn-rollback-profile');
    btnRollbackProfile.addEventListener('click', async () => {
        if (!isOnline) { alert('Backend is offline.'); return; }
        if (!sessionToken) { alert('Please login first.'); return; }

        const contactId = document.getElementById('rollback-contact-id').value;
        const versionId = document.getElementById('rollback-version-id').value;

        const payload = {
            session_token: sessionToken,
            contact_id: contactId,
            version_id: versionId
        };

        updateInspector(payload, { status: 'rolling back profile version...' });
        setButtonLoading(btnRollbackProfile, true, 'Rolling back...');

        try {
            const res = await fetch(`${BACKEND_URL}/api/v1/profile/rollback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            updateInspector(payload, data);

            if (res.ok) {
                alert(`Profile rolled back successfully to version: ${versionId}`);
                await fetchProfileDetails(contactId, 'rollback-profile-details', 'rollback-output-container');
            } else {
                alert(`Rollback error: ${data.detail}`);
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setButtonLoading(btnRollbackProfile, false);
        }
    });
});
