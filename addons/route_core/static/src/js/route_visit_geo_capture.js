/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, xml } from "@odoo/owl";

class RouteGeoCaptureCheckinAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.visitId = this.props.action.params.visit_id;
        this.viewId = this.props.action.params.view_id || false;
        this.actionId = this.props.action.params.action_id || false;
        this.returnActionName = this.props.action.params.return_action_name || _t("Today's Visits");
        onMounted(() => this.captureCurrentLocation());
    }

    async captureCurrentLocation() {
        if (!this.visitId) {
            this.notification.add(_t("Missing visit reference for geo check-in."), {
                title: _t("Geo Check-in"),
                type: "danger",
            });
            await this.returnToVisit();
            return;
        }

        if (!window.isSecureContext) {
            this.notification.add(
                _t("Location capture requires HTTPS. Please open Odoo through the secure https:// address."),
                { title: _t("Geo Check-in"), type: "danger" }
            );
            await this.returnToVisit();
            return;
        }

        if (!navigator.geolocation) {
            this.notification.add(_t("This browser does not support GPS location capture."), {
                title: _t("Geo Check-in"),
                type: "danger",
            });
            await this.returnToVisit();
            return;
        }

        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout: 20000,
                    maximumAge: 0,
                });
            });

            const coords = position.coords || {};
            const result = await this.orm.call("route.visit", "action_save_browser_geo_checkin", [
                [this.visitId],
                coords.latitude,
                coords.longitude,
                coords.accuracy || 0,
            ]);

            const distanceLabel = result && result.distance_display ? result.distance_display : false;
            const message = distanceLabel
                ? _t("Current location captured. Distance from outlet:") + " " + distanceLabel
                : _t("Current location captured.");
            this.notification.add(message, { title: _t("Geo Check-in"), type: "success" });
        } catch (error) {
            let message = _t("Could not capture current location.");
            if (error && error.code === 1) {
                message = _t("Location permission was denied. Please allow location access in the browser and try again.");
            } else if (error && error.code === 2) {
                message = _t("Current location is unavailable. Please check GPS/location services and try again.");
            } else if (error && error.code === 3) {
                message = _t("Location capture timed out. Please try again in an open area or with stronger GPS signal.");
            } else if (error && error.message) {
                message = error.message;
            }
            this.notification.add(message, { title: _t("Geo Check-in"), type: "warning" });
        }

        await this.returnToVisit();
    }

    async returnToVisit() {
        const action = {
            type: "ir.actions.act_window",
            name: this.returnActionName,
            res_model: "route.visit",
            res_id: this.visitId,
            view_mode: "form",
            views: [[this.viewId || false, "form"]],
            target: "current",
            context: {
                search_default_filter_my_visits: 1,
                search_default_filter_today: 1,
                pda_mode: true,
                route_pda_salesperson_mode: true,
                create: false,
                edit: true,
                delete: false,
            },
        };
        if (this.actionId) {
            action.id = this.actionId;
        }
        await this.action.doAction(action);
    }
}

RouteGeoCaptureCheckinAction.template = xml`
    <div class="o_action route_geo_capture_action p-4">
        <div class="alert alert-info" role="alert">
            <strong>Geo Check-in</strong><br/>
            Capturing your current GPS location. Please allow location access when your browser asks.
        </div>
    </div>
`;

registry.category("actions").add("route_core_capture_geo_checkin", RouteGeoCaptureCheckinAction);


