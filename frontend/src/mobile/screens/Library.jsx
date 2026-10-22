import React, { useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Store, RefreshCw, X } from 'lucide-react';
import { useBooks } from '../data';
import { Screen, ScreenHeader, IconButton } from '../ui';
import { BookCover } from './Home';
import { tap } from '../device';

/** All of the student's books, with search and pull to refresh. */
const Library = () => {
    const navigate = useNavigate();
    const { books, loading, error, refresh } = useBooks();
    const [query, setQuery] = useState('');
    const [searching, setSearching] = useState(false);
    const [pull, setPull] = useState(0);
    const [refreshing, setRefreshing] = useState(false);
    const start = useRef(null);

    const shown = useMemo(() => {
        const q = query.trim().toLowerCase();
        return q ? books.filter((b) => b.name.toLowerCase().includes(q)) : books;
    }, [books, query]);

    const onTouchStart = (e) => { start.current = window.scrollY <= 0 ? e.touches[0].clientY : null; };
    const onTouchMove = (e) => {
        if (start.current == null) return;
        const d = e.touches[0].clientY - start.current;
        setPull(d > 0 ? Math.min(90, d * 0.5) : 0);
    };
    const onTouchEnd = async () => {
        if (pull > 60) {
            tap('medium');
            setRefreshing(true);
            await refresh();
            setRefreshing(false);
        }
        setPull(0);
        start.current = null;
    };

    return (
        <Screen className="m-tab-space" style={{}}>
            <ScreenHeader
                title="Books"
                subtitle={books.length ? `${books.length} ${books.length === 1 ? 'book' : 'books'}` : undefined}
                right={(
                    <div className="flex gap-2">
                        <IconButton icon={searching ? X : Search} label="Search" onClick={() => { setSearching((s) => !s); setQuery(''); }} />
                        <IconButton icon={Store} label="Free books" onClick={() => navigate('/bookstore')} />
                    </div>
                )}
            />
            <div onTouchStart={onTouchStart} onTouchMove={onTouchMove} onTouchEnd={onTouchEnd}>
                <div className="flex items-center justify-center overflow-hidden transition-[height]" style={{ height: refreshing ? 48 : pull }}>
                    <RefreshCw className={`h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} style={{ color: 'var(--m-accent)', transform: `rotate(${pull * 4}deg)` }} />
                </div>

                {searching && (
                    <div className="px-4 pb-3">
                        <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search your books"
                            className="h-12 w-full rounded-2xl px-4 text-[15px] outline-none" style={{ background: 'var(--m-soft)', color: 'var(--m-text)' }} />
                    </div>
                )}

                {error && !books.length && (
                    <div className="mx-4 rounded-2xl p-4 text-[14px]" style={{ background: 'var(--m-soft)' }}>
                        Couldn't load your books. The server may be waking up. <button onClick={refresh} className="font-bold" style={{ color: 'var(--m-accent)' }}>Try again</button>
                    </div>
                )}

                <div className="grid grid-cols-2 gap-x-3 gap-y-4 px-4">
                    {loading && !books.length && [0, 1, 2, 3].map((i) => <div key={i} className="m-skeleton h-44" />)}
                    {shown.map((b, i) => (
                        <motion.div key={b.id} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: Math.min(i, 10) * 0.03 }}>
                            <BookCover book={b} size="lg" onClick={() => navigate(`/app/book/${b.id}`)} />
                        </motion.div>
                    ))}
                    {!loading && (
                        <button onClick={() => { tap('medium'); window.dispatchEvent(new Event('lumina-add')); }}
                            className="m-pressable flex h-44 flex-col items-center justify-center gap-2 rounded-[18px] border-2 border-dashed" style={{ borderColor: 'var(--m-border)', color: 'var(--m-muted)' }}>
                            <Plus className="h-8 w-8" />
                            <span className="text-[13px] font-bold">New book</span>
                        </button>
                    )}
                </div>
                {query && !shown.length && <p className="px-6 pt-6 text-center text-[14px]" style={{ color: 'var(--m-muted)' }}>No book matches "{query}".</p>}
            </div>
        </Screen>
    );
};

export default Library;
