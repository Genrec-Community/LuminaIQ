// Page to return to after signing in (set by Login from ?next=, used by Dashboard
// for sign-in methods that redirect through /dashboard).
export const AFTER_LOGIN_KEY = 'lumina_after_login';

export const takeAfterLogin = () => {
    try {
        const next = sessionStorage.getItem(AFTER_LOGIN_KEY);
        sessionStorage.removeItem(AFTER_LOGIN_KEY);
        return next && next.startsWith('/') && !next.startsWith('//') ? next : null;
    } catch {
        return null;
    }
};
