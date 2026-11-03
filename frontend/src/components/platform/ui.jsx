import React from 'react';

/** Shared pieces of the admin console's dashboards (AI costs, analytics). */

export const num = (n) => Number(n || 0).toLocaleString('en-IN');
export const pct = (r) => `${Math.round(Number(r || 0) * 100)}%`;
export const inr = (n) => `₹${Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
export const usd = (n) => {
    const v = Number(n || 0);
    if (v === 0) return '$0';
    return v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(2)}`;
};

/** "↑ 12%" / "↓ 5%" against the previous period: an arrow and words, so it never relies on colour. */
export const Change = ({ change, days, invert = false }) => {
    if (change === null || change === undefined) return <span className="text-[#5E5046]">no earlier data to compare</span>;
    const flat = Math.abs(change) < 0.005;
    const up = change > 0;
    const good = flat ? null : up !== invert;
    const cls = good === null ? 'text-[#5E5046]' : good ? 'text-[#1E5C42]' : 'text-rose-700';
    return (
        <span className={cls}>
            {flat ? '→ no change' : `${up ? '↑' : '↓'} ${Math.abs(Math.round(change * 100))}%`}
            <span className="text-[#5E5046]"> vs previous {days} days</span>
        </span>
    );
};

export const Stat = ({ label, value, hint, children }) => (
    <div className="rounded-2xl border border-[#E6D5CC] bg-white p-4">
        <div className="text-sm text-[#5E5046]">{label}</div>
        <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
        {hint && <div className="mt-0.5 text-xs text-[#5E5046]">{hint}</div>}
        {children && <div className="mt-0.5 text-xs">{children}</div>}
    </div>
);

export const Table = ({ title, note, columns, rows, empty, minWidth = 520 }) => (
    <section className="mt-6">
        {title && <h3 className="mb-1 font-bold">{title}</h3>}
        {note && <p className="mb-2 text-xs text-[#5E5046]">{note}</p>}
        <div className="overflow-x-auto rounded-2xl border border-[#E6D5CC] bg-white">
            <table className="w-full text-sm" style={{ minWidth }}>
                <thead>
                    <tr className="border-b border-[#E6D5CC] text-left text-[#5E5046]">
                        {columns.map(([key, label, align]) => (
                            <th key={key} className={`px-3 py-2 font-semibold ${align === 'right' ? 'text-right' : ''}`}>{label}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 && (
                        <tr><td colSpan={columns.length} className="px-3 py-4 text-[#5E5046]">{empty}</td></tr>
                    )}
                    {rows.map((r, i) => (
                        <tr key={i} className="border-b border-[#F3E9E2] last:border-0">
                            {columns.map(([key, , align, fmt]) => (
                                <td key={key} className={`px-3 py-2 ${align === 'right' ? 'text-right tabular-nums' : ''}`}>
                                    {fmt ? fmt(r[key], r) : r[key]}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    </section>
);
