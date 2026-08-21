/**
 * Shared chat utilities: source deduplication and file-to-data-URL conversion.
 */

/** Deduplicate a sources array by filename (keep first occurrence). */
export function dedupeSources(sources) {
  if (!Array.isArray(sources)) return [];
  const seen = new Set();
  const result = [];
  for (const src of sources) {
    if (!src || seen.has(src.filename)) continue;
    seen.add(src.filename);
    result.push(src);
  }
  return result;
}

/** Read a File/Blob into a Base64 data URL. */
export function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Max size for an attached image (10 MB raw → ~13.4 MB base64). */
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;