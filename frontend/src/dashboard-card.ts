import { html, nothing, type TemplateResult } from "lit";
import {
  DASHBOARD_CARD_TAG,
  DASHBOARD_EDITOR_TAG,
} from "./config";
import { BaseUnraidCard } from "./dashboard-cards-base";
import { UnraidDashboardCardEditor } from "./dashboard-cards-editor";
import {
  iconTemplate,
  mdiBell,
  mdiDatabase,
  mdiDocker,
  mdiExpansionCard,
  mdiFan,
  mdiFlash,
  mdiFolder,
  mdiHarddisk,
  mdiHarddiskPlus,
  mdiLanConnect,
  mdiMonitor,
  mdiServer,
  mdiServerNetwork,
  mdiWrench,
} from "./icons";
import { registerDashboardCard } from "./register-dashboard-card";

import "./server-card";
import "./storage-card";
import "./shares-card";
import "./network-card";
import "./docker-card";
import "./ups-card";
import "./vm-card";
import "./zfs-card";
import "./fans-card";
import "./gpu-card";
import "./notifications-card";
import "./maintenance-card";
import "./remote-shares-card";
import "./unassigned-devices-card";

type ActiveTab =
  | "overview"
  | "storage"
  | "zfs"
  | "shares"
  | "remote-shares"
  | "unassigned"
  | "network"
  | "docker"
  | "vms"
  | "fans"
  | "gpu"
  | "ups"
  | "maintenance"
  | "notifications";

export class UnraidDashboardCard extends BaseUnraidCard {
  static override editorTag = DASHBOARD_EDITOR_TAG;

  static override properties = {
    ...BaseUnraidCard.properties,
    _activeTab: { state: true },
  };

  declare _activeTab: ActiveTab;

  constructor() {
    super();
    this._activeTab = "overview";
  }

  protected override render(): TemplateResult {
    const device = this.getActiveDevice();
    const serverName = this.config.title || device?.name_by_user || device?.name || "Unraid Server";

    return html`
      <ha-card style="gap: 12px;">
        <div class="header">
          <div class="header-main">
            <div class="header-icon">${iconTemplate(mdiServer, 22)}</div>
            <div class="header-titles">
              <span class="header-title">${serverName} Dashboard</span>
              <span class="header-subtitle">Unified Unraid Control Center</span>
            </div>
          </div>
        </div>
        <div class="tab-strip" style="display: flex; flex-wrap: wrap; gap: 6px;">
          <button
            class="tab-btn ${this._activeTab === "overview" ? "active" : ""}"
            @click=${() => (this._activeTab = "overview")}
          >
            ${iconTemplate(mdiServer, 14)} Overview
          </button>
          <button
            class="tab-btn ${this._activeTab === "storage" ? "active" : ""}"
            @click=${() => (this._activeTab = "storage")}
          >
            ${iconTemplate(mdiHarddisk, 14)} Storage
          </button>
          <button
            class="tab-btn ${this._activeTab === "zfs" ? "active" : ""}"
            @click=${() => (this._activeTab = "zfs")}
          >
            ${iconTemplate(mdiDatabase, 14)} ZFS
          </button>
          <button
            class="tab-btn ${this._activeTab === "shares" ? "active" : ""}"
            @click=${() => (this._activeTab = "shares")}
          >
            ${iconTemplate(mdiFolder, 14)} Shares
          </button>
          <button
            class="tab-btn ${this._activeTab === "remote-shares" ? "active" : ""}"
            @click=${() => (this._activeTab = "remote-shares")}
          >
            ${iconTemplate(mdiServerNetwork, 14)} Remote
          </button>
          <button
            class="tab-btn ${this._activeTab === "unassigned" ? "active" : ""}"
            @click=${() => (this._activeTab = "unassigned")}
          >
            ${iconTemplate(mdiHarddiskPlus, 14)} Unassigned
          </button>
          <button
            class="tab-btn ${this._activeTab === "network" ? "active" : ""}"
            @click=${() => (this._activeTab = "network")}
          >
            ${iconTemplate(mdiLanConnect, 14)} Network
          </button>
          <button
            class="tab-btn ${this._activeTab === "docker" ? "active" : ""}"
            @click=${() => (this._activeTab = "docker")}
          >
            ${iconTemplate(mdiDocker, 14)} Docker
          </button>
          <button
            class="tab-btn ${this._activeTab === "vms" ? "active" : ""}"
            @click=${() => (this._activeTab = "vms")}
          >
            ${iconTemplate(mdiMonitor, 14)} VMs
          </button>
          <button
            class="tab-btn ${this._activeTab === "fans" ? "active" : ""}"
            @click=${() => (this._activeTab = "fans")}
          >
            ${iconTemplate(mdiFan, 14)} Fans
          </button>
          <button
            class="tab-btn ${this._activeTab === "gpu" ? "active" : ""}"
            @click=${() => (this._activeTab = "gpu")}
          >
            ${iconTemplate(mdiExpansionCard, 14)} GPU
          </button>
          <button
            class="tab-btn ${this._activeTab === "ups" ? "active" : ""}"
            @click=${() => (this._activeTab = "ups")}
          >
            ${iconTemplate(mdiFlash, 14)} UPS
          </button>
          <button
            class="tab-btn ${this._activeTab === "maintenance" ? "active" : ""}"
            @click=${() => (this._activeTab = "maintenance")}
          >
            ${iconTemplate(mdiWrench, 14)} Maintenance
          </button>
          <button
            class="tab-btn ${this._activeTab === "notifications" ? "active" : ""}"
            @click=${() => (this._activeTab = "notifications")}
          >
            ${iconTemplate(mdiBell, 14)} Notifications
          </button>
        </div>
        <div>
          ${this._activeTab === "overview"
            ? html`<unraid-server-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-server-card", embedded: true }}></unraid-server-card>`
            : nothing}
          ${this._activeTab === "storage"
            ? html`<unraid-storage-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-storage-card", embedded: true }}></unraid-storage-card>`
            : nothing}
          ${this._activeTab === "zfs"
            ? html`<unraid-zfs-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-zfs-card", embedded: true }}></unraid-zfs-card>`
            : nothing}
          ${this._activeTab === "shares"
            ? html`<unraid-shares-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-shares-card", embedded: true }}></unraid-shares-card>`
            : nothing}
          ${this._activeTab === "remote-shares"
            ? html`<unraid-remote-shares-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-remote-shares-card", embedded: true }}></unraid-remote-shares-card>`
            : nothing}
          ${this._activeTab === "unassigned"
            ? html`<unraid-unassigned-devices-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-unassigned-devices-card", embedded: true }}></unraid-unassigned-devices-card>`
            : nothing}
          ${this._activeTab === "network"
            ? html`<unraid-network-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-network-card", embedded: true }}></unraid-network-card>`
            : nothing}
          ${this._activeTab === "docker"
            ? html`<unraid-docker-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-docker-card", embedded: true }}></unraid-docker-card>`
            : nothing}
          ${this._activeTab === "vms"
            ? html`<unraid-vm-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-vm-card", embedded: true }}></unraid-vm-card>`
            : nothing}
          ${this._activeTab === "fans"
            ? html`<unraid-fans-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-fans-card", embedded: true }}></unraid-fans-card>`
            : nothing}
          ${this._activeTab === "gpu"
            ? html`<unraid-gpu-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-gpu-card", embedded: true }}></unraid-gpu-card>`
            : nothing}
          ${this._activeTab === "ups"
            ? html`<unraid-ups-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-ups-card", embedded: true }}></unraid-ups-card>`
            : nothing}
          ${this._activeTab === "maintenance"
            ? html`<unraid-maintenance-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-maintenance-card", embedded: true }}></unraid-maintenance-card>`
            : nothing}
          ${this._activeTab === "notifications"
            ? html`<unraid-notifications-card .hass=${this.hass} .config=${{ ...this.config, type: "custom:unraid-notifications-card", embedded: true }}></unraid-notifications-card>`
            : nothing}
        </div>
      </ha-card>
    `;
  }
}

registerDashboardCard({
  tag: DASHBOARD_CARD_TAG,
  editorTag: DASHBOARD_EDITOR_TAG,
  card: UnraidDashboardCard,
  editor: UnraidDashboardCardEditor,
  name: "Unraid Unified Dashboard Card",
  description: "All-in-one Unraid master card with tabbed overview, storage, ZFS, docker, UPS, and VM monitoring.",
});
