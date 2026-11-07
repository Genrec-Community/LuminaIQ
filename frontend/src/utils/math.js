/**
 * Maths in Markdown, ready for KaTeX (remark-math + rehype-katex).
 *
 * normalizeMath(): models also write \( ... \) and \[ ... \]; the renderer only understands
 * $ ... $ and $$ ... $$. Code blocks are left alone.
 * hideUnfinishedMath(): while an answer streams in, a formula that has opened but not yet
 * closed would flash as raw LaTeX (or swallow the rest of the text). Hold it back until it closes.
 */

const splitCode = (text) => text.split(/(```[\s\S]*?```|`[^`\n]*`)/g);

export const normalizeMath = (text) => {
    if (!text || (!text.includes('\\(') && !text.includes('\\[') && !text.includes('$$'))) return text || '';
    return splitCode(text).map((part, i) => {
        if (i % 2 === 1) return part;   // code
        return part
            .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `\n$$\n${m.trim()}\n$$\n`)
            .replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m.trim()}$`)
            // "$$...$$" alone on a line is a display formula: put the fences on their own lines
            .replace(/^[ \t]*\$\$([^\n$]+?)\$\$[ \t]*$/gm, (_, m) => `$$\n${m.trim()}\n$$`);
    }).join('');
};

// Positions of unescaped $ signs outside code
const dollarRuns = (text) => {
    const runs = [];
    const re = /(\\*)(\${1,2})/g;
    let m;
    while ((m = re.exec(text))) {
        if (m[1].length % 2 === 1) continue;            // \$ is a literal dollar
        runs.push({ index: m.index + m[1].length, len: m[2].length });
    }
    return runs;
};

export const hideUnfinishedMath = (text) => {
    if (!text || !text.includes('$')) return text || '';
    const parts = splitCode(text);
    const lastIdx = parts.length - 1;
    // An unclosed code block at the very end is still being written: leave it alone
    const last = parts[lastIdx];
    const runs = dollarRuns(last);
    const block = runs.filter((r) => r.len === 2);
    let cut = -1;
    if (block.length % 2 === 1) cut = block[block.length - 1].index;
    else {
        // single $ ... $ only pairs within a paragraph
        const paraStart = last.lastIndexOf('\n\n') + 1;
        const singles = runs.filter((r) => r.len === 1 && r.index >= paraStart);
        if (singles.length % 2 === 1) cut = singles[singles.length - 1].index;
    }
    if (cut === -1) return text;
    parts[lastIdx] = last.slice(0, cut);
    return parts.join('');
};

export const prepareMath = (text, streaming = false) => {
    const normal = normalizeMath(text);
    return streaming ? hideUnfinishedMath(normal) : normal;
};
