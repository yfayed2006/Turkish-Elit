/** @odoo-module **/

const STORAGE_KEYS = {
    workspaceHash: "route_core.v3.workspace.hash",
    workspaceUrl: "route_core.v3.workspace.url",
    productCenterHash: "route_core.v3.product_center.hash",
    productCenterUrl: "route_core.v3.product_center.url",
    snapshotCenterHash: "route_core.v3.snapshot_center.hash",
    snapshotCenterUrl: "route_core.v3.snapshot_center.url",
    collectionsCenterHash: "route_core.v3.collections_center.hash",
    collectionsCenterUrl: "route_core.v3.collections_center.url",
};

const INLINE_BACK_WRAPPER_ID = "route-workspace-inline-back-wrapper";
const INLINE_BACK_BUTTON_ID = "route-workspace-inline-back-btn";

let isInternalRedirect = false;
let observerStarted = false;

function normalizeText(value) {
    return (value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function isElementVisible(element) {
    if (!element || !(element instanceof Element)) {
        return false;
    }
    const style = window.getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
        return false;
    }
    if (element.closest(".o_invisible_modifier")) {
        return false;
    }
    return !!(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
}

function getVisibleRoots() {
    const selectors = [
        ".o_action_manager .o_action",
        ".o_action_manager .o_view_controller",
        ".o_web_client .o_content .o_action",
        ".o_web_client .o_content .o_view_controller",
        ".o_web_client .o_content",
    ];
    const roots = [];
    for (const selector of selectors) {
        for (const element of document.querySelectorAll(selector)) {
            if (isElementVisible(element) && !roots.includes(element)) {
                roots.push(element);
            }
        }
    }
    return roots.length ? roots : [document.body];
}

function getActiveRoot() {
    const roots = getVisibleRoots();
    return roots[roots.length - 1] || document.body;
}

function findVisibleInRoot(root, selector) {
    if (!root) {
        return null;
    }
    const matches = Array.from(root.querySelectorAll(selector)).filter(isElementVisible);
    return matches.length ? matches[matches.length - 1] : null;
}

function getVisibleText(selector) {
    const root = getActiveRoot();
    const element = findVisibleInRoot(root, selector) || (isElementVisible(root) && root.matches?.(selector) ? root : null);
    return element ? element.textContent.trim() : "";
}

function getRootText() {
    const root = getActiveRoot();
    return normalizeText(root ? root.innerText : "");
}

function findActionTitle() {
    const root = getActiveRoot();
    const selectors = [
        ".o_control_panel .breadcrumb-item.active",
        ".o_control_panel .o_last_breadcrumb_item",
        ".o_control_panel .o_breadcrumb .active",
        ".o_control_panel .o_control_panel_breadcrumbs .active",
        ".route_pda_detail_title",
        ".route_pda_home_title",
        ".o_form_view .oe_title h1",
        "h1",
        ".breadcrumb-item.active",
        ".o_last_breadcrumb_item",
    ];
    for (const selector of selectors) {
        const element = findVisibleInRoot(root, selector);
        if (element) {
            return element.textContent.trim();
        }
    }
    return "";
}

function hasVisibleSelector(selector) {
    const root = getActiveRoot();
    return !!findVisibleInRoot(root, selector);
}

function isRouteWorkspacePage() {
    return hasVisibleSelector(".route_pda_home_title")
        && normalizeText(getVisibleText(".route_pda_home_title")) === "route workspace";
}

function isProductCenterPage() {
    return hasVisibleSelector(".route_pda_center_grid")
        && getRootText().includes("vehicle products stock")
        && getRootText().includes("main warehouse products stock")
        && getRootText().includes("all products");
}

function detectPageKind() {
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const isRouteForm = hasVisibleSelector(".route_pda_home_sheet");

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
    if (!isRouteForm && title === "products" && rootText.includes("price:")) {
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
    switch (detectPageKind()) {
        case "workspace":
            rememberPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
            break;
        case "product_center":
            rememberPair(STORAGE_KEYS.productCenterHash, STORAGE_KEYS.productCenterUrl);
            break;
        case "snapshot_center":
            rememberPair(STORAGE_KEYS.snapshotCenterHash, STORAGE_KEYS.snapshotCenterUrl);
            break;
        case "collections_center":
            rememberPair(STORAGE_KEYS.collectionsCenterHash, STORAGE_KEYS.collectionsCenterUrl);
            break;
    }
}

function rememberCurrentAs(targetName) {
    switch (targetName) {
        case "workspace":
            rememberPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
            break;
        case "product_center":
            rememberPair(STORAGE_KEYS.productCenterHash, STORAGE_KEYS.productCenterUrl);
            break;
        case "snapshot_center":
            rememberPair(STORAGE_KEYS.snapshotCenterHash, STORAGE_KEYS.snapshotCenterUrl);
            break;
        case "collections_center":
            rememberPair(STORAGE_KEYS.collectionsCenterHash, STORAGE_KEYS.collectionsCenterUrl);
            break;
    }
}

function rememberOriginFromClick(event) {
    const button = event.target.closest("button[name]");
    if (!button || !isElementVisible(button)) {
        return;
    }
    const name = button.getAttribute("name") || "";

    if ([
        "action_open_vehicle_products",
        "action_open_main_warehouse_products",
        "action_open_products",
        "action_open_consignment_outlet_stock",
    ].includes(name)) {
        rememberCurrentAs("product_center");
        return;
    }

    if ([
        "action_open_collections_snapshot_screen",
    ].includes(name)) {
        rememberCurrentAs("snapshot_center");
        return;
    }

    if ([
        "action_open_collections_snapshot_from_collections_center",
    ].includes(name)) {
        rememberCurrentAs("collections_center");
        return;
    }

    if ([
        "action_open_product_center_screen",
        "action_open_snapshot_center_screen",
        "action_open_visit_collections_center_screen",
    ].includes(name)) {
        rememberCurrentAs("workspace");
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
        case "snapshot_center":
            return {
                hash: workspace.hash,
                url: workspace.url,
            };
        default:
            return { hash: "", url: "" };
    }
}

function getBackLabel(pageKind) {
    if (["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products"].includes(pageKind)) {
        return "Back to Products and Stock";
    }
    if (pageKind === "daily_summary") {
        return "Back";
    }
    if (["product_center", "snapshot_center", "collections_center"].includes(pageKind)) {
        return "Back to Route Workspace";
    }
    return "Back";
}

function navigateToTarget(target) {
    const targetHash = target?.hash || "";
    const targetUrl = target?.url || "";

    if (targetUrl && window.location.href !== targetUrl) {
        isInternalRedirect = true;
        window.location.assign(targetUrl);
        window.setTimeout(() => {
            isInternalRedirect = false;
        }, 700);
        return;
    }

    if (targetHash) {
        const cleanHash = targetHash.startsWith("#") ? targetHash : `#${targetHash}`;
        if (window.location.hash !== cleanHash) {
            isInternalRedirect = true;
            window.location.hash = cleanHash.slice(1);
            window.setTimeout(() => {
                isInternalRedirect = false;
            }, 350);
        }
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
        navigateToTarget({
            hash: button.dataset.targetHash || "",
            url: button.dataset.targetUrl || "",
        });
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
        host.prepend(wrapper);
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
        navigateToTarget(target);
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

