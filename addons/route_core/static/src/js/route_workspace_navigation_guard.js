/** @odoo-module **/

const STORAGE_KEYS = {
    workspace: "route_core.workspace.hash",
    productCenter: "route_core.product_center.hash",
    snapshotCenter: "route_core.snapshot_center.hash",
    collectionsCenter: "route_core.collections_center.hash",
};

const INLINE_BACK_WRAPPER_ID = "route-workspace-inline-back-wrapper";
const INLINE_BACK_BUTTON_ID = "route-workspace-inline-back-btn";

let isInternalRedirect = false;
let observerStarted = false;

function normalizeText(value) {
    return (value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function getVisibleText(selector) {
    const el = document.querySelector(selector);
    return el ? el.textContent.trim() : "";
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
    return !!document.querySelector(".route_pda_home_title")
        && normalizeText(getVisibleText(".route_pda_home_title")) === "route workspace";
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

function removeInlineBackButton() {
    const existing = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (existing) {
        existing.remove();
    }
}

function findInlineBackHost() {
    return document.querySelector(".o_content .o_view_controller")
        || document.querySelector(".o_content")
        || null;
}

function buildInlineBackButton(pageKind, targetHash) {
    const wrapper = document.createElement("div");
    wrapper.id = INLINE_BACK_WRAPPER_ID;
    wrapper.style.display = "block";
    wrapper.style.margin = "12px 16px 8px 16px";

    const button = document.createElement("button");
    button.id = INLINE_BACK_BUTTON_ID;
    button.type = "button";
    button.className = "btn btn-link";
    button.dataset.targetHash = targetHash;
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
    button.title = getBackLabel(pageKind);
    button.innerHTML = `<i class="fa fa-arrow-left"></i><span>${getBackLabel(pageKind)}</span>`;

    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        navigateToHash(button.dataset.targetHash || "");
    });

    wrapper.appendChild(button);
    return wrapper;
}

function ensureInlineBackButton() {
    const pageKind = detectPageKind();
    const targetHash = getBackTargetForPage(pageKind);
    const supportedPages = new Set([
        "vehicle_stock",
        "warehouse_stock",
        "outlet_stock",
        "all_products",
        "daily_summary",
    ]);

    const host = findInlineBackHost();

    if (!supportedPages.has(pageKind) || !targetHash || !host) {
        removeInlineBackButton();
        return;
    }

    const existing = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (existing) {
        const button = existing.querySelector(`#${INLINE_BACK_BUTTON_ID}`);
        if (button) {
            button.dataset.targetHash = targetHash;
            button.title = getBackLabel(pageKind);
            const span = button.querySelector("span");
            if (span) {
                span.textContent = getBackLabel(pageKind);
            }
        }

        if (existing.parentElement !== host) {
            existing.remove();
            host.prepend(existing);
        }
        return;
    }

    const wrapper = buildInlineBackButton(pageKind, targetHash);
    host.prepend(wrapper);
}

function handleBrowserBack() {
    if (isInternalRedirect) {
        return;
    }

    const pageKind = detectPageKind();
    const protectedPages = new Set([
        "vehicle_stock",
        "warehouse_stock",
        "outlet_stock",
        "all_products",
        "daily_summary",
    ]);

    if (!protectedPages.has(pageKind)) {
        return;
    }

    const targetHash = getBackTargetForPage(pageKind);
    if (!targetHash) {
        return;
    }

    window.setTimeout(() => {
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
        refreshTimer = window.setTimeout(refreshNavigationUi, 80);
    };

    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });

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
