/**
 * Storage — barrel exports.
 *
 * Usage:
 *   import { storage } from "@/services/storage/LocalStorageProvider";
 *   // or through the service registry:
 *   import { Services } from "@/services";
 *   Services.storage.upload(file);
 */

export type { StorageProvider, UploadResult, FileMetadata } from "./Provider";
export { LocalStorageProvider } from "./LocalStorageProvider";
