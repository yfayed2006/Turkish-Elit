/** @odoo-module **/

/*
 * Route Core - Split Payment mobile line cleanup.
 *
 * The split payment one2many remains an editable Odoo list. On mobile, CSS renders every
 * row as a card, but Odoo list views do not consistently remove per-row invisible cells
 * for selection-dependent fields. This small helper reads the payment mode of every row
 * and hides fields that do not belong to that mode.
 */

const FIELD_SETS = {
    cash: new Set(["payment_mode", "amount", "payment_date"]),
    bank: new Set(["payment_mode", "amount", "payment_date", "reference", "bank_name"]),
    pos: new Set(["payment_mode", "amount", "payment_date", "reference", "pos_terminal"]),
    cheque: new Set([
        "payment_mode",
        "amount",
        "payment_date",
        "bank_name",
        "cheque_number",
        "cheque_date",
        "cheque_holder_name",
        "cheque_note",
    ]),
};

const CONTROL_FIELDS = new Set(["currency_id"]);
const HIDDEN_CLASS = "route_split_payment_runtime_hidden";
const ROW_MODE_PREFIX = "route_split_payment_mode_";
const MODE_CLASSES = Object.keys(FIELD_SETS).map((mode) => `${ROW_MODE_PREFIX}${mode}`);

function isMobileSplitPaymentLayout() {
    return window.matchMedia && window.matchMedia("(max-width: 768px)").matches;
}

function normalizeMode(value) {
    const text = String(value || "").trim().toLowerCase();
    if (!text) {
        return "cash";
    }
    if (text === "cash" || text.includes("cash")) {
        return "cash";
    }
    if (text === "bank" || text.includes("bank")) {
        return "bank";
    }
    if (text === "pos" || text.includes("pos")) {
        return "pos";
    }
    if (text === "cheque" || text === "check" || text.includes("cheque") || text.includes("check")) {
        return "cheque";
    }
    return FIELD_SETS[text] ? text : "cash";
}

function getPaymentModeFromRow(row) {
    const cell = row.querySelector('td[name="payment_mode"]');
    if (!cell) {
        return "cash";
    }

    const select = cell.querySelector("select");
    if (select) {
        return normalizeMode(select.value || select.options?.[select.selectedIndex]?.textContent);
    }

    const input = cell.querySelector("input");
    if (input && input.value) {
        return normalizeMode(input.value);
    }

    const fieldValue = cell.querySelector(".o_field_widget");
    return normalizeMode((fieldValue || cell).textContent || "");
}

function cellName(cell) {
    return cell.getAttribute("name") || "";
}

function clearRuntimeVisibility(row) {
    row.classList.remove(...MODE_CLASSES);
    row.querySelectorAll(`td.${HIDDEN_CLASS}`).forEach((cell) => {
        cell.classList.remove(HIDDEN_CLASS);
        cell.style.removeProperty("display");
    });
}

function applyRowVisibility(row) {
    clearRuntimeVisibility(row);

    if (!isMobileSplitPaymentLayout()) {
        return;
    }

    const mode = getPaymentModeFromRow(row);
    const allowedFields = FIELD_SETS[mode] || FIELD_SETS.cash;
    row.classList.add(`${ROW_MODE_PREFIX}${mode}`);

    Array.from(row.children).forEach((cell) => {
        if (!cell.matches || !cell.matches("td[name]")) {
            return;
        }
        const name = cellName(cell);
        if (!name || CONTROL_FIELDS.has(name)) {
            cell.classList.add(HIDDEN_CLASS);
            return;
        }
        if (!allowedFields.has(name)) {
            cell.classList.add(HIDDEN_CLASS);
        }
    });
}

function applyAllSplitPaymentRows() {
    document
        .querySelectorAll(".route_pda_split_payment_lines table.o_list_table tbody tr.o_data_row")
        .forEach(applyRowVisibility);
}

let scheduled = false;
function scheduleApply() {
    if (scheduled) {
        return;
    }
    scheduled = true;
    window.requestAnimationFrame(() => {
        scheduled = false;
        applyAllSplitPaymentRows();
    });
}

function startObserver() {
    scheduleApply();

    document.addEventListener(
        "change",
        (ev) => {
            if (ev.target && ev.target.closest && ev.target.closest(".route_pda_split_payment_lines")) {
                scheduleApply();
            }
        },
        true
    );

    document.addEventListener(
        "input",
        (ev) => {
            if (ev.target && ev.target.closest && ev.target.closest(".route_pda_split_payment_lines")) {
                scheduleApply();
            }
        },
        true
    );

    window.addEventListener("resize", scheduleApply);

    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            const target = mutation.target;
            if (target && target.closest && target.closest(".route_pda_split_payment_lines")) {
                scheduleApply();
                return;
            }
            for (const node of mutation.addedNodes || []) {
                if (node.nodeType === Node.ELEMENT_NODE && node.querySelector && node.querySelector(".route_pda_split_payment_lines")) {
                    scheduleApply();
                    return;
                }
            }
        }
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "style", "value"],
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver, { once: true });
} else {
    startObserver();
}
