import { MessageSquare, CheckSquare, Layers, Zap, Plus } from 'lucide-react';
import { useTools } from '../context/ToolsContext';
import { useGamification } from '../context/GamificationContext';

/**
 * Home for Class 5-10 learners: four big, clear choices instead of a busy
 * dashboard. Each opens their current book on that tool.
 */
const CARDS = [
    { tool: 'chat', icon: MessageSquare, title: 'Ask a question', sub: 'Stuck? Ask anything from your book', color: '#3b8fd6' },
    { tool: 'quiz', icon: CheckSquare, title: 'Practise', sub: 'A quick quiz to test yourself', color: '#2f9e7a' },
    { tool: 'flashcards', icon: Layers, title: 'Revise', sub: 'Flip cards to remember', color: '#e46a91' },
    { tool: 'power', icon: Zap, title: "Today's goal", sub: 'Learn one topic, step by step', color: '#f59e0b' },
];

const SchoolHome = ({ name, bookName, onOpen, onAddBook }) => {
    const { has } = useTools();
    const { data: progress } = useGamification();
    const goal = progress?.daily_goal;
    const cards = CARDS.filter((c) => has(c.tool));
    return (
        <section className="mb-10" aria-labelledby="school-home-title">
            <h2 id="school-home-title" className="text-3xl md:text-4xl font-bold text-[#163628]">
                Hi {name}! 👋 What do you want to do?
            </h2>
            <p className="mt-1 mb-5 text-lg text-[#5E5046]">
                {bookName ? <>Your book: <b className="text-[#163628]">{bookName}</b></> : 'Add your textbook to begin.'}
            </p>
            {bookName ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {cards.map(({ tool, icon: Icon, title, sub, color }) => (
                        <button
                            key={tool}
                            type="button"
                            onClick={() => onOpen(tool)}
                            className="flex items-center gap-4 rounded-3xl border-2 border-[#E6D5CC] bg-white p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-[#1E5C42] hover:shadow-md active:scale-[0.98]"
                        >
                            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-white" style={{ background: color }}>
                                <Icon className="h-8 w-8" aria-hidden="true" />
                            </span>
                            <span className="min-w-0 flex-1">
                                <span className="block text-xl font-bold text-[#163628]">{title}</span>
                                {tool === 'power' && goal ? (
                                    <>
                                        <span className="block text-base text-[#5E5046]">
                                            {goal.completed ? 'Done for today! 🎉' : `Answer ${goal.target} questions${goal.focus?.topic ? ` about ${goal.focus.topic}` : ''}`}
                                        </span>
                                        <span className="mt-2 block h-2.5 overflow-hidden rounded-full bg-[#F2E6DB]" aria-hidden="true">
                                            <span className="block h-full rounded-full bg-[#f59e0b]"
                                                style={{ width: `${Math.min(100, (100 * goal.progress) / (goal.target || 1))}%` }} />
                                        </span>
                                        <span className="mt-1 block text-sm font-semibold text-[#5E5046]">{goal.progress} of {goal.target}</span>
                                    </>
                                ) : (
                                    <span className="block text-base text-[#5E5046]">{sub}</span>
                                )}
                            </span>
                        </button>
                    ))}
                </div>
            ) : (
                <button type="button" onClick={onAddBook}
                    className="flex w-full items-center justify-center gap-3 rounded-3xl bg-[#1E5C42] p-6 text-xl font-bold text-white hover:bg-[#163628]">
                    <Plus className="h-7 w-7" aria-hidden="true" /> Add my textbook
                </button>
            )}
        </section>
    );
};

export default SchoolHome;
