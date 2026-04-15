/** @odoo-module **/

const INLINE_BACK_WRAPPER_ID = "route-workspace-inline-back-wrapper";
const INLINE_BACK_BUTTON_ID = "route-workspace-inline-back-btn";
const FLOATING_BACK_WRAPPER_ID = "route-workspace-floating-back-wrapper";
const FLOATING_BACK_BUTTON_ID = "route-workspace-floating-back-btn";
const PRODUCT_CENTER_ROUTE = "/route_core/pda/product_center";
const STOCK_PAGE_KINDS = new Set(["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products"]);

let observerStarted = false;
let isInternalRedirect = false;

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
    return hasVisibleButton("action_open_product_center_screen") && pageText.includes("route workspace");
}

function isProductCenterPage() {
    return hasAnyVisibleButton([
        "action_open_vehicle_products",
        "action_open_main_warehouse_products",
        "action_open_products",
    ]);
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

    if (title.includes("vehicle products stock") || rootText.includes("vehicle products stock") || pageText.includes("vehicle products stock")) {
        return "vehicle_stock";
    }
    if (title.includes("main warehouse products stock") || rootText.includes("main warehouse products stock") || pageText.includes("main warehouse products stock")) {
        return "warehouse_stock";
    }
    if (title.includes("consignment outlets stock") || title.includes("outlet stock balances") || rootText.includes("consignment outlets stock") || rootText.includes("outlet stock balances") || pageText.includes("consignment outlets stock") || pageText.includes("outlet stock balances")) {
        return "outlet_stock";
    }
    if ((title === "products" || title === "all products" || rootText.includes("all products") || pageText.includes("all products"))
        && (rootText.includes("barcode") || rootText.includes("price") || pageText.includes("barcode") || pageText.includes("price"))) {
        return "all_products";
    }
    return "";
}

function hasBackArrowIcon(element) {
    return !!element?.querySelector?.(".fa-arrow-left, .fa-chevron-left, .oi-arrow-left, .oi-chevron-left");
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
    return hasBackArrowIcon(clickable) || text === "back" || aria.includes("back") || classes.includes("back") || parentClasses.includes("back");
}

function goToProductCenter() {
    if (isInternalRedirect) {
        return;
    }
    isInternalRedirect = true;
    window.location.assign(PRODUCT_CENTER_ROUTE);
}

function removeInlineBackButton() {
    document.getElementById(INLINE_BACK_WRAPPER_ID)?.remove();
}

function removeFloatingBackButton() {
    document.getElementById(FLOATING_BACK_WRAPPER_ID)?.remove();
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
    button.innerHTML = '<i class="fa fa-arrow-left"></i><span>Products and Stock</span>';
    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        goToProductCenter();
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
    button.title = "Products and Stock";
    button.innerHTML = '<i class="fa fa-arrow-left"></i><span>Products and Stock</span>';
    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        goToProductCenter();
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

function interceptMobileHeaderBack(event) {
    if (!isSmallScreen() || isInternalRedirect) {
        return;
    }
    if (!STOCK_PAGE_KINDS.has(detectPageKind())) {
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
    goToProductCenter();
}

function refreshNavigationUi() {
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
    document.addEventListener("click", scheduleRefresh, true);
    window.addEventListener("hashchange", scheduleRefresh);

    refreshNavigationUi();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootRouteWorkspaceNavigationGuard);
} else {
    bootRouteWorkspaceNavigationGuard();
}


