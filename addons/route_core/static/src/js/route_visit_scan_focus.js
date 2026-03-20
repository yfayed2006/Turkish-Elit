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

        const selectors = [];
        if (focusTarget === "lot") {
            selectors.push(
                '.o_field_widget[name="lot_barcode"] input',
                '[name="lot_barcode"] input',
                'input[name="lot_barcode"]'
            );
        } else if (focusTarget === "product") {
            selectors.push(
                '.o_field_widget[name="barcode"] input',
                '[name="barcode"] input',
                'input[name="barcode"]'
            );
        } else {
            return;
        }

        const tryFocus = (attempt = 0) => {
            let input = null;
            for (const selector of selectors) {
                input = this.el?.querySelector(selector);
                if (input) {
                    break;
                }
            }

            if (input) {
                try {
                    document.activeElement?.blur?.();
                } catch (_) {}

                input.focus();
                input.select?.();
                return;
            }

            if (attempt < 10) {
                setTimeout(() => tryFocus(attempt + 1), 100);
            }
        };

        setTimeout(() => tryFocus(), 50);
    },
});
