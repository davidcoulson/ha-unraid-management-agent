import { html, nothing, type TemplateResult } from "lit";
import {
  ZFS_CARD_TAG,
  ZFS_EDITOR_TAG,
} from "./config";
import { BaseUnraidCard } from "./dashboard-cards-base";
import { UnraidZfsCardEditor } from "./dashboard-cards-editor";
import {
  iconTemplate,
  mdiAlertCircle,
  mdiDatabase,
} from "./icons";
import { registerDashboardCard } from "./register-dashboard-card";

interface ZFSPoolItem {
  name: string;
  usagePct: number;
  totalSize?: string;
  usedSize?: string;
  freeSize?: string;
  health: string;
  errors?: number;
  corruptedFiles?: number;
  usageEntityId?: string;
  healthEntityId?: string;
}

export class UnraidZfsCard extends BaseUnraidCard {
  static override editorTag = ZFS_EDITOR_TAG;

  private getArcData() {
    const hitRatioState = this.getEntity("zfs_arc_hit_ratio");
    const configuredMaxState = this.getEntity("zfs_arc_configured_max");

    const hitRatio = hitRatioState?.state != null && !isNaN(Number(hitRatioState.state))
      ? Math.round(Number(hitRatioState.state))
      : undefined;

    let configuredMax: string | undefined;
    if (configuredMaxState?.state != null) {
      const val = configuredMaxState.state;
      if (val === "0" || val === "Auto") {
        configuredMax = "Auto";
      } else {
        const num = Number(val);
        if (!isNaN(num) && num > 0) {
          configuredMax = `${(num / (1024 * 1024 * 1024)).toFixed(1)} GB`;
        } else {
          configuredMax = `${val} ${configuredMaxState.attributes?.unit_of_measurement || ""}`.trim();
        }
      }
    }

    return {
      hitRatio,
      hitRatioEntityId: hitRatioState?.entity_id,
      configuredMax,
      configuredMaxEntityId: configuredMaxState?.entity_id,
      attributes: hitRatioState?.attributes,
    };
  }

  private getPools(): ZFSPoolItem[] {
    const usageEntities = this.getEntities("zfs_pool_usage");
    const healthEntities = this.getEntities("zfs_pool_health");
    const corruptedEntities = this.getEntities("corrupted_files");

    const poolMap = new Map<string, ZFSPoolItem>();
    const device = this.getActiveDevice();
    const deviceId = device?.id;

    // Also search all states for zfs pools if not registered with translation_key
    if (this.hass?.states) {
      for (const [entityId, stateObj] of Object.entries(this.hass.states)) {
        if (deviceId && this.hass.entities) {
          const ent = this.hass.entities[entityId];
          if (ent && ent.device_id && ent.device_id !== deviceId) continue;
        }

        const match = entityId.match(/_zfs_([a-zA-Z0-9_-]+)_usage$/i);
        if (match && match[1]) {
          const poolName = match[1];
          if (!poolMap.has(poolName)) {
            const usageNum = parseFloat(stateObj.state);
            poolMap.set(poolName, {
              name: (stateObj.attributes?.pool_name as string) || poolName,
              usagePct: !isNaN(usageNum) ? Math.round(usageNum) : 0,
              totalSize: stateObj.attributes?.total_size as string,
              usedSize: stateObj.attributes?.used_size as string,
              freeSize: stateObj.attributes?.free_space as string || stateObj.attributes?.free_size as string,
              health: "ONLINE",
              usageEntityId: entityId,
            });
          }
        }
      }
    }

    for (const u of usageEntities) {
      const poolName = (u.attributes?.pool_name as string) || u.entity_id.replace(/^.*?_zfs_/, "").replace(/_usage$/, "");
      const usageNum = parseFloat(u.state);
      if (!poolMap.has(poolName)) {
        poolMap.set(poolName, {
          name: poolName,
          usagePct: !isNaN(usageNum) ? Math.round(usageNum) : 0,
          totalSize: u.attributes?.total_size as string,
          usedSize: u.attributes?.used_size as string,
          freeSize: u.attributes?.free_space as string || u.attributes?.free_size as string,
          health: "ONLINE",
          usageEntityId: u.entity_id,
        });
      }
    }

    // Attach health
    for (const h of healthEntities) {
      const poolName = (h.attributes?.pool_name as string) || h.entity_id.replace(/^.*?_zfs_/, "").replace(/_health$/, "");
      const item = poolMap.get(poolName);
      if (item) {
        item.health = h.state || "ONLINE";
        item.healthEntityId = h.entity_id;
        if (h.attributes?.errors !== undefined) {
          item.errors = Number(h.attributes.errors);
        }
      }
    }

    // Attach corrupted files
    for (const c of corruptedEntities) {
      const poolName = c.entity_id.replace(/^.*?_zfs_/, "").replace(/_corrupted_files$/, "");
      const item = poolMap.get(poolName);
      if (item) {
        const val = parseInt(c.state, 10);
        if (!isNaN(val)) {
          item.corruptedFiles = val;
        }
      }
    }

    return Array.from(poolMap.values()).sort((a, b) => a.name.localeCompare(b.name));
  }

  protected override render(): TemplateResult {
    const device = this.getActiveDevice();
    const serverName = this.config.title || device?.name_by_user || device?.name || "Unraid Server";

    const arc = this.getArcData();
    const pools = this.getPools();

    const hasData = arc.hitRatio !== undefined || pools.length > 0;

    return html`
      <ha-card>
        ${this.renderHeader(
          serverName,
          "ZFS Storage & Cache",
          mdiDatabase,
          html`
            <span class="badge ${pools.some((p) => p.health !== "ONLINE") ? "badge-warning" : "badge-online"}">
              <span class="pulse-dot"></span>
              <span>${pools.length} Pool${pools.length === 1 ? "" : "s"}</span>
            </span>
          `
        )}

        ${!hasData
          ? html`
              <div class="empty-state">
                ${iconTemplate(mdiDatabase, 32)}
                <div class="empty-title">No ZFS Telemetry Available</div>
                <div class="empty-subtext">Enable the ZFS collector in Unraid Management Agent to monitor pools and ARC cache.</div>
              </div>
            `
          : html`
              ${arc.hitRatio !== undefined
                ? html`
                    <div class="rings-grid">
                      <div
                        class="ring-card"
                        role="${arc.hitRatioEntityId ? "button" : "none"}"
                        tabindex="${arc.hitRatioEntityId ? "0" : "-1"}"
                        style="${arc.hitRatioEntityId ? "cursor: pointer;" : ""}"
                        @click=${() => arc.hitRatioEntityId && this.openMoreInfo(arc.hitRatioEntityId)}
                        @keydown=${(e: KeyboardEvent) => (e.key === "Enter" || e.key === " ") && arc.hitRatioEntityId && (e.preventDefault(), this.openMoreInfo(arc.hitRatioEntityId))}
                        title="Click to view ARC Cache details"
                      >
                        <div
                          class="ring-gauge"
                          style="--pct: ${arc.hitRatio}; --ring-color: ${arc.hitRatio > 90 ? "var(--unraid-online)" : arc.hitRatio > 70 ? "var(--unraid-warning)" : "var(--unraid-error)"}"
                        >
                          <span class="ring-content">${arc.hitRatio}%</span>
                        </div>
                        <span class="ring-label">ARC Hit Ratio</span>
                        <span class="ring-subtext">
                          ${arc.configuredMax ? `Max: ${arc.configuredMax}` : "ZFS Adaptive Cache"}
                        </span>
                      </div>
                    </div>
                  `
                : nothing}

              ${pools.length > 0
                ? html`
                    <div class="divider"></div>
                    <div class="disk-list">
                      ${pools.map((p) => {
                        const isDegraded = p.health.toUpperCase() !== "ONLINE";
                        const hasCorrupted = (p.corruptedFiles || 0) > 0;
                        return html`
                          <div
                            class="disk-row"
                            @click=${() => p.usageEntityId && this.openMoreInfo(p.usageEntityId)}
                            style="${p.usageEntityId ? "cursor: pointer;" : ""}"
                          >
                            <div class="disk-main">
                              <span class="disk-icon ${isDegraded ? "disk-warning" : "disk-online"}">
                                ${iconTemplate(isDegraded ? mdiAlertCircle : mdiDatabase, 18)}
                              </span>
                              <div class="disk-info">
                                <span class="disk-name">${p.name}</span>
                                <span class="disk-subtext">
                                  ${p.usedSize && p.totalSize ? `${p.usedSize} / ${p.totalSize}` : `${p.usagePct}% used`}
                                  ${hasCorrupted ? ` • ${p.corruptedFiles} corrupted` : ""}
                                </span>
                              </div>
                            </div>
                            <div class="disk-meta">
                              <span class="disk-temp">${p.usagePct}%</span>
                              <span class="badge ${isDegraded ? "badge-error" : "badge-online"}">
                                ${p.health}
                              </span>
                            </div>
                          </div>
                        `;
                      })}
                    </div>
                  `
                : nothing}
            `}
      </ha-card>
    `;
  }
}

registerDashboardCard({
  tag: ZFS_CARD_TAG,
  editorTag: ZFS_EDITOR_TAG,
  card: UnraidZfsCard,
  editor: UnraidZfsCardEditor,
  name: "Unraid ZFS Card",
  description: "Monitor ZFS pools, pool health, corrupted files, and ARC cache performance",
});
