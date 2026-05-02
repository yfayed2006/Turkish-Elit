/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

function focusField(root, fieldName) {
    if (!root) {
        return false;
    }

    const selectors = [
        `.o_field_widget[name="${fieldName}"] input`,
        `[name="${fieldName}"] input`,
        `input[name="${fieldName}"]`,
        `.o_field_char[name="${fieldName}"] input`,
        `.o_input[name="${fieldName}"]`,
    ];

    for (const selector of selectors) {
        const el = root.querySelector(selector);
        if (el && !el.disabled && el.offsetParent !== null) {
            try {
                if (typeof el.scrollIntoView === "function") {
                    el.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
                }
                el.focus();
                if (typeof el.select === "function") {
                    el.select();
                }
                return true;
            } catch (_e) {
                // ignore
            }
        }
    }
    return false;
}

function focusWithRetry(root, fieldName, maxAttempts = 20, delay = 120) {
    let attempt = 0;

    const run = () => {
        if (focusField(root, fieldName)) {
            return;
        }
        attempt += 1;
        if (attempt < maxAttempts) {
            setTimeout(run, delay);
        }
    };

    setTimeout(run, 50);
}

patch(FormRenderer.prototype, {
    setup() {
        super.setup?.();
        this.__routeVisitScanLastFocusTarget = null;
        this.__routeVisitScanObserver = null;
    },

    mounted() {
        super.mounted?.();
        this._routeVisitScanInstallFocusFlow();
        this._routeVisitScanApplyImmediateFocus();
    },

    patched() {
        super.patched?.();
        this._routeVisitScanApplyImmediateFocus();
    },

    willUnmount() {
        if (this.__routeVisitScanObserver) {
            this.__routeVisitScanObserver.disconnect();
            this.__routeVisitScanObserver = null;
        }
        super.willUnmount?.();
    },

    _routeVisitScanIsTargetWizard() {
        const record = this.props?.record;
        return !!record && record.resModel === "route.visit.scan.wizard";
    },

    _routeVisitScanGetFocusTarget() {
        const record = this.props?.record;
        if (!record || record.resModel !== "route.visit.scan.wizard") {
            return null;
        }
        return record.data?.focus_target || null;
    },

    _routeVisitScanApplyImmediateFocus() {
        if (!this._routeVisitScanIsTargetWizard()) {
            return;
        }

        const focusTarget = this._routeVisitScanGetFocusTarget();
        if (!focusTarget) {
            return;
        }

        const fieldName = focusTarget === "product" ? "barcode" : "lot_barcode";

        if (this.__routeVisitScanLastFocusTarget !== focusTarget) {
            this.__routeVisitScanLastFocusTarget = focusTarget;
            focusWithRetry(this.el, fieldName, 25, 120);
        }
    },
      _routeVisitScanInstallFocusFlow() {
        if (!this._routeVisitScanIsTargetWizard() || this.__routeVisitScanObserver) {
            return;
        }

        const root = this.el;
        if (!root) {
            return;
        }

        const clickedButtonName = { value: null };

        root.addEventListener(
            "click",
            (ev) => {
                const button = ev.target.closest("button");
                if (!button) {
                    return;
                }

                const buttonName = button.getAttribute("name");
                if (buttonName === "action_set_active_lot") {
                    clickedButtonName.value = "set_lot";
                } else if (buttonName === "action_clear_active_lot") {
                    clickedButtonName.value = "clear_lot";
                }
            },
            true
        );

        this.__routeVisitScanObserver = new MutationObserver(() => {
            if (!this._routeVisitScanIsTargetWizard()) {
                return;
            }

            if (clickedButtonName.value === "set_lot") {
                focusWithRetry(this.el, "barcode", 25, 120);
                clickedButtonName.value = null;
                return;
            }

            if (clickedButtonName.value === "clear_lot") {
                focusWithRetry(this.el, "lot_barcode", 25, 120);
                clickedButtonName.value = null;
            }
        });

        this.__routeVisitScanObserver.observe(root, {
            childList: true,
            subtree: true,
        });
    },
});

