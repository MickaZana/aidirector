/**
 * LocalStorageProvider — development-only storage backend.
 *
 * Stores file data as base64-encoded data URIs in localStorage under the
 * key prefix "storage_". Suitable for development and testing only.
 *
 * NOT suitable for production:
 *   - localStorage has a ~5 MB quota per origin
 *   - Data is not encrypted
 *   - No cross-tab consistency guarantees
 */

import type { StorageProvider, UploadResult, FileMetadata } from "./Provider";

const STORAGE_PREFIX = "storage_";
const META_SUFFIX = "_meta";

function metaKey(id: string): string {
  return `${STORAGE_PREFIX}${id}${META_SUFFIX}`;
}

function dataKey(id: string): string {
  return `${STORAGE_PREFIX}${id}`;
}

function generateId(): string {
  return `local_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
}

export class LocalStorageProvider implements StorageProvider {
  async upload(file: File | Blob, key?: string): Promise<UploadResult> {
    const id = key ?? generateId();

    // Convert file/blob to base64 data URI
    const dataUri = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(new Error("Failed to read file"));
      reader.readAsDataURL(file);
    });

    const now = new Date().toISOString();
    const mimeType = file.type || "application/octet-stream";

    localStorage.setItem(dataKey(id), dataUri);
    localStorage.setItem(
      metaKey(id),
      JSON.stringify({
        id,
        key: id,
        size: file.size,
        mimeType,
        createdAt: now,
        updatedAt: now,
        metadata: {},
      } satisfies FileMetadata),
    );

    return { id, key: id, size: file.size, mimeType, createdAt: now };
  }

  async download(id: string): Promise<string> {
    const dataUri = localStorage.getItem(dataKey(id));
    if (!dataUri) {
      throw new Error(`Storage: object "${id}" not found`);
    }
    return dataUri;
  }

  async delete(id: string): Promise<void> {
    localStorage.removeItem(dataKey(id));
    localStorage.removeItem(metaKey(id));
  }

  async getMetadata(id: string): Promise<FileMetadata> {
    const raw = localStorage.getItem(metaKey(id));
    if (!raw) {
      throw new Error(`Storage: metadata for "${id}" not found`);
    }
    return JSON.parse(raw) as FileMetadata;
  }

  async list(prefix?: string): Promise<string[]> {
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (
        key &&
        key.startsWith(STORAGE_PREFIX) &&
        !key.endsWith(META_SUFFIX)
      ) {
        const id = key.slice(STORAGE_PREFIX.length);
        if (!prefix || id.startsWith(prefix)) {
          keys.push(id);
        }
      }
    }
    return keys;
  }

  /** Clear all locally stored objects (dev helper). */
  async clear(): Promise<void> {
    const keys = await this.list();
    for (const id of keys) {
      await this.delete(id);
    }
  }
}
