/**
 * Storage Provider interface.
 *
 * Defines the contract for all storage backends. Every storage operation
 * in the application must go through this abstraction — never call
 * localStorage, sessionStorage, or any file-system API directly.
 *
 * Implementations:
 *   - LocalStorageProvider  (development, localStorage-backed)
 *   - R2StorageProvider     (future: Cloudflare R2 / S3-compatible)
 */

export interface UploadResult {
  /** Unique identifier for the stored object */
  id: string;
  /** The key/path under which the object was stored */
  key: string;
  /** Size in bytes */
  size: number;
  /** MIME type of the stored object */
  mimeType: string;
  /** ISO-8601 timestamp of when the object was stored */
  createdAt: string;
}

export interface FileMetadata {
  /** Unique identifier for the stored object */
  id: string;
  /** The key/path under which the object is stored */
  key: string;
  /** Size in bytes */
  size: number;
  /** MIME type */
  mimeType: string;
  /** ISO-8601 timestamp of creation */
  createdAt: string;
  /** ISO-8601 timestamp of last modification */
  updatedAt: string;
  /** Arbitrary metadata key-value pairs */
  metadata: Record<string, string>;
}

export interface StorageProvider {
  /**
   * Upload a file or blob to storage.
   * @param file - The File or Blob to store
   * @param key  - Optional storage key; auto-generated if omitted
   * @returns UploadResult with the assigned id and key
   */
  upload(file: File | Blob, key?: string): Promise<UploadResult>;

  /**
   * Retrieve a download URL for a stored object.
   * @param id - The object's unique identifier
   * @returns A URL string that can be used to download the object
   */
  download(id: string): Promise<string>;

  /**
   * Permanently delete a stored object.
   * @param id - The object's unique identifier
   */
  delete(id: string): Promise<void>;

  /**
   * Get metadata for a stored object without downloading its contents.
   * @param id - The object's unique identifier
   * @returns FileMetadata
   */
  getMetadata(id: string): Promise<FileMetadata>;

  /**
   * List all stored object keys (optionally filtered by prefix).
   * @param prefix - Optional key prefix to filter by
   */
  list(prefix?: string): Promise<string[]>;
}
