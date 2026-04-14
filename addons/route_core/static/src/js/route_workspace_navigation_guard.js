/** @odoo-module **/

const STORAGE_KEYS = {
    workspaceHash: "route_core.workspace.hash",
    workspaceUrl: "route_core.workspace.url",
    productCenterHash: "route_core.product_center.hash",
    productCenterUrl: "route_core.product_center.url",
    snapshotCenterHash: "route_core.snapshot_center.hash",
    snapshotCenterUrl: "route_core.snapshot_center.url",
    collectionsCenterHash: "route_core.collections_center.hash",
    collectionsCenterUrl: "route_core.collections_center.url",
};

const INLINE_BACK_WRAPPER_ID = "route-workspace-inline-back-wrapper";
const INLINE_BACK_BUTTON_ID = "route-workspace-inline-back-btn";

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
        ".o_content .breadcrumb-item.active",
        ".o_content .o_last_breadcrumb_item",
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
    const bodyText = getBodyText();
    return bodyText.includes("products and stock")
        && bodyText.includes("vehicle products stock")
        && bodyText.includes("main warehouse products stock");
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
    if (title.startsWith("vehicle products stock") || bodyText.includes("vehicle products stock")) {
        return "vehicle_stock";
    }
    if (title.startsWith("main warehouse products stock") || bodyText.includes("main warehouse products stock")) {
        return "warehouse_stock";
    }
    if (title.startsWith("outlet stock balances") || bodyText.includes("outlet stock balances")) {
        return "outlet_stock";
    }
    if ((title === "products" || bodyText.includes("\nproducts\n")) && bodyText.includes("price:")) {
        return "all_products";
    }
    return "";
}

function getCurrentHash() {
    return window.location.hash || "";
}

function getCurrentUrl() {
    return window.location.href || "";
}

function rememberKeyPair(hashKey, urlKey) {
    const currentHash = getCurrentHash();
    const currentUrl = getCurrentUrl();

    if (currentHash) {
        sessionStorage.setItem(hashKey, currentHash);
    }
    if (currentUrl) {
        sessionStorage.setItem(urlKey, currentUrl);
    }
}

function rememberNavigationTargets() {
    switch (detectPageKind()) {
        case "workspace":
            rememberKeyPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
            break;
        case "product_center":
            rememberKeyPair(STORAGE_KEYS.productCenterHash, STORAGE_KEYS.productCenterUrl);
            break;
        case "snapshot_center":
            rememberKeyPair(STORAGE_KEYS.snapshotCenterHash, STORAGE_KEYS.snapshotCenterUrl);
            break;
        case "collections_center":
            rememberKeyPair(STORAGE_KEYS.collectionsCenterHash, STORAGE_KEYS.collectionsCenterUrl);
            break;
    }
}

function getStoredTarget(hashKey, urlKey) {
    return {
        hash: sessionStorage.getItem(hashKey) || "",
        url: sessionStorage.getItem(urlKey) || "",
    };
}

function getBackTargetForPage(pageKind) {
    const workspace = getStoredTarget(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
    const productCenter = getStoredTarget(STORAGE_KEYS.productCenterHash, STORAGE_KEYS.productCenterUrl);
    const snapshotCenter = getStoredTarget(STORAGE_KEYS.snapshotCenterHash, STORAGE_KEYS.snapshotCenterUrl);
    const collectionsCenter = getStoredTarget(STORAGE_KEYS.collectionsCenterHash, STORAGE_KEYS.collectionsCenterUrl);

    switch (pageKind) {
        case "vehicle_stock":
        case "warehouse_stock":
        case "outlet_stock":
        case "all_products":
            return {
                hash: productCenter.hash || workspace.hash,
                url: productCenter.url || workspace.url,
            };
        case "daily_summary":
            return {
                hash: collectionsCenter.hash || snapshotCenter.hash || workspace.hash,
                url: collectionsCenter.url || snapshotCenter.url || workspace.url,
            };
        case "product_center":
        case "collections_center":
            return {
                hash: workspace.hash,
                url: workspace.url,
            };
        default:
            return {
                hash: "",
                url: "",
            };
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

function navigateToTarget(targetHash, targetUrl) {
    const cleanHash = targetHash
        ? (targetHash.startsWith("#") ? targetHash : `#${targetHash}`)
        : "";

    if (cleanHash && window.location.hash !== cleanHash) {
        isInternalRedirect = true;
        window.location.hash = cleanHash.slice(1);
        window.setTimeout(() => {
            isInternalRedirect = false;
        }, 250);
        return;
    }

    if (targetUrl && window.location.href !== targetUrl) {
        isInternalRedirect = true;
        window.location.assign(targetUrl);
        window.setTimeout(() => {
            isInternalRedirect = false;
        }, 500);
    }
}

function removeInlineBackButton() {
    const wrapper = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (wrapper) {
        wrapper.remove();
    }
}

function findInlineBackHost() {
    return document.querySelector(".o_content .o_view_controller")
        || document.querySelector(".o_content")
        || document.querySelector(".o_action_manager")
        || null;
}

function buildInlineBackButton(pageKind, target) {
    const wrapper = document.createElement("div");
    wrapper.id = INLINE_BACK_WRAPPER_ID;
    wrapper.style.display = "block";
    wrapper.style.margin = "12px 16px 8px 16px";

    const button = document.createElement("button");
    button.id = INLINE_BACK_BUTTON_ID;
    button.type = "button";
    button.className = "btn btn-link";
    button.dataset.targetHash = target.hash || "";
    button.dataset.targetUrl = target.url || "";
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
        navigateToTarget(button.dataset.targetHash || "", button.dataset.targetUrl || "");
    });

    wrapper.appendChild(button);
    return wrapper;
}

function ensureInlineBackButton() {
    const pageKind = detectPageKind();
    const target = getBackTargetForPage(pageKind);
    const supportedPages = new Set([
        "vehicle_stock",
        "warehouse_stock",
        "outlet_stock",
        "all_products",
        "daily_summary",
    ]);
    const host = findInlineBackHost();

    if (!supportedPages.has(pageKind) || !host || (!target.hash && !target.url)) {
        removeInlineBackButton();
        return;
    }

    let wrapper = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (!wrapper) {
        wrapper = buildInlineBackButton(pageKind, target);
        host.insertAdjacentElement("afterbegin", wrapper);
    }

    const button = document.getElementById(INLINE_BACK_BUTTON_ID);
    if (!button) {
        return;
    }

    button.dataset.targetHash = target.hash || "";
    button.dataset.targetUrl = target.url || "";
    button.title = getBackLabel(pageKind);

    const labelSpan = button.querySelector("span");
    if (labelSpan) {
        labelSpan.textContent = getBackLabel(pageKind);
    }

    if (wrapper.parentElement !== host || host.firstElementChild !== wrapper) {
        wrapper.remove();
        host.insertAdjacentElement("afterbegin", wrapper);
    }
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

    const target = getBackTargetForPage(pageKind);
    if (!target.hash && !target.url) {
        return;
    }

    window.setTimeout(() => {
        navigateToTarget(target.hash || "", target.url || "");
    }, 0);
}

function refreshNavigationUi() {
    rememberNavigationTargets();
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

