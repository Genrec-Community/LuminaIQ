import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { prepareMath } from '../utils/math';

const KATEX = [rehypeKatex, { throwOnError: false, strict: 'ignore', output: 'htmlAndMathml' }];
const REMARK = [remarkGfm, remarkMath];

// Inline mode renders into a <span>: for quiz options, flashcard sides and labels, which
// sit inside buttons and headings where a <p> isn't allowed.
const INLINE = {
    p: ({ children }) => <>{children}</>,
};

/**
 * The app's one Markdown renderer: tables and lists (GFM) plus maths ($...$, $$...$$, and
 * \( \) / \[ \] which are normalised). `streaming` holds back a formula until it's closed.
 */
const Markdown = React.memo(({ children, streaming = false, inline = false, components, className }) => {
    const text = prepareMath(typeof children === 'string' ? children : String(children ?? ''), streaming);
    const body = (
        <ReactMarkdown remarkPlugins={REMARK} rehypePlugins={[KATEX]}
            components={inline ? { ...INLINE, ...components } : components}>
            {text}
        </ReactMarkdown>
    );
    if (inline) return <span className={className}>{body}</span>;
    return className ? <div className={className}>{body}</div> : body;
});

export default Markdown;
