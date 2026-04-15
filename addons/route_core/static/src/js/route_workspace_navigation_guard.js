/** @odoo-module **/

const STORAGE_KEYS = {
    workspaceHash: "route_core.v15.workspace.hash",
    workspaceUrl: "route_core.v15.workspace.url",
    productCenterHash: "route_core.v15.product_center.hash",
    productCenterUrl: "route_core.v15.product_center.url",
    pendingButtonName: "route_core.v15.pending.button_name",
    pendingButtonTs: "route_core.v15.pending.button_ts",
};

const INLINE_BACK_WRAPPER_ID = "route-workspace-inline-back-wrapper";
const INLINE_BACK_BUTTON_ID = "route-workspace-inline-back-btn";
const FLOATING_BACK_WRAPPER_ID = "route-workspace-floating-back-wrapper";
const FLOATING_BACK_BUTTON_ID = "route-workspace-floating-back-btn";
const PRODUCT_CENTER_BUTTON = "action_open_product_center_screen";
const STOCK_PAGE_KINDS = new Set(["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products"]);

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

function isSmallScreen() {
    return window.matchMedia("(max-width: 767.98px)").matches;
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

function findVisibleAnywhere(selector) {
    const matches = Array.from(document.querySelectorAll(selector)).filter(isElementVisible);
    return matches.length ? matches[matches.length - 1] : null;
}

function hasVisibleButton(name) {
    return !!findVisibleAnywhere(`button[name="${name}"]`);
}

function hasAnyVisibleButton(names) {
    return names.some((name) => hasVisibleButton(name));
}

function findAnyButton(name) {
    const matches = Array.from(document.querySelectorAll(`button[name="${name}"]`));
    return matches.length ? matches[matches.length - 1] : null;
}

function getRootText() {
    const root = getActiveRoot();
    return normalizeText(root ? root.innerText : "");
}

function getPageText() {
    return normalizeText(document.body ? document.body.innerText : "");
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
        const element = findVisibleInRoot(root, selector) || findVisibleAnywhere(selector);
        if (element) {
            return element.textContent.trim();
        }
    }
    return "";
}

function isRouteWorkspacePage() {
    const pageText = getPageText();
    return (
        hasVisibleButton("action_open_product_center_screen")
        && hasVisibleButton("action_open_visit_collections_center_screen")
        && pageText.includes("route workspace")
    );
}

function isProductCenterPage() {
    return hasAnyVisibleButton([
        "action_open_vehicle_products",
        "action_open_main_warehouse_products",
        "action_open_products",
    ]);
}

function isSnapshotCenterPage() {
    return hasAnyVisibleButton([
        "action_open_today_overview_screen",
        "action_open_collections_snapshot_screen",
    ]);
}

function isCollectionsCenterPage() {
    return hasAnyVisibleButton([
        "action_open_collections_snapshot_from_collections_center",
        "action_open_visit_collections",
    ]);
}

function isDailySummaryPage() {
    return hasVisibleButton("action_back_from_collections_snapshot")
        && hasVisibleButton("action_open_current_visit_statement_of_account");
}

function detectPageKind() {
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const pageText = getPageText();

    if (isRouteWorkspacePage()) {
        return "workspace";
    }
    if (isProductCenterPage()) {
        return "product_center";
    }
    if (isSnapshotCenterPage()) {
        return "snapshot_center";
    }
    if (isCollectionsCenterPage()) {
        return "collections_center";
    }
    if (isDailySummaryPage()) {
        return "daily_summary";
    }

    if (
        title.includes("vehicle products stock")
        || rootText.includes("vehicle products stock")
        || pageText.includes("vehicle products stock")
    ) {
        return "vehicle_stock";
    }

    if (
        title.includes("main warehouse products stock")
        || rootText.includes("main warehouse products stock")
        || pageText.includes("main warehouse products stock")
    ) {
        return "warehouse_stock";
    }

    if (
        title.includes("consignment outlets stock")
        || title.includes("outlet stock balances")
        || rootText.includes("consignment outlets stock")
        || rootText.includes("outlet stock balances")
        || pageText.includes("consignment outlets stock")
        || pageText.includes("outlet stock balances")
    ) {
        return "outlet_stock";
    }

    if (
        (title === "products" || title === "all products" || rootText.includes("all products") || pageText.includes("all products"))
        && (rootText.includes("barcode") || rootText.includes("price") || pageText.includes("barcode") || pageText.includes("price"))
    ) {
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

function rememberVisibleActionButtons() {
    // Compatibility hook kept intentionally. Some deployed bundles may still
    // call this helper during refreshNavigationUi.
}

function rememberNavigationTargets() {
    const pageKind = detectPageKind();
    if (pageKind === "workspace") {
        rememberPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
    }
    if (pageKind === "product_center") {
        rememberPair(STORAGE_KEYS.productCenterHash, STORAGE_KEYS.productCenterUrl);
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

function getProductCenterTarget() {
    return {
        hash: sessionStorage.getItem(STORAGE_KEYS.productCenterHash) || "",
        url: sessionStorage.getItem(STORAGE_KEYS.productCenterUrl) || "",
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
    if (timestamp && Date.now() - timestamp > 12000) {
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
    if (!button || !isElementVisible(button)) {
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

function navigateToWorkspaceTarget(target) {
    const targetUrl = target?.url || "";
    const targetHash = target?.hash || "";

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
    navigateToWorkspaceTarget(workspaceTarget);
}

function navigateBackToProductCenter() {
    navigateViaWorkspace(PRODUCT_CENTER_BUTTON);
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
    }, 150);
}

function hasBackArrowIcon(element) {
    if (!element) {
        return false;
    }
    return !!element.querySelector(".fa-arrow-left, .fa-chevron-left, .oi-arrow-left, .oi-chevron-left");
}

function looksLikeMobileHeaderBackControl(element) {
    const clickable = element?.closest?.("a, button");
    if (!clickable || clickable.id === FLOATING_BACK_BUTTON_ID || !isElementVisible(clickable)) {
        return false;
    }

    const rect = clickable.getBoundingClientRect();
    if (rect.top > 120 || rect.left > 220) {
        return false;
    }

    const text = normalizeText(clickable.textContent);
    const aria = normalizeText(clickable.getAttribute("aria-label") || clickable.getAttribute("title") || "");
    const classes = normalizeText(clickable.className || "");
    const parentClasses = normalizeText(clickable.parentElement?.className || "");

    return (
        hasBackArrowIcon(clickable)
        || text === "back"
        || aria.includes("back")
        || classes.includes("back")
        || parentClasses.includes("back")
    );
}

function removeInlineBackButton() {
    const wrapper = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (wrapper) {
        wrapper.remove();
    }
}

function removeFloatingBackButton() {
    const wrapper = document.getElementById(FLOATING_BACK_WRAPPER_ID);
    if (wrapper) {
        wrapper.remove();
    }
}

function getDesktopBackHost() {
    const root = getActiveRoot();
    return findVisibleInRoot(root, ".o_view_controller") || root || null;
}

function buildInlineBackButton() {
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
    button.innerHTML = '<i class="fa fa-arrow-left"></i><span>Back to Products and Stock</span>';

    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        navigateBackToProductCenter();
    });

    wrapper.appendChild(button);
    return wrapper;
}

function buildFloatingBackButton() {
    const wrapper = document.createElement("div");
    wrapper.id = FLOATING_BACK_WRAPPER_ID;
    wrapper.style.position = "fixed";
    wrapper.style.left = "12px";
    wrapper.style.top = "110px";
    wrapper.style.zIndex = "9999";
    wrapper.style.pointerEvents = "auto";

    const button = document.createElement("button");
    button.id = FLOATING_BACK_BUTTON_ID;
    button.type = "button";
    button.className = "btn btn-light";
    button.style.border = "1px solid rgba(0,0,0,0.12)";
    button.style.borderRadius = "999px";
    button.style.background = "#ffffff";
    button.style.padding = "8px 14px";
    button.style.fontWeight = "600";
    button.style.fontSize = "14px";
    button.style.boxShadow = "0 2px 10px rgba(0,0,0,0.08)";
    button.style.display = "inline-flex";
    button.style.alignItems = "center";
    button.style.gap = "6px";
    button.style.color = "inherit";
    button.style.cursor = "pointer";
    button.title = "Back to Products and Stock";
    button.innerHTML = '<i class="fa fa-arrow-left"></i><span>Back to Products and Stock</span>';

    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        navigateBackToProductCenter();
    });

    wrapper.appendChild(button);
    return wrapper;
}

function ensureBackButton() {
    const pageKind = detectPageKind();
    if (!STOCK_PAGE_KINDS.has(pageKind)) {
        removeInlineBackButton();
        removeFloatingBackButton();
        return;
    }

    if (isSmallScreen()) {
        removeInlineBackButton();
        if (!document.getElementById(FLOATING_BACK_BUTTON_ID)) {
            document.body.appendChild(buildFloatingBackButton());
        }
        return;
    }

    removeFloatingBackButton();
    const host = getDesktopBackHost();
    if (!host) {
        return;
    }
    let wrapper = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (!wrapper) {
        wrapper = buildInlineBackButton();
        host.prepend(wrapper);
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
    if (!STOCK_PAGE_KINDS.has(pageKind)) {
        return;
    }
    window.setTimeout(() => {
        navigateBackToProductCenter();
    }, 0);
}

function interceptMobileHeaderBack(event) {
    if (isInternalRedirect || !isSmallScreen()) {
        return;
    }
    const pageKind = detectPageKind();
    if (!STOCK_PAGE_KINDS.has(pageKind)) {
        return;
    }
    if (!looksLikeMobileHeaderBackControl(event.target)) {
        return;
    }

    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
        event.stopImmediatePropagation();
    }
    navigateViaWorkspace(PRODUCT_CENTER_BUTTON);
}

function refreshNavigationUi() {
    rememberVisibleActionButtons();
    rememberNavigationTargets();
    maybeRunPendingButton();
    ensureBackButton();
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

    document.addEventListener("click", interceptMobileHeaderBack, true);
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

