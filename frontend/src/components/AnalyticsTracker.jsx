import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { pagePath, sendAttribution, track } from '../utils/analytics';

/** Page views (paths without ids) and, once per user, where they first came from. */
const AnalyticsTracker = () => {
    const location = useLocation();
    const { user } = useAuth();

    useEffect(() => {
        const path = pagePath(location.pathname);
        track('page_view', { page: path });
    }, [location.pathname, location.search]);

    useEffect(() => {
        if (user?.id) sendAttribution(user.id);
    }, [user?.id]);

    return null;
};

export default AnalyticsTracker;
