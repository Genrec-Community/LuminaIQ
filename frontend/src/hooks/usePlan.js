import { useCallback, useEffect, useState } from 'react';
import { getMyPlan } from '../api';
import { LIMIT_EVENT, PLAN_EVENT } from '../utils/plan';

/** Current plan + usage; refreshes after purchases and whenever a limit is hit. */
export default function usePlan() {
    const [plan, setPlan] = useState(null);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            setPlan(await getMyPlan());
        } catch {
            /* billing unavailable: UI treats plan as unknown */
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
        window.addEventListener(PLAN_EVENT, refresh);
        window.addEventListener(LIMIT_EVENT, refresh);
        return () => {
            window.removeEventListener(PLAN_EVENT, refresh);
            window.removeEventListener(LIMIT_EVENT, refresh);
        };
    }, [refresh]);

    return { plan, loading, refresh };
}
