import * as tus from 'tus-js-client';
import { supabase } from '../supabaseClient';

/*
 * Book uploads go straight from the browser to Supabase Storage with the TUS
 * resumable protocol: 6 MB chunks, automatic retries, and after a refresh (or a
 * dropped connection) the same file continues from the last finished chunk.
 * The backend then fetches the file from storage (fast, server to server).
 */

const CHUNK_SIZE = 6 * 1024 * 1024; // Supabase requires exactly 6 MB chunks
const BUCKET = 'uploads';
const PENDING_KEY = 'lumina_pending_uploads';

const readPending = () => {
    try { return JSON.parse(localStorage.getItem(PENDING_KEY) || '[]'); } catch { return []; }
};
const writePending = (list) => {
    try { localStorage.setItem(PENDING_KEY, JSON.stringify(list)); } catch { /* storage unavailable */ }
};
const keyOf = (file) => `${file.name}|${file.size}|${file.lastModified}`;

/** Unfinished uploads for a project (shown after a refresh so the student can resume). */
export const pendingUploads = (projectId) => readPending().filter(u => u.projectId === projectId);

export const forgetPendingUpload = (key) => writePending(readPending().filter(u => u.key !== key));

const rememberPending = (entry) => {
    const list = readPending().filter(u => u.key !== entry.key);
    writePending([...list, entry]);
};

const safeName = (name) => name.normalize('NFKD').replace(/[^\w.-]+/g, '_').slice(-120);

/**
 * Upload a file to the user's folder in the "uploads" bucket.
 * Resolves with the storage path. Throws { fallback: true } when direct upload
 * can't be used (no Supabase session), so the caller can use the old route.
 */
export async function uploadToStorage(file, projectId, onProgress) {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.user?.id) {
        const err = new Error('No storage session');
        err.fallback = true;
        throw err;
    }
    const objectName = `${session.user.id}/${projectId}/${file.size}-${file.lastModified}-${safeName(file.name)}`;
    const key = keyOf(file);
    const entry = { key, projectId, name: file.name, size: file.size, pct: 0, startedAt: Date.now() };
    rememberPending(entry);

    await new Promise((resolve, reject) => {
        let lastSaved = 0;
        const upload = new tus.Upload(file, {
            endpoint: `${import.meta.env.VITE_SUPABASE_URL}/storage/v1/upload/resumable`,
            retryDelays: [0, 1000, 3000, 5000, 10000, 20000],
            chunkSize: CHUNK_SIZE,
            uploadDataDuringCreation: true,
            removeFingerprintOnSuccess: true,
            headers: { authorization: `Bearer ${session.access_token}`, apikey: import.meta.env.VITE_SUPABASE_ANON_KEY, 'x-upsert': 'true' },
            metadata: {
                bucketName: BUCKET,
                objectName,
                contentType: file.type || 'application/octet-stream',
                cacheControl: '3600',
            },
            // Long uploads can outlive the login token: always send the current one
            onBeforeRequest: async (req) => {
                const { data } = await supabase.auth.getSession();
                if (data.session?.access_token) req.setHeader('authorization', `Bearer ${data.session.access_token}`);
            },
            onProgress: (sent, total) => {
                const pct = total ? Math.round((sent / total) * 100) : 0;
                onProgress?.(pct, sent);
                if (pct - lastSaved >= 5) {
                    lastSaved = pct;
                    rememberPending({ ...entry, pct });
                }
            },
            onError: (error) => {
                // The server refused the upload itself (not a network drop): let the caller fall back
                const status = error?.originalResponse?.getStatus?.();
                if (status && status >= 400 && status < 500 && status !== 409) error.fallback = true;
                reject(error);
            },
            onSuccess: () => resolve(),
        });
        upload.findPreviousUploads().then((previous) => {
            if (previous.length) upload.resumeFromPreviousUpload(previous[0]);
            upload.start();
        }).catch(() => upload.start());
    });

    return { path: objectName, key };
}
