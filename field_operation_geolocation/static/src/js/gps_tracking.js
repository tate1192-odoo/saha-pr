/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { Component, useState, onWillStart, onWillUnmount, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// Single source of truth for the polling cadence (minutes). The server also
// returns an interval from /field_team/get_my_team; where it is available we
// use it, and everywhere else we fall back on this constant so the value is
// never hard-coded twice.
const DEFAULT_INTERVAL_MINUTES = 5;

// -------------------------------------------------------------------------
// 1. KISIM: GPS SERVİSİ (Motor)
// -------------------------------------------------------------------------
const FIELD_TEAM_GPS_SERVICE = {
    dependencies: ["notification"],

    start(env, { notification }) {
        let gpsInterval = null;
        let currentTeamId = null;
        // Session-scoped fallback for the device token when localStorage is
        // unavailable (private mode, blocked storage, ...).
        let fallbackDeviceToken = null;

        const isGeolocationSupported = () => 'geolocation' in navigator;

        // Stable, low-entropy device identifier. Previously the whole
        // navigator.userAgent (a strong fingerprinting vector) was shipped to
        // the server on every ping. We now generate a short random token once
        // and persist it in localStorage; if storage is not usable we keep a
        // token for the current session only.
        const getDeviceId = () => {
            const storageKey = 'field_operation_geolocation.device_id';
            try {
                let token = browser.localStorage.getItem(storageKey);
                if (!token) {
                    token = 'dev-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
                    browser.localStorage.setItem(storageKey, token);
                }
                return token;
            } catch (error) {
                if (!fallbackDeviceToken) {
                    fallbackDeviceToken = 'dev-' + Math.random().toString(36).slice(2, 10);
                }
                return fallbackDeviceToken;
            }
        };

        const getCurrentPosition = () => {
            return new Promise((resolve, reject) => {
                if (!isGeolocationSupported()) {
                    reject(new Error(_t("This browser does not support location services.")));
                    return;
                }
                const options = {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                };
                navigator.geolocation.getCurrentPosition(resolve, reject, options);
            });
        };

        const getBatteryLevel = async () => {
            if ('getBattery' in navigator) {
                try {
                    const battery = await navigator.getBattery();
                    return Math.round(battery.level * 100);
                } catch (e) { return null; }
            }
            return null;
        };

        const getSignalStrength = () => {
            if ('connection' in navigator) {
                const connection = navigator.connection;
                if (connection) return connection.effectiveType === '4g' ? '4' : '3';
            }
            return '3';
        };

        const sendPosition = async (teamId, position, additionalData = {}) => {
            try {
                const payload = {
                    team_id: teamId,
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    device_id: getDeviceId(),
                    battery_level: await getBatteryLevel(),
                    // Valid default from the team model selection
                    // (idle / moving / working / break).
                    status: 'working',
                    signal_strength: getSignalStrength(),
                    ...additionalData
                };

                const result = await rpc("/field_team/update_gps", payload);
                if (result && result.error) {
                    console.error('GPS update error:', result.error);
                }
                return result;
            } catch (error) {
                console.error('Failed to send GPS data:', error);
                // Normalise the shape so callers can always inspect `.error`.
                return { error: error.message || String(error) };
            }
        };

        const startGPSWatcher = async (teamId, intervalMinutes = DEFAULT_INTERVAL_MINUTES) => {
            if (!isGeolocationSupported()) {
                notification.add(_t("This browser does not support location services."), { type: "danger" });
                return false;
            }

            if (gpsInterval) clearInterval(gpsInterval);
            currentTeamId = teamId;

            let result;
            try {
                const position = await getCurrentPosition();
                // 'working' is the closest valid status to "tracking started":
                // the worker is on duty. The model only accepts
                // idle / moving / working / break.
                result = await sendPosition(teamId, position, { status: 'working' });
            } catch (error) {
                console.error('GPS start error:', error);
                notification.add(
                    _t("GPS tracking could not be started: %s", error.message || error),
                    { type: "danger" }
                );
                return false;
            }

            // The server (and the RPC layer) report failures as an `error`
            // payload: only claim success when the write actually went through.
            if (result && result.error) {
                notification.add(
                    _t("GPS tracking could not be started: %s", result.error),
                    { type: "danger" }
                );
                return false;
            }

            notification.add(_t("GPS tracking started"), { type: 'success' });

            const intervalMs = intervalMinutes * 60 * 1000;
            gpsInterval = browser.setInterval(async () => {
                try {
                    const position = await getCurrentPosition();
                    await sendPosition(teamId, position);
                } catch (error) {
                    console.error('Periodic GPS error:', error);
                }
            }, intervalMs);

            return true;
        };

        const stopGPSWatcher = () => {
            if (gpsInterval) {
                browser.clearInterval(gpsInterval);
                gpsInterval = null;
                currentTeamId = null;
                notification.add(_t("GPS tracking stopped"), { type: 'info' });
            }
        };

        const autoStartTracking = async () => {
            try {
                const teamInfo = await rpc("/field_team/get_my_team", {});
                if (teamInfo.team_id) {
                    return await startGPSWatcher(
                        teamInfo.team_id,
                        teamInfo.interval || DEFAULT_INTERVAL_MINUTES
                    );
                }
            } catch (error) {
                // Stay silent: the user may simply not belong to any team.
            }
            return false;
        };

        return {
            startGPSWatcher,
            stopGPSWatcher,
            autoStartTracking,
            getTrackingStatus: () => ({ isTracking: gpsInterval !== null })
        };
    },
};

registry.category("services").add("fieldTeamGPS", FIELD_TEAM_GPS_SERVICE);

// -------------------------------------------------------------------------
// 2. KISIM: SYSTRAY (Sağ Üst İkon)
// -------------------------------------------------------------------------
class GPSSystrayItem extends Component {
    setup() {
        this.gpsService = useService("fieldTeamGPS");
        this.state = useState({ isTracking: false, color: 'gray' });
        this.title = _t("Field Tracking");

        onWillStart(async () => {
            const started = await this.gpsService.autoStartTracking();
            this.updateState(started);
        });

        // Tear the watcher down when the systray (and the whole SPA under it)
        // is unmounted: without this the interval and the geolocation watcher
        // keep running after the page is left.
        onWillUnmount(() => {
            this.gpsService.stopGPSWatcher();
        });
    }

    updateState(isTracking) {
        this.state.isTracking = isTracking;
        this.state.color = isTracking ? '#28a745' : 'gray';
    }

    async onClick() {
        if (this.state.isTracking) {
            this.gpsService.stopGPSWatcher();
            this.updateState(false);
        } else {
            const started = await this.gpsService.autoStartTracking();
            this.updateState(started);
        }
    }
}

GPSSystrayItem.template = xml`
    <div class="o_nav_entry" t-on-click="onClick" style="cursor: pointer; display: flex; align-items: center; padding: 0 10px;">
        <i class="fa fa-location-arrow fa-lg" t-attf-style="color: #{state.color};" t-att-title="title"></i>
    </div>
`;

registry.category("systray").add("field_operation_geolocation.gps_item", { Component: GPSSystrayItem });

// -------------------------------------------------------------------------
// 3. KISIM: CLIENT ACTIONS (Python Butonlarının Aradığı Yer)
// -------------------------------------------------------------------------

// "Start GPS Tracking" butonuna basınca burası çalışır
registry.category("actions").add("start_gps_tracking", async (env, action) => {
    const gpsService = env.services.fieldTeamGPS;
    const teamId = action.params.team_id;

    if (teamId) {
        await gpsService.startGPSWatcher(teamId);
    } else {
        env.services.notification.add(_t("Team ID not found"), { type: "danger" });
    }

    return { type: "ir.actions.act_window_close" };
});

// "Stop GPS Tracking" butonuna basınca burası çalışır
registry.category("actions").add("stop_gps_tracking", async (env, action) => {
    const gpsService = env.services.fieldTeamGPS;
    gpsService.stopGPSWatcher();
    return { type: "ir.actions.act_window_close" };
});
