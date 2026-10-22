import * as tus from 'tus-js-client';
// Static import (not lazy): a lazily loaded chunk breaks in tabs opened before a redeploy
import { api } from '../api';

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
// Phones give a re-picked file a new lastModified time, so a file is recognised
// by its name and size only (that is what lets a resume continue, not restart).
const keyOf = (file) => `${file.name}|${file.size}`;

/** Unfinished uploads for a project (shown after a refresh so the student can resume). */
export const pendingUploads = (projectId) => readPending().filter(u => u.projectId === projectId);

export const forgetPendingUpload = (key) => writePending(readPending().filter(u => u.key !== key));

const rememberPending = (entry) => {
    const list = readPending().filter(u => u.key !== entry.key);
    writePending([...list, entry]);
};

const safeName = (name) => name.normalize('NFKD').replace(/[^\w.-]+/g, '_').slice(-120);

// Keep the screen on while uploading (phones otherwise sleep and cut the connection)
const keepAwake = () => {
    let lock = null;
    let active = true;
    const acquire = async () => {
        try { if (active && document.visibilityState === 'visible' && navigator.wakeLock) lock = await navigator.wakeLock.request('screen'); } catch { /* not supported or refused */ }
    };
    const onVisible = () => { if (document.visibilityState === 'visible') acquire(); };
    document.addEventListener('visibilitychange', onVisible);
    acquire();
    return () => {
        active = false;
        document.removeEventListener('visibilitychange', onVisible);
        try { lock?.release(); } catch { /* already released */ }
    };
};

// Resolves when the page is visible and online again
const whenBackOnline = () => new Promise((resolve) => {
    const ready = () => document.visibilityState === 'visible' && navigator.onLine !== false;
    if (ready()) { setTimeout(resolve, 1500); return; }
    const check = () => {
        if (!ready()) return;
        document.removeEventListener('visibilitychange', check);
        window.removeEventListener('online', check);
        setTimeout(resolve, 500);
    };
    document.addEventListener('visibilitychange', check);
    window.addEventListener('online', check);
});

/** Single PUT with the signed token (not resumable), with real progress. */
const putSigned = (file, bucket, path, token, onProgress) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', `${import.meta.env.VITE_SUPABASE_URL}/storage/v1/object/upload/sign/${bucket}/${path.split('/').map(encodeURIComponent).join('/')}?token=${encodeURIComponent(token)}`);
    xhr.setRequestHeader('x-upsert', 'true');
    xhr.setRequestHeader('apikey', import.meta.env.VITE_SUPABASE_ANON_KEY);
    xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100), e.loaded); };
    xhr.onload = () => (xhr.status < 300 ? resolve() : reject(Object.assign(new Error(`Upload failed (${xhr.status})`), { status: xhr.status })));
    xhr.onerror = () => reject(new Error('Upload failed (network)'));
    xhr.send(file);
});

/**
 * Upload a file to the user's folder in the "uploads" bucket.
 * The backend hands out a signed token for this one file, so it works for every
 * login method (email logins have no Supabase session in the browser).
 * Resolves with the storage path. Throws { fallback: true } when the direct
 * upload can't be used, so the caller can use the old route.
 */
export async function uploadToStorage(file, projectId, onProgress) {
    let permit;
    try {
        permit = (await api.post('/documents/upload-url', { project_id: projectId, filename: file.name, size: file.size })).data;
    } catch (e) {
        if (e?.response?.status && e.response.status < 500 && e.response.status !== 404) throw e; // limit, too big, wrong type
        const err = new Error('Upload permit unavailable');
        err.fallback = true;
        throw err;
    }
    const { bucket, path, token } = permit;
    const key = keyOf(file);
    const entry = { key, projectId, name: file.name, size: file.size, pct: 0, startedAt: Date.now() };
    rememberPending(entry);

    const release = keepAwake();
    try {
        await new Promise((resolve, reject) => {
            let lastSaved = 0;
            const upload = new tus.Upload(file, {
                endpoint: `${import.meta.env.VITE_SUPABASE_URL}/storage/v1/upload/resumable/sign`,
                retryDelays: [0, 1000, 3000, 5000, 10000, 20000, 30000],
                // Same file (name + size) in the same project = same upload, even after re-picking
                fingerprint: async () => ['lumina', path].join('|'),
                chunkSize: CHUNK_SIZE,
                uploadDataDuringCreation: true,
                removeFingerprintOnSuccess: true,
                headers: { 'x-signature': token, apikey: import.meta.env.VITE_SUPABASE_ANON_KEY, 'x-upsert': 'true' },
                metadata: {
                    bucketName: bucket,
                    objectName: path,
                    contentType: file.type || 'application/octet-stream',
                    cacheControl: '3600',
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
                    const status = error?.originalResponse?.getStatus?.();
                    if (!status) {
                        // Connection lost (screen off, signal, tab in background): wait, then carry on
                        // from the last finished chunk with the same file; nothing to re-pick
                        whenBackOnline().then(() => upload.start());
                        return;
                    }
                    reject(Object.assign(error, { status }));
                },
                onSuccess: () => resolve(),
            });
            upload.findPreviousUploads().then((previous) => {
                if (previous.length) upload.resumeFromPreviousUpload(previous[0]);
                upload.start();
            }).catch(() => upload.start());
        });
    } catch (tusError) {
        // Resumable refused (e.g. an expired token on an old resume): one plain upload with a fresh token
        console.warn('Resumable upload refused, uploading in one go', tusError?.status);
        try {
            const fresh = (await api.post('/documents/upload-url', { project_id: projectId, filename: file.name, size: file.size })).data;
            await putSigned(file, fresh.bucket, fresh.path, fresh.token, onProgress);
        } catch (putError) {
            putError.fallback = true;
            throw putError;
        }
    } finally {
        release();
    }

    return { path, key };
}
