/** @odoo-module **/

const STORAGE_KEYS = {
    workspace: "route_core.workspace.hash",
    productCenter: "route_core.product_center.hash",
    snapshotCenter: "route_core.snapshot_center.hash",
    collectionsCenter: "route_core.collections_center.hash",
};

const BACK_BUTTON_ID = "route-workspace-inline-back-btn";
const BACK_BUTTON_WRAPPER_ID = "route-workspace-inline-back-wrapper";

let isInternalRedirect = false;
let observerStarted = false;

function normalizeText(value) {
    return (value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function getVisibleText(selector) {
    const element = document.querySelector(selector);
    return element ? element.textContent.trim() : "";
}

function getBodyText() {
    return normalizeText(document.body ? document.body.innerText : "");
}

function findActionTitle() {
    const selectors = [
        ".o_control_panel .breadcrumb-item.active",
        ".o_control_panel .o_last_breadcrumb_item",
        ".o_control_panel .o_breadcrumb .active",
        ".o_control_panel .o_control_panel_breadcrumbs .active",
        ".route_pda_detail_title",
        ".route_pda_home_title",
        ".o_form_view .oe_title h1",
        ".o_content h1",
    ];
    for (const selector of selectors) {
        const value = getVisibleText(selector);
        if (value) {
            return value;
        }
    }
    return "";
}

function isRouteWorkspacePage() {
    return !!document.querySelector(".route_pda_home_title") && normalizeText(getVisibleText(".route_pda_home_title")) === "route workspace";
}

function isProductCenterPage() {
    return !!document.querySelector(".route_pda_center_grid")
        && getBodyText().includes("vehicle products stock")
        && getBodyText().includes("main warehouse products stock");
}

function detectPageKind() {
    const title = normalizeText(findActionTitle());
    const bodyText = getBodyText();
    const isRouteForm = !!document.querySelector(".route_pda_home_sheet");

    if (isRouteWorkspacePage()) {
        return "workspace";
    }
    if (isProductCenterPage()) {
        return "product_center";
    }
    if (isRouteForm && (title === "stock and lot snapshot" || title === "snapshot center")) {
        return "snapshot_center";
    }
    if (isRouteForm && title === "visit collections") {
        return "collections_center";
    }
    if (isRouteForm && title === "daily summary") {
        return "daily_summary";
    }
    if (title.startsWith("vehicle products stock")) {
        return "vehicle_stock";
    }
    if (title.startsWith("main warehouse products stock")) {
        return "warehouse_stock";
    }
    if (title.startsWith("outlet stock balances")) {
        return "outlet_stock";
    }
    if (!isRouteForm && title === "products" && bodyText.includes("price:")) {
        return "all_products";
    }
    return "";
}

function getCurrentHash() {
    return window.location.hash || "";
}

function rememberNavigationHashes() {
    const hash = getCurrentHash();
    if (!hash) {
        return;
    }
    switch (detectPageKind()) {
        case "workspace":
            sessionStorage.setItem(STORAGE_KEYS.workspace, hash);
            break;
        case "product_center":
            sessionStorage.setItem(STORAGE_KEYS.productCenter, hash);
            break;
        case "snapshot_center":
            sessionStorage.setItem(STORAGE_KEYS.snapshotCenter, hash);
            break;
        case "collections_center":
            sessionStorage.setItem(STORAGE_KEYS.collectionsCenter, hash);
            break;
    }
}

function getBackTargetForPage(pageKind) {
    const workspaceHash = sessionStorage.getItem(STORAGE_KEYS.workspace) || "";
    const productCenterHash = sessionStorage.getItem(STORAGE_KEYS.productCenter) || workspaceHash;
    const snapshotCenterHash = sessionStorage.getItem(STORAGE_KEYS.snapshotCenter) || workspaceHash;
    const collectionsCenterHash = sessionStorage.getItem(STORAGE_KEYS.collectionsCenter) || snapshotCenterHash || workspaceHash;

    switch (pageKind) {
        case "vehicle_stock":
        case "warehouse_stock":
        case "outlet_stock":
        case "all_products":
            return productCenterHash || workspaceHash;
        case "daily_summary":
            return collectionsCenterHash || snapshotCenterHash || workspaceHash;
        case "product_center":
        case "collections_center":
            return workspaceHash;
        default:
            return "";
    }
}

function getBackLabel(pageKind) {
    if (["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products"].includes(pageKind)) {
        return "Back to Products and Stock";
    }
    if (pageKind === "daily_summary") {
        return "Back";
    }
    return "Back to Route Workspace";
}

function findControlPanelHost() {
    return document.querySelector(".o_control_panel .o_cp_top_left")
        || document.querySelector(".o_control_panel .o_cp_top")
        || document.querySelector(".o_control_panel")
        || null;
}

function navigateToHash(targetHash) {
    if (!targetHash) {
        return;
    }
    const cleanHash = targetHash.startsWith("#") ? targetHash : `#${targetHash}`;
    if (window.location.hash === cleanHash) {
        return;
    }
    isInternalRedirect = true;
    window.location.hash = cleanHash.slice(1);
    window.setTimeout(() => {
        isInternalRedirect = false;
    }, 250);
}

function removeBackButton() {
    const wrapper = document.getElementById(BACK_BUTTON_WRAPPER_ID);
    if (wrapper) {
        wrapper.remove();
    }
}

function ensureInlineBackButton() {
    const pageKind = detectPageKind();
    const targetHash = getBackTargetForPage(pageKind);
    const supportedPages = new Set(["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products"]);
    const host = findControlPanelHost();

    if (!supportedPages.has(pageKind) || !targetHash || !host) {
        removeBackButton();
        return;
    }

    let wrapper = document.getElementById(BACK_BUTTON_WRAPPER_ID);
    if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.id = BACK_BUTTON_WRAPPER_ID;
        wrapper.className = "route_workspace_inline_back_wrapper";

        const button = document.createElement("button");
        button.id = BACK_BUTTON_ID;
        button.type = "button";
        button.className = "btn btn-secondary route_workspace_inline_back_btn";
        button.innerHTML = '<i class="fa fa-arrow-left"></i><span>Back</span>' ;
        button.addEventListener("click", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            navigateToHash(button.dataset.targetHash || "");
        });

        wrapper.appendChild(button);
        host.prepend(wrapper);
    }

    const button = document.getElementById(BACK_BUTTON_ID);
    if (!button) {
        return;
    }
    button.dataset.targetHash = targetHash;
    button.title = getBackLabel(pageKind);
    const labelSpan = button.querySelector("span");
    if (labelSpan) {
        labelSpan.textContent = getBackLabel(pageKind);
    }

    if (wrapper.parentElement !== host) {
        host.prepend(wrapper);
    }
}

function handleBrowserBack() {
    if (isInternalRedirect) {
        return;
    }
    const pageKind = detectPageKind();
    const protectedPages = new Set(["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products", "daily_summary"]);
    if (!protectedPages.has(pageKind)) {
        return;
    }
    const targetHash = getBackTargetForPage(pageKind);
    if (!targetHash) {
        return;
    }
    window.setTimeout(() => {
        // If the browser back navigation would keep the user inside the wrong cached SPA state,
        // force a clean return to the logical parent screen that we memorized earlier.
        navigateToHash(targetHash);
    }, 0);
}

function refreshNavigationUi() {
    rememberNavigationHashes();
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
        refreshTimer = window.setTimeout(refreshNavigationUi, 60);
    };

    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.body, { childList: true, subtree: true });

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
