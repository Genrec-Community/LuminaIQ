import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Trash2 } from 'lucide-react';
import { deleteAccount, apiErrorText } from '../api';
import { useAuth } from '../context/AuthContext';

/** Permanently delete the signed-in account. Used in web Settings; the phone app has its own sheet. */
const DeleteAccountForm = () => {
    const { logout } = useAuth();
    const navigate = useNavigate();
    const [confirm, setConfirm] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const submit = async (e) => {
        e.preventDefault();
        if (confirm !== 'DELETE') return;
        setBusy(true); setError('');
        try {
            await deleteAccount();
            try { localStorage.clear(); } catch { /* ignore */ }
            await logout();
            navigate('/', { replace: true });
        } catch (err) {
            setError(apiErrorText(err, 'Could not delete the account. Try again or email support@luminaiq.fun.'));
            setBusy(false);
        }
    };

    return (
        <form onSubmit={submit} className="space-y-3 rounded-2xl border border-red-200 bg-red-50/60 p-4">
            <p className="text-sm text-[#5a4a42]">
                This permanently deletes your account, your books and files, and everything you made in Lumina IQ. It can't be undone.{' '}
                <a href="/delete-account" className="font-semibold text-[#C8A288]">What gets deleted</a>
            </p>
            <input value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Type DELETE to confirm"
                className="w-full rounded-2xl border border-red-200 bg-white px-4 py-3 outline-none focus:ring-2 focus:ring-red-300 text-[#4A3B32]" />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button type="submit" disabled={busy || confirm !== 'DELETE'}
                className="inline-flex items-center gap-2 rounded-2xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                Delete my account
            </button>
        </form>
    );
};

export default DeleteAccountForm;
