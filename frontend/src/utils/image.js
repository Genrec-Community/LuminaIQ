/**
 * Shrink a photo before upload: at most 1600 px on its longest side, JPEG ~85%.
 * Phone photos are often 4-12 MB; this makes them ~200-500 KB, which uploads fast on mobile
 * data and is plenty for reading a textbook question. Honours the photo's rotation.
 */
export const MAX_SIDE = 1600;

export const shrinkImage = async (file, maxSide = MAX_SIDE, quality = 0.85) => {
    if (!file || !file.type?.startsWith('image/')) throw new Error('Please choose a photo (JPG or PNG).');
    let bitmap;
    try {
        bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch {
        bitmap = await new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error("That photo couldn't be opened."));
            img.src = URL.createObjectURL(file);
        });
    }
    const w = bitmap.width, h = bitmap.height;
    const scale = Math.min(1, maxSide / Math.max(w, h));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fff';                      // transparent PNGs get a white page, not black
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    if (bitmap.close) bitmap.close();
    return canvas.toDataURL('image/jpeg', quality);
};

/** The student's own words, without the photo transcript the server adds for the tutor. */
export const PHOTO_MARKER = "[From the student's photo]";
export const visibleText = (content) => {
    const i = (content || '').indexOf(PHOTO_MARKER);
    return i === -1 ? content : content.slice(0, i).trim();
};
