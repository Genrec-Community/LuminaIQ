import React from 'react';
import { KeyRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ChangePasswordForm from './ChangePasswordForm';

/**
 * School-created accounts start with a password the school chose (or reset).
 * Before anything else, the student picks their own.
 */
const ForcePasswordChange = () => {
    const { user, updateUser, logout } = useAuth();
    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-[#FDF6F0] p-4">
            <div className="w-full max-w-md rounded-3xl border border-[#E6D5CC] bg-white p-6 sm:p-8 shadow-xl">
                <div className="mb-5 flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#C8A288] text-white"><KeyRound className="h-5 w-5" /></div>
                    <div>
                        <h1 className="text-xl font-bold text-[#4A3B32]">Choose your own password</h1>
                        <p className="text-sm text-[#8a6a5c]">Signed in as <span className="font-mono">{user?.login_id || user?.email}</span></p>
                    </div>
                </div>
                <p className="mb-4 text-sm text-[#8a6a5c]">Your school gave you this password. Pick a new one that only you know.</p>
                <ChangePasswordForm submitLabel="Save my password" onDone={() => updateUser({ must_change_password: false })} />
                <button onClick={logout} className="mt-4 w-full text-sm font-semibold text-[#8a6a5c] hover:text-[#4A3B32]">Sign out</button>
            </div>
        </div>
    );
};

export default ForcePasswordChange;
