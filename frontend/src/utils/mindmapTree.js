// The mindmaps API stores and returns a flat graph: { nodes: [{ id, label, level, parent }], edges: [{ from, to }] }.
// The Learning Path view (TopicMindmap) draws a tree: { label, children: [...] }. This turns one into the other.

export function mindmapToTree(data, fallbackLabel = '') {
    if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch { return null; }
    }
    const nodes = Array.isArray(data?.nodes) ? data.nodes.filter((n) => n && n.id != null) : [];
    if (!nodes.length) return null;

    const byId = new Map();
    nodes.forEach((n) => byId.set(String(n.id), { label: String(n.label ?? ''), children: [] }));

    // A node's parent comes from its own `parent` field, else from the first edge pointing at it.
    const parentOf = new Map();
    nodes.forEach((n) => {
        if (n.parent != null && byId.has(String(n.parent))) parentOf.set(String(n.id), String(n.parent));
    });
    (Array.isArray(data.edges) ? data.edges : []).forEach((e) => {
        const to = String(e?.to), from = String(e?.from);
        if (byId.has(to) && byId.has(from) && !parentOf.has(to)) parentOf.set(to, from);
    });

    // The root is the level-0 node, else the first node without a parent.
    const top = nodes.filter((n) => !parentOf.has(String(n.id)));
    const rootNode = top.find((n) => Number(n.level) === 0) || top[0] || nodes[0];
    const rootId = String(rootNode.id);
    const root = byId.get(rootId);

    // Attach every node once, following parent links that lead back to the root (cycles are cut).
    const reaches = (id) => {
        const seen = new Set();
        while (id !== rootId) {
            if (seen.has(id) || !parentOf.has(id)) return false;
            seen.add(id);
            id = parentOf.get(id);
        }
        return true;
    };
    nodes.forEach((n) => {
        const id = String(n.id);
        if (id === rootId) return;
        const parent = reaches(id) ? parentOf.get(id) : rootId; // stray nodes hang off the root
        byId.get(parent).children.push(byId.get(id));
    });

    if (!root.label) root.label = fallbackLabel;
    return root;
}
