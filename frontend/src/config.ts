export const SERVER_CARD_TAG = "unraid-server-card";
export const SERVER_EDITOR_TAG = "unraid-server-card-editor";

export const STORAGE_CARD_TAG = "unraid-storage-card";
export const STORAGE_EDITOR_TAG = "unraid-storage-card-editor";

export const DOCKER_CARD_TAG = "unraid-docker-card";
export const DOCKER_EDITOR_TAG = "unraid-docker-card-editor";

export const UPS_CARD_TAG = "unraid-ups-card";
export const UPS_EDITOR_TAG = "unraid-ups-card-editor";

export const VM_CARD_TAG = "unraid-vm-card";
export const VM_EDITOR_TAG = "unraid-vm-card-editor";

export const SHARES_CARD_TAG = "unraid-shares-card";
export const SHARES_EDITOR_TAG = "unraid-shares-card-editor";

export const NETWORK_CARD_TAG = "unraid-network-card";
export const NETWORK_EDITOR_TAG = "unraid-network-card-editor";

export const ZFS_CARD_TAG = "unraid-zfs-card";
export const ZFS_EDITOR_TAG = "unraid-zfs-card-editor";

export const FANS_CARD_TAG = "unraid-fans-card";
export const FANS_EDITOR_TAG = "unraid-fans-card-editor";

export const GPU_CARD_TAG = "unraid-gpu-card";
export const GPU_EDITOR_TAG = "unraid-gpu-card-editor";

export const NOTIFICATIONS_CARD_TAG = "unraid-notifications-card";
export const NOTIFICATIONS_EDITOR_TAG = "unraid-notifications-card-editor";

export const MAINTENANCE_CARD_TAG = "unraid-maintenance-card";
export const MAINTENANCE_EDITOR_TAG = "unraid-maintenance-card-editor";

export const REMOTE_SHARES_CARD_TAG = "unraid-remote-shares-card";
export const REMOTE_SHARES_EDITOR_TAG = "unraid-remote-shares-card-editor";

export const UNASSIGNED_DEVICES_CARD_TAG = "unraid-unassigned-devices-card";
export const UNASSIGNED_DEVICES_EDITOR_TAG = "unraid-unassigned-devices-card-editor";

export const DASHBOARD_CARD_TAG = "unraid-dashboard-card";
export const DASHBOARD_EDITOR_TAG = "unraid-dashboard-card-editor";

export interface CardConfig {
  type: string;
  server?: string;
  name?: string;
  title?: string;
  view_mode?: "grid" | "list";
  show_system_info?: boolean;
  show_motherboard?: boolean;
  show_user_shares?: boolean;
  embedded?: boolean;
  hide_header?: boolean;
  [key: string]: unknown;
}
