/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

patch(FormRenderer.prototype, {
    mounted() {
        super.mounted?.();
        this._routeVisitScanApplyFocus();
    },

    patched() {
        super.patched?.();
        this._routeVisitScanApplyFocus();
    },

    _routeVisitScanApplyFocus() {
        const record = this.props?.record;
        if (!record || record.resModel !== "route.visit.scan.wizard") {
            return;
        }

        const focusTarget = record.data?.focus_target;
        if (!focusTarget) {
            return;
        }

        let selector = null;
        if (focusTarget === "lot") {
            selector = 'div[name="lot_barcode"] input';
        } else if (focusTarget === "product") {
            selector = 'div[name="barcode"] input';
        }

        if (!selector) {
            return;
        }

        setTimeout(() => {
            const input = this.el?.querySelector(selector);
            if (input) {
                input.focus();
                input.select?.();
            }
        }, 50);
    },
});
