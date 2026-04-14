{
    "name": "Route Core",
    "version": "19.0.1.0.43",
    "summary": "Sales representative route visits",
    "author": "Yasser Fayed",
    "license": "LGPL-3",
    "depends": ["base", "sale", "mail", "stock", "contacts"],
    "data": [
        "security/route_security_groups.xml",
        "security/ir.model.access.csv",
        "security/route_record_rules.xml",
        "security/route_vehicle_closing_pending_visit_security.xml",
        "security/route_plan_skip_visit_security.xml",
        "security/route_plan_pending_visit_review_security.xml",
        "data/route_visit_sequence.xml",
        "data/route_outlet_sequence.xml",
        "data/route_vehicle_sequence.xml",
        "data/route_plan_sequence.xml",
        "data/route_refill_backorder_sequence.xml",
        "data/route_shortage_sequence.xml",
        "data/route_loading_proposal_sequence.xml",
        "data/route_vehicle_closing_sequence.xml",
        "data/route_salesperson_shortage_sequence.xml",
        "data/route_salesperson_deduction_sequence.xml",
        "data/route_direct_return_sequence.xml",
        "views/route_city_views.xml",
        "views/route_area_views.xml",
        "views/route_outlet_views.xml",
        "views/route_plan_views.xml",
        "views/route_vehicle_views.xml",
        "views/route_return_settings_views.xml",
        "views/route_visit_views.xml",
        "views/route_visit_payment_views.xml",
        "views/route_visit_workflow_ux_views.xml",
        "views/route_visit_payment_ux_views.xml",
        "views/outlet_stock_balance_views.xml",
        "views/route_location_link_views.xml",
        "views/route_product_barcode_views.xml",
        "views/route_shortage_views.xml",
        "views/route_loading_proposal_views.xml",
        "views/route_vehicle_stock_snapshot_views.xml",
        "views/route_vehicle_closing_views.xml",
        "views/route_salesperson_deduction_views.xml",
        "reports/route_salesperson_shortage_report.xml",
        "reports/route_visit_settlement_receipt_report.xml",
        "reports/route_visit_statement_report.xml",
        "views/route_salesperson_shortage_views.xml",
        "views/route_visit_document_links_views.xml",
        "views/route_direct_return_views.xml",
        "views/route_supervisor_assignment_views.xml",
        "views/route_pda_home_views.xml",
        "views/sale_order_direct_sale_views.xml",
        "views/route_role_actions_menus.xml",
        "views/route_role_ui_security_views.xml",
        "wizard/route_visit_end_wizard_views.xml",
        "wizard/route_plan_add_area_outlets_wizard_views.xml",
        "wizard/route_plan_skip_visit_wizard_views.xml",
        "wizard/route_visit_scan_wizard_views.xml",
        "wizard/route_visit_return_scan_wizard_views.xml",
        "wizard/route_visit_collect_payment_wizard_views.xml",
        "wizard/route_visit_statement_wizard_views.xml",
        "wizard/route_visit_finish_summary_wizard_views.xml",
        "wizard/route_visit_missing_lot_wizard_views.xml",
        "wizard/route_loading_source_wizard_views.xml",
        "wizard/route_vehicle_closing_scan_wizard_views.xml",
        "wizard/route_vehicle_closing_pending_visit_wizard_views.xml",
        "wizard/route_plan_pending_visit_review_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "route_core/static/src/js/route_visit_scan_focus.js",
            "route_core/static/src/js/route_workspace_navigation_guard.js",
            "route_core/static/src/css/route_pda_home.css",
        ],
    },
    "installable": True,
    "application": True,
}
"vehicle_stock";
        }
        if (title.startsWith("main warehouse products stock") || rootText.includes("main warehouse products stock")) {
            return "warehouse_stock";
        }
        if (
            title.startsWith("consignment outlets stock")
            || title.startsWith("outlet stock balances")
            || rootText.includes("consignment outlets stock")
            || rootText.includes("outlet stock balances")
        ) {
            return "outlet_stock";
        }
        if (
            (title === "products" || title === "all products" || rootText.includes("all products"))
            && (rootText.includes("barcode") || rootText.includes("price"))
        ) {
            return "all_products";
        }
    }
    return "";
}

function getCurrentHash() {
    return window.location.hash || "";
}

function getCurrentUrl() {
    return window.location.href || "";
}

function rememberPair(hashKey, urlKey) {
    const hash = getCurrentHash();
    const url = getCurrentUrl();
    if (hash) {
        sessionStorage.setItem(hashKey, hash);
    }
    if (url) {
        sessionStorage.setItem(urlKey, url);
    }
}

function rememberNavigationTargets() {
    if (detectPageKind() === "workspace") {
        rememberPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
    }
}

function rememberOriginFromClick(event) {
    const button = event.target.closest("button[name]");
    if (!button) {
        return;
    }
    const name = button.getAttribute("name") || "";
    if ([
        "action_open_product_center_screen",
        "action_open_snapshot_center_screen",
        "action_open_visit_collections_center_screen",
    ].includes(name)) {
        rememberPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
    }
}

function getWorkspaceTarget() {
    return {
        hash: sessionStorage.getItem(STORAGE_KEYS.workspaceHash) || "",
        url: sessionStorage.getItem(STORAGE_KEYS.workspaceUrl) || "",
    };
}

function setPendingButton(buttonName) {
    if (!buttonName) {
        return;
    }
    sessionStorage.setItem(STORAGE_KEYS.pendingButtonName, buttonName);
    sessionStorage.setItem(STORAGE_KEYS.pendingButtonTs, String(Date.now()));
}

function clearPendingButton() {
    sessionStorage.removeItem(STORAGE_KEYS.pendingButtonName);
    sessionStorage.removeItem(STORAGE_KEYS.pendingButtonTs);
}

function getPendingButton() {
    const buttonName = sessionStorage.getItem(STORAGE_KEYS.pendingButtonName) || "";
    const timestamp = parseInt(sessionStorage.getItem(STORAGE_KEYS.pendingButtonTs) || "0", 10);
    if (!buttonName) {
        return "";
    }
    if (timestamp && Date.now() - timestamp > 10000) {
        clearPendingButton();
        return "";
    }
    return buttonName;
}

function dispatchClick(element) {
    if (!element) {
        return false;
    }
    element.dispatchEvent(new MouseEvent("click", {
        bubbles: true,
        cancelable: true,
        view: window,
    }));
    return true;
}

function openServerButton(buttonName) {
    if (!buttonName) {
        return false;
    }
    const button = findAnyButton(buttonName);
    if (!button) {
        return false;
    }
    isInternalRedirect = true;
    dispatchClick(button);
    window.setTimeout(() => {
        isInternalRedirect = false;
    }, 900);
    return true;
}

function openWorkspaceMenuFallback() {
    const candidates = Array.from(document.querySelectorAll("a, button"));
    const link = candidates.find((element) => isElementVisible(element) && normalizeText(element.textContent) === "route workspace");
    if (!link) {
        return false;
    }
    isInternalRedirect = true;
    dispatchClick(link);
    window.setTimeout(() => {
        isInternalRedirect = false;
    }, 900);
    return true;
}

function navigateToTarget(target) {
    const targetHash = target?.hash || "";
    const targetUrl = target?.url || "";

    if (targetUrl && window.location.href !== targetUrl) {
        isInternalRedirect = true;
        window.location.assign(targetUrl);
        window.setTimeout(() => {
            isInternalRedirect = false;
        }, 1000);
        return true;
    }

    if (targetHash) {
        const cleanHash = targetHash.startsWith("#") ? targetHash : `#${targetHash}`;
        if (window.location.hash !== cleanHash) {
            isInternalRedirect = true;
            window.location.hash = cleanHash.slice(1);
            window.setTimeout(() => {
                isInternalRedirect = false;
            }, 700);
            return true;
        }
    }
    return false;
}

function navigateViaWorkspace(buttonName) {
    if (openServerButton(buttonName)) {
        return;
    }
    setPendingButton(buttonName);
    if (openWorkspaceMenuFallback()) {
        return;
    }
    const workspaceTarget = getWorkspaceTarget();
    navigateToTarget(workspaceTarget);
}

function maybeRunPendingButton() {
    const pendingButton = getPendingButton();
    if (!pendingButton) {
        return;
    }
    if (detectPageKind() !== "workspace") {
        return;
    }
    clearPendingButton();
    window.setTimeout(() => {
        openServerButton(pendingButton);
    }, 80);
}

function getBackLabel(pageKind) {
    if (PAGE_KINDS_WITH_INLINE_BACK.has(pageKind)) {
        return "Back to Products and Stock";
    }
    return "Back";
}

function handleInlineBack(pageKind) {
    if (["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products"].includes(pageKind)) {
        navigateViaWorkspace("action_open_product_center_screen");
    }
}

function removeInlineBackButton() {
    const wrapper = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (wrapper) {
        wrapper.remove();
    }
}

function findInlineBackHost() {
    const root = getActiveRoot();
    return findVisibleInRoot(root, ".o_view_controller") || root || null;
}

function buildInlineBackButton(pageKind) {
    const wrapper = document.createElement("div");
    wrapper.id = INLINE_BACK_WRAPPER_ID;
    wrapper.style.display = "block";
    wrapper.style.margin = "12px 16px 8px 16px";

    const button = document.createElement("button");
    button.id = INLINE_BACK_BUTTON_ID;
    button.type = "button";
    button.className = "btn btn-link";
    button.style.padding = "0";
    button.style.border = "0";
    button.style.background = "transparent";
    button.style.fontWeight = "600";
    button.style.fontSize = "16px";
    button.style.textDecoration = "none";
    button.style.boxShadow = "none";
    button.style.display = "inline-flex";
    button.style.alignItems = "center";
    button.style.gap = "6px";
    button.style.color = "inherit";
    button.dataset.pageKind = pageKind;
    button.title = getBackLabel(pageKind);
    button.innerHTML = `<i class="fa fa-arrow-left"></i><span>${getBackLabel(pageKind)}</span>`;

    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        handleInlineBack(button.dataset.pageKind || "");
    });

    wrapper.appendChild(button);
    return wrapper;
}

function ensureInlineBackButton() {
    const pageKind = detectPageKind();
    const host = findInlineBackHost();

    if (!PAGE_KINDS_WITH_INLINE_BACK.has(pageKind) || !host) {
        removeInlineBackButton();
        return;
    }

    let wrapper = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (!wrapper) {
        wrapper = buildInlineBackButton(pageKind);
        host.prepend(wrapper);
    }

    const button = document.getElementById(INLINE_BACK_BUTTON_ID);
    if (!button) {
        return;
    }

    button.dataset.pageKind = pageKind;
    button.title = getBackLabel(pageKind);

    const labelSpan = button.querySelector("span");
    if (labelSpan) {
        labelSpan.textContent = getBackLabel(pageKind);
    }

    if (wrapper.parentElement !== host) {
        wrapper.remove();
        host.prepend(wrapper);
    }
}

function handleBrowserBack() {
    if (isInternalRedirect) {
        return;
    }
    const pageKind = detectPageKind();
    if (!PAGE_KINDS_WITH_INLINE_BACK.has(pageKind)) {
        return;
    }
    window.setTimeout(() => {
        handleInlineBack(pageKind);
    }, 0);
}

function refreshNavigationUi() {
    rememberNavigationTargets();
    maybeRunPendingButton();
    ensureInlineBackButton();
}

function bootRouteWorkspaceNavigationGuard() {
    if (observerStarted || !document.body) {
        return;
    }

    observerStarted = true;

    let refreshTimer = null;
    const scheduleRefresh = () => {
        window.clearTimeout(refreshTimer);
        refreshTimer = window.setTimeout(refreshNavigationUi, 80);
    };

    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["class", "style"],
    });

    document.addEventListener("click", rememberOriginFromClick, true);
    document.addEventListener("click", scheduleRefresh, true);
    window.addEventListener("hashchange", scheduleRefresh);
    window.addEventListener("popstate", handleBrowserBack);

    refreshNavigationUi();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootRouteWorkspaceNavigationGuard);
} else {
    bootRouteWorkspaceNavigationGuard();
}
