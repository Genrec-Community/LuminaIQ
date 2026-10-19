import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2, GraduationCap, AlertTriangle } from 'lucide-react';
import { joinWithCode } from '../api';
import { emitPlanChanged } from '../utils/plan';

const errText = (e) => e?.response?.data?.detail?.message || e?.response?.data?.detail || 'Could not join. Please try again.';

/** Invite link: /join/<code>. Joins the class, then opens its books. */
const JoinClass = () => {
    const { code } = useParams();
    const navigate = useNavigate();
    const [state, setState] = useState({ status: 'joining' });
    const started = useRef(false);

    useEffect(() => {
        if (started.current) return;
        started.current = true;
        joinWithCode(code)
            .then((r) => {
                emitPlanChanged();
                setState({ status: 'joined', ...r });
                if (r.project_id) setTimeout(() => navigate(`/project/${r.project_id}`, { replace: true }), 1400);
            })
            .catch((e) => setState({ status: 'error', message: errText(e) }));
    }, [code, navigate]);

    return (
        <div className="min-h-[100dvh] bg-[#FDF6F0] flex items-center justify-center p-6">
            <div className="max-w-md w-full rounded-3xl border border-[#E6D5CC] bg-white p-8 text-center">
                {state.status === 'joining' && <><Loader2 className="mx-auto h-10 w-10 animate-spin text-[#C8A288]" /><p className="mt-3 text-[#8a6a5c]">Joining your class…</p></>}
                {state.status === 'joined' && (
                    <>
                        <GraduationCap className="mx-auto h-12 w-12 text-[#C8A288]" />
                        <h1 className="mt-3 text-2xl font-bold text-[#4A3B32]">You're in!</h1>
                        <p className="mt-1 text-[#8a6a5c]">{state.class ? `${state.class} · ${state.institution}` : `Teacher at ${state.institution}`}</p>
                        {!state.project_id && (
                            <button onClick={() => navigate('/institution')} className="mt-6 w-full rounded-2xl bg-[#C8A288] px-4 py-3 font-semibold text-white">Open institution</button>
                        )}
                    </>
                )}
                {state.status === 'error' && (
                    <>
                        <AlertTriangle className="mx-auto h-10 w-10 text-amber-500" />
                        <p className="mt-3 text-[#4A3B32]">{state.message}</p>
                        <button onClick={() => navigate('/dashboard')} className="mt-6 w-full rounded-2xl border-2 border-[#E6D5CC] px-4 py-3 font-semibold text-[#4A3B32]">Go to dashboard</button>
                    </>
                )}
            </div>
        </div>
    );
};

export default JoinClass;
