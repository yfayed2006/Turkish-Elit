/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, xml } from "@odoo/owl";

class RouteOutletProspectGeoCaptureAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.prospectId = this.props.action.params.prospect_id;
        this.viewId = this.props.action.params.view_id || false;
        onMounted(() => this.captureCurrentLocation());
    }

    async captureCurrentLocation() {
        if (!this.prospectId) {
            this.notification.add(_t("Missing potential customer reference for GPS capture."), {
                title: _t("Potential Customer Location"),
                type: "danger",
            });
            await this.returnToProspect();
            return;
        }

        if (!window.isSecureContext) {
            this.notification.add(
                _t("Location capture requires HTTPS. Please open Odoo through the secure https:// address."),
                { title: _t("Potential Customer Location"), type: "danger" }
            );
            await this.returnToProspect();
            return;
        }

        if (!navigator.geolocation) {
            this.notification.add(_t("This browser does not support GPS location capture."), {
                title: _t("Potential Customer Location"),
                type: "danger",
            });
            await this.returnToProspect();
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
            await this.orm.call("route.outlet.prospect", "action_save_browser_location", [
                this.prospectId,
                coords.latitude,
                coords.longitude,
                coords.accuracy || 0,
            ]);
            this.notification.add(_t("Current GPS location captured for the potential customer."), {
                title: _t("Potential Customer Location"),
                type: "success",
            });
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
            this.notification.add(message, { title: _t("Potential Customer Location"), type: "warning" });
        }

        await this.returnToProspect();
    }

    async returnToProspect() {
        const action = {
            type: "ir.actions.act_window",
            name: _t("Potential Customer"),
            res_model: "route.outlet.prospect",
            res_id: this.prospectId,
            view_mode: "form",
            views: [[this.viewId || false, "form"]],
            target: "current",
            context: {
                create: true,
                edit: true,
                delete: false,
            },
        };
        await this.action.doAction(action);
    }
}

RouteOutletProspectGeoCaptureAction.template = xml`
    <div class="o_action route_geo_capture_action p-4">
        <div class="alert alert-info" role="alert">
            <strong>Potential Customer Location</strong><br/>
            Capturing your current GPS location. Please allow location access when your browser asks.
        </div>
    </div>
`;

registry.category("actions").add("route_core_capture_outlet_prospect_location", RouteOutletProspectGeoCaptureAction);
