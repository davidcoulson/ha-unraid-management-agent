import { html, nothing, type TemplateResult } from "lit";
import {
  GPU_CARD_TAG,
  GPU_EDITOR_TAG,
} from "./config";
import { BaseUnraidCard } from "./dashboard-cards-base";
import { UnraidGpuCardEditor } from "./dashboard-cards-editor";
import {
  iconTemplate,
  mdiExpansionCard,
} from "./icons";
import { registerDashboardCard } from "./register-dashboard-card";

interface GPUItem {
  index: number;
  name: string;
  driver?: string;
  utilizationPct?: number;
  utilizationEntityId?: string;
  temp?: number;
  tempEntityId?: string;
  power?: number;
  powerEntityId?: string;
  energy?: number;
  energyEntityId?: string;
  memUtilPct?: number;
  memUtilEntityId?: string;
}

export class UnraidGpuCard extends BaseUnraidCard {
  static override editorTag = GPU_EDITOR_TAG;

  private getGpus(): GPUItem[] {
    const gpuMap = new Map<string, GPUItem>();
    if (!this.hass?.states) return [];

    const device = this.getActiveDevice();
    const deviceId = device?.id;
    const cleanName = device?.name
      ? this.slugifyDeviceName(device.name)
      : undefined;

    for (const [entityId, stateObj] of Object.entries(this.hass.states)) {
      if (!entityId.startsWith("sensor.")) continue;

      const ent = this.hass.entities?.[entityId];
      if (deviceId && ent?.device_id) {
        if (ent.device_id !== deviceId) continue;
      } else if (cleanName && !entityId.includes(cleanName)) {
        continue;
      }

      const match = entityId.match(
        /_gpu_(?:(.+?)_)?(utilization|temperature|power|energy|memory_utilization|vram_usage)$/i
      );
      if (!match || !match[2]) continue;

      const rawKey = match[1] || "0";
      const gpuKey = rawKey.toLowerCase();
      const metric = match[2].toLowerCase();

      if (!gpuMap.has(gpuKey)) {
        const parsedIndex = parseInt(rawKey, 10);
        const index = !isNaN(parsedIndex) ? parsedIndex : gpuMap.size;
        const friendlyName =
          typeof stateObj.attributes?.friendly_name === "string"
            ? (stateObj.attributes.friendly_name as string)
                .replace(/^(?:.*?\s+)?(?:GPU\s+)?/i, "")
                .replace(
                  /\s+(?:Utilization|Temperature|Power|Energy|VRAM|Usage).*$/i,
                  "",
                )
            : undefined;

        const gpuName =
          (typeof stateObj.attributes?.gpu_name === "string"
            ? (stateObj.attributes.gpu_name as string)
            : undefined) ||
          friendlyName ||
          (rawKey !== "0"
            ? rawKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
            : `GPU ${index}`);
        const driver =
          (stateObj.attributes?.gpu_driver_version as string) ||
          (stateObj.attributes?.driver_version as string) ||
          undefined;

        gpuMap.set(gpuKey, {
          index,
          name: gpuName,
          driver,
        });
      }

      const item = gpuMap.get(gpuKey)!;

      // Update name and driver from any metric attribute that provides them
      if (stateObj.attributes?.gpu_name && (!item.name || item.name.startsWith("GPU "))) {
        item.name = stateObj.attributes.gpu_name as string;
      }
      if (
        (stateObj.attributes?.gpu_driver_version || stateObj.attributes?.driver_version) &&
        !item.driver
      ) {
        item.driver = (stateObj.attributes.gpu_driver_version || stateObj.attributes.driver_version) as string;
      }

      const numVal = parseFloat(stateObj.state);

      if (metric === "utilization") {
        item.utilizationPct = !isNaN(numVal) ? Math.round(numVal) : undefined;
        item.utilizationEntityId = entityId;
      } else if (metric === "temperature") {
        item.temp = !isNaN(numVal) ? Math.round(numVal) : undefined;
        item.tempEntityId = entityId;
      } else if (metric === "power") {
        item.power = !isNaN(numVal) ? Math.round(numVal) : undefined;
        item.powerEntityId = entityId;
      } else if (metric === "energy") {
        item.energy = !isNaN(numVal) ? Number(numVal.toFixed(2)) : undefined;
        item.energyEntityId = entityId;
      } else if (metric === "memory_utilization" || metric === "vram_usage") {
        item.memUtilPct = !isNaN(numVal) ? Math.round(numVal) : undefined;
        item.memUtilEntityId = entityId;
      }
    }

    return Array.from(gpuMap.values()).sort((a, b) => a.index - b.index);
  }

  protected override render(): TemplateResult {
    const device = this.getActiveDevice();
    const serverName = this.config.title || device?.name_by_user || device?.name || "Unraid Server";
    const gpus = this.getGpus();

    return html`
      <ha-card>
        ${this.renderHeader(
          serverName,
          "GPU Accelerators",
          mdiExpansionCard,
          html`
            <span class="badge ${gpus.length > 0 ? "badge-online" : ""}">
              <span class="pulse-dot"></span>
              <span>${gpus.length} GPU${gpus.length === 1 ? "" : "s"}</span>
            </span>
          `
        )}

        ${gpus.length === 0
          ? html`
              <div class="empty-state">
                ${iconTemplate(mdiExpansionCard, 32)}
                <div class="empty-title">No GPU Telemetry Available</div>
                <div class="empty-subtext">Enable GPU monitoring or install NVIDIA / Intel GPU plugins to view GPU stats.</div>
              </div>
            `
          : html`
              <div class="gpu-grid" style="display: flex; flex-direction: column; gap: 14px;">
                ${gpus.map((gpu) => {
                  const util = gpu.utilizationPct ?? 0;
                  return html`
                    <div class="ring-card" style="padding: 12px; background: rgba(255, 255, 255, 0.02); border-radius: 8px;">
                      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; width: 100%;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                          ${iconTemplate(mdiExpansionCard, 20)}
                          <span style="font-weight: 600; font-size: 14px;">${gpu.name}</span>
                        </div>
                        ${gpu.driver ? html`<span class="badge">${gpu.driver}</span>` : nothing}
                      </div>

                      <div class="rings-grid" style="grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));">
                        ${gpu.utilizationPct !== undefined
                          ? html`
                              <div
                                class="ring-card"
                                @click=${() => gpu.utilizationEntityId && this.openMoreInfo(gpu.utilizationEntityId)}
                                style="cursor: pointer;"
                                title="Click for GPU load details"
                              >
                                <div
                                  class="ring-gauge"
                                  style="--pct: ${util}; --ring-color: ${util > 80 ? "var(--unraid-error)" : util > 50 ? "var(--unraid-warning)" : "var(--unraid-online)"}"
                                >
                                  <span class="ring-content">${util}%</span>
                                </div>
                                <span class="ring-label">GPU Load</span>
                              </div>
                            `
                          : nothing}

                        ${gpu.temp !== undefined
                          ? html`
                              <div
                                class="ring-card"
                                @click=${() => gpu.tempEntityId && this.openMoreInfo(gpu.tempEntityId)}
                                style="cursor: pointer;"
                                title="Click for Temperature details"
                              >
                                <div
                                  class="ring-gauge"
                                  style="--pct: ${Math.min(100, Math.round((gpu.temp / 90) * 100))}; --ring-color: ${gpu.temp > 80 ? "var(--unraid-error)" : gpu.temp > 65 ? "var(--unraid-warning)" : "var(--unraid-info)"}"
                                >
                                  <span class="ring-content">${gpu.temp}°C</span>
                                </div>
                                <span class="ring-label">Temperature</span>
                              </div>
                            `
                          : nothing}

                        ${gpu.power !== undefined
                          ? html`
                              <div
                                class="ring-card"
                                @click=${() => gpu.powerEntityId && this.openMoreInfo(gpu.powerEntityId)}
                                style="cursor: pointer;"
                                title="Click for Power details"
                              >
                                <div class="ring-gauge" style="--pct: 60; --ring-color: var(--unraid-accent)">
                                  <span class="ring-content">${gpu.power}W</span>
                                </div>
                                <span class="ring-label">Power Draw</span>
                                ${gpu.energy !== undefined ? html`<span class="ring-subtext">${gpu.energy} kWh</span>` : nothing}
                              </div>
                            `
                          : nothing}

                        ${gpu.memUtilPct !== undefined
                          ? html`
                              <div
                                class="ring-card"
                                @click=${() => gpu.memUtilEntityId && this.openMoreInfo(gpu.memUtilEntityId)}
                                style="cursor: pointer;"
                                title="Click for VRAM details"
                              >
                                <div class="ring-gauge" style="--pct: ${gpu.memUtilPct}; --ring-color: var(--unraid-info)">
                                  <span class="ring-content">${gpu.memUtilPct}%</span>
                                </div>
                                <span class="ring-label">VRAM Usage</span>
                              </div>
                            `
                          : nothing}
                      </div>
                    </div>
                  `;
                })}
              </div>
            `}
      </ha-card>
    `;
  }
}

registerDashboardCard({
  tag: GPU_CARD_TAG,
  editorTag: GPU_EDITOR_TAG,
  card: UnraidGpuCard,
  editor: UnraidGpuCardEditor,
  name: "Unraid GPU Card",
  description: "Monitor graphics cards utilization, temperature, power draw, and VRAM",
});
