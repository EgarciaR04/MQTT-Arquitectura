export interface FirmwareRelease {
  id: number;
  device_id: number;
  version: string;
  original_filename: string;
  file_size: number;
  status: 'ready' | 'notified';
  created_at: string;
  notified_at: string | null;
}
