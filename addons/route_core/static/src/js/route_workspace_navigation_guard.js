/** @odoo-module **/

const STORAGE_KEYS = {
    workspaceHash: "route_core.v16.workspace.hash",
    workspaceUrl: "route_core.v16.workspace.url",
    productCenterHash: "route_core.v16.product_center.hash",
    productCenterUrl: "route_core.v16.product_center.url",
    outletCenterHash: "route_core.v16.outlet_center.hash",
    outletCenterUrl: "route_core.v16.outlet_center.url",
    outletFormHash: "route_core.v16.outlet_form.hash",
    outletFormUrl: "route_core.v16.outlet_form.url",
    outletSubpageButton: "route_core.v16.outlet_subpage.button",
    outletSubpageTs: "route_core.v16.outlet_subpage.ts",
    pendingButtonName: "route_core.v16.pending.button_name",
    pendingButtonTs: "route_core.v16.pending.button_ts",
    outletWorkspaceActiveTs: "route_core.v16.outlet_workspace.active_ts",
    browserGuardSignature: "route_core.v16.browser_guard_signature",
};

const INLINE_BACK_WRAPPER_ID = "route-workspace-inline-back-wrapper";
const INLINE_BACK_BUTTON_ID = "route-workspace-inline-back-btn";
const FLOATING_BACK_WRAPPER_ID = "route-workspace-floating-back-wrapper";
const FLOATING_BACK_BUTTON_ID = "route-workspace-floating-back-btn";
const PRODUCT_CENTER_BUTTON = "action_open_product_center_screen";
const OUTLET_CENTER_BUTTON = "action_open_outlet_center_screen";
const PRODUCT_CENTER_DIRECT_ROUTE = "/route_core/pda/product_center";
const OUTLET_CENTER_DIRECT_ROUTE = "/route_core/pda/outlet_center";
const STOCK_PAGE_KINDS = new Set(["vehicle_stock", "warehouse_stock", "outlet_stock", "all_products"]);
const OUTLET_WORKSPACE_ENTRY_BUTTONS = new Set([
    "action_open_direct_sale_customers",
    "action_open_consignment_customers",
    "action_open_all_outlets",
]);
const OUTLET_FORM_ENTRY_BUTTONS = new Set([
    "action_view_visits",
    "action_view_payments",
    "action_view_sale_orders",
    "action_view_return_orders",
    "action_view_transfers",
    "action_view_stock_balances",
]);
const OUTLET_WORKSPACE_FLAG_TTL = 30 * 60 * 1000;
const OUTLET_SUBPAGE_FLAG_TTL = 90 * 1000;

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

function getBreadcrumbText() {
    const texts = [];
    const selectors = [
        ".o_control_panel .breadcrumb-item",
        ".o_control_panel .o_breadcrumb li",
        ".o_control_panel_breadcrumbs .breadcrumb-item",
        ".breadcrumb-item",
    ];
    for (const selector of selectors) {
        for (const element of document.querySelectorAll(selector)) {
            if (!isElementVisible(element)) {
                continue;
            }
            const text = normalizeText(element.textContent || "");
            if (text && !texts.includes(text)) {
                texts.push(text);
            }
        }
    }
    return texts.join(" / ");
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

function isOutletCenterPage() {
    return hasAnyVisibleButton(Array.from(OUTLET_WORKSPACE_ENTRY_BUTTONS));
}

function isOutletWorkspaceActive() {
    const timestamp = parseInt(sessionStorage.getItem(STORAGE_KEYS.outletWorkspaceActiveTs) || "0", 10);
    if (!timestamp) {
        return false;
    }
    if (Date.now() - timestamp > OUTLET_WORKSPACE_FLAG_TTL) {
        clearOutletWorkspaceActive();
        return false;
    }
    return true;
}

function markOutletWorkspaceActive() {
    sessionStorage.setItem(STORAGE_KEYS.outletWorkspaceActiveTs, String(Date.now()));
}

function clearOutletWorkspaceActive() {
    sessionStorage.removeItem(STORAGE_KEYS.outletWorkspaceActiveTs);
}

function setRecentOutletSubpage(buttonName) {
    if (!buttonName) {
        return;
    }
    sessionStorage.setItem(STORAGE_KEYS.outletSubpageButton, buttonName);
    sessionStorage.setItem(STORAGE_KEYS.outletSubpageTs, String(Date.now()));
}

function clearRecentOutletSubpage() {
    sessionStorage.removeItem(STORAGE_KEYS.outletSubpageButton);
    sessionStorage.removeItem(STORAGE_KEYS.outletSubpageTs);
}

function getRecentOutletSubpage() {
    const buttonName = sessionStorage.getItem(STORAGE_KEYS.outletSubpageButton) || "";
    const timestamp = parseInt(sessionStorage.getItem(STORAGE_KEYS.outletSubpageTs) || "0", 10);
    if (!buttonName) {
        return "";
    }
    if (timestamp && Date.now() - timestamp > OUTLET_SUBPAGE_FLAG_TTL) {
        clearRecentOutletSubpage();
        return "";
    }
    return buttonName;
}

function recentOutletSubpageIs(buttonNames) {
    const buttonName = getRecentOutletSubpage();
    return !!buttonName && buttonNames.includes(buttonName);
}

function isOutletWorkspacePage() {
    if (!isOutletWorkspaceActive()) {
        return false;
    }
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const pageText = getPageText();
    const breadcrumbText = getBreadcrumbText();
    const listLike = (
        ["outlets", "direct sale customers", "consignment customers", "all outlets"].includes(title)
        || breadcrumbText.includes("outlets")
        || pageText.includes("customer and outlets")
    ) && (
        rootText.includes("outlet code")
        || rootText.includes("current due")
        || rootText.includes("last visit")
        || pageText.includes("outlet code")
    );
    return listLike;
}

function isOutletFormPage() {
    if (!isOutletWorkspaceActive()) {
        return false;
    }
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const breadcrumbText = getBreadcrumbText();
    const hasOutletButtons = hasAnyVisibleButton(Array.from(OUTLET_FORM_ENTRY_BUTTONS));
    const hasOutletTabs = rootText.includes("outlet summary") || rootText.includes("outlet details") || rootText.includes("financial snapshot") || rootText.includes("consignment stock snapshot");
    const hasQuickSnapshot = rootText.includes("quick snapshot") && rootText.includes("current due") && rootText.includes("last visit date");
    const hasOutletTrail = breadcrumbText.includes("outlets") || breadcrumbText.includes("customer and outlets");
    return !!(
        (hasOutletButtons && hasQuickSnapshot)
        || (hasOutletTrail && hasOutletTabs)
        || (title && title !== "outlets" && title !== "customer and outlets" && hasQuickSnapshot)
    );
}

function isOutletRelatedSubpage(pageNames, requiredHints = [], originButtons = []) {
    if (!isOutletWorkspaceActive()) {
        return false;
    }
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const pageText = getPageText();
    const breadcrumbText = getBreadcrumbText();
    const hasOutletTrail = breadcrumbText.includes("outlets") || breadcrumbText.includes("customer and outlets");
    const hasRecentOrigin = originButtons.length ? recentOutletSubpageIs(originButtons) : false;
    if (!pageNames.includes(title)) {
        return false;
    }
    if (!(hasOutletTrail || hasRecentOrigin)) {
        return false;
    }
    return requiredHints.length
        ? requiredHints.some((hint) => rootText.includes(hint) || pageText.includes(hint))
        : true;
}

function isOutletVisitsPage() {
    return isOutletRelatedSubpage(["outlet visits", "visits", "my visits"], ["process", "visit", "outlet"], ["action_view_visits"]);
}

function isOutletPaymentsPage() {
    return isOutletRelatedSubpage(["outlet payments", "payments", "all payments"], ["payment", "collected", "open due", "promise"], ["action_view_payments"]);
}

function isOutletSaleOrdersPage() {
    return isOutletRelatedSubpage(["outlet sales orders", "sale orders", "sales orders", "all sale orders"], ["invoice status", "order date", "salesperson", "customer", "order snapshot"], ["action_view_sale_orders"]);
}

function isOutletReturnsPage() {
    if (!isOutletWorkspaceActive()) {
        return false;
    }
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const pageText = getPageText();
    const breadcrumbText = getBreadcrumbText();
    const hasOutletTrail = breadcrumbText.includes("outlets") || breadcrumbText.includes("customer and outlets") || recentOutletSubpageIs(["action_view_return_orders"]);
    if (!hasOutletTrail) {
        return false;
    }
    return (
        title.includes("return")
        || title.includes("returns")
        || rootText.includes("return date")
        || rootText.includes("create return pickings")
        || pageText.includes("vehicle return")
        || pageText.includes("damaged return")
        || pageText.includes("near expiry return")
    );
}

function isOutletTransfersPage() {
    if (!isOutletWorkspaceActive()) {
        return false;
    }
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const pageText = getPageText();
    const breadcrumbText = getBreadcrumbText();
    const hasOutletTrail = breadcrumbText.includes("outlets") || breadcrumbText.includes("customer and outlets") || recentOutletSubpageIs(["action_view_transfers"]);
    if (!hasOutletTrail) {
        return false;
    }
    return (
        title.includes("transfer")
        || title.includes("transfers")
        || pageText.includes("from")
        || pageText.includes("to vehicle")
        || pageText.includes("mus/stock")
        || rootText.includes("from")
    );
}

function isOutletStockFromOutletPage() {
    if (!isOutletWorkspaceActive()) {
        return false;
    }
    const title = normalizeText(findActionTitle());
    const rootText = getRootText();
    const pageText = getPageText();
    const breadcrumbText = getBreadcrumbText();
    const hasOutletTrail = breadcrumbText.includes("outlets") || breadcrumbText.includes("customer and outlets") || recentOutletSubpageIs(["action_view_stock_balances"]);
    if (!hasOutletTrail) {
        return false;
    }
    return (
        title.includes("outlet stock")
        || title.includes("stock balances")
        || rootText.includes("outlet stock")
        || rootText.includes("stock balances")
        || pageText.includes("outlet stock")
        || pageText.includes("stock balances")
    );
}

function isDailySummaryPage() {
    return hasVisibleButton("action_back_from_collections_snapshot")
        && hasVisibleButton("action_open_current_visit_statement_of_account");
}

function findRouteSalesAppTile() {
    const candidates = Array.from(document.querySelectorAll("a, button, .o_app, .o_app_switcher_item"));
    return candidates.find((element) => {
        if (!isElementVisible(element)) {
            return false;
        }
        const text = normalizeText(element.textContent || "");
        return text === "route sales" || text.includes("route sales");
    }) || null;
}

function isAppsHomePage() {
    if (isRouteWorkspacePage()) {
        return false;
    }
    return !!findRouteSalesAppTile() && !hasVisibleButton(PRODUCT_CENTER_BUTTON);
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
    if (isOutletCenterPage()) {
        return "outlet_center";
    }
    if (isOutletWorkspacePage()) {
        return "outlet_workspace";
    }
    if (isOutletFormPage()) {
        return "outlet_form";
    }
    if (isOutletVisitsPage()) {
        return "outlet_visits";
    }
    if (isOutletPaymentsPage()) {
        return "outlet_payments";
    }
    if (isOutletSaleOrdersPage()) {
        return "outlet_sales_orders";
    }
    if (isOutletReturnsPage()) {
        return "outlet_returns";
    }
    if (isOutletTransfersPage()) {
        return "outlet_transfers";
    }
    if (isOutletStockFromOutletPage()) {
        return "outlet_stock_from_outlet";
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
        title.includes("vehicle stock")
        || title.includes("vehicle products stock")
        || rootText.includes("vehicle stock")
        || rootText.includes("vehicle products stock")
        || pageText.includes("vehicle stock")
        || pageText.includes("vehicle products stock")
    ) {
        return "vehicle_stock";
    }

    if (
        title.includes("warehouse stock")
        || title.includes("main warehouse products stock")
        || rootText.includes("warehouse stock")
        || rootText.includes("main warehouse products stock")
        || pageText.includes("warehouse stock")
        || pageText.includes("main warehouse products stock")
    ) {
        return "warehouse_stock";
    }

    if (
        title.includes("outlet stock")
        || title.includes("consignment outlets stock")
        || title.includes("outlet stock balances")
        || rootText.includes("outlet stock")
        || rootText.includes("outlet stock balances")
        || pageText.includes("outlet stock")
        || pageText.includes("outlet stock balances")
    ) {
        return "outlet_stock";
    }

    if (
        (title === "products" || title === "all products" || title === "product catalog" || rootText.includes("all products") || pageText.includes("all products"))
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
    // Compatibility hook kept intentionally.
}

function rememberNavigationTargets() {
    const pageKind = detectPageKind();
    if (pageKind === "workspace") {
        clearOutletWorkspaceActive();
        rememberPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
    }
    if (pageKind === "product_center") {
        clearOutletWorkspaceActive();
        rememberPair(STORAGE_KEYS.productCenterHash, STORAGE_KEYS.productCenterUrl);
    }
    if (["outlet_center", "outlet_workspace", "outlet_form", "outlet_visits", "outlet_payments", "outlet_sales_orders", "outlet_returns", "outlet_transfers", "outlet_stock_from_outlet"].includes(pageKind)) {
        markOutletWorkspaceActive();
    }
    if (pageKind === "outlet_center") {
        rememberPair(STORAGE_KEYS.outletCenterHash, STORAGE_KEYS.outletCenterUrl);
        clearRecentOutletSubpage();
    }
    if (pageKind === "outlet_form") {
        rememberPair(STORAGE_KEYS.outletFormHash, STORAGE_KEYS.outletFormUrl);
    }
    if (["workspace", "product_center", "snapshot_center", "collections_center", "daily_summary"].includes(pageKind) || isAppsHomePage()) {
        clearOutletWorkspaceActive();
        clearRecentOutletSubpage();
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
        "action_open_outlet_center_screen",
    ].includes(name)) {
        rememberPair(STORAGE_KEYS.workspaceHash, STORAGE_KEYS.workspaceUrl);
    }
    if (OUTLET_WORKSPACE_ENTRY_BUTTONS.has(name)) {
        markOutletWorkspaceActive();
        clearRecentOutletSubpage();
    }
    if (OUTLET_FORM_ENTRY_BUTTONS.has(name)) {
        rememberPair(STORAGE_KEYS.outletFormHash, STORAGE_KEYS.outletFormUrl);
        markOutletWorkspaceActive();
        setRecentOutletSubpage(name);
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

function getOutletCenterTarget() {
    return {
        hash: sessionStorage.getItem(STORAGE_KEYS.outletCenterHash) || "",
        url: sessionStorage.getItem(STORAGE_KEYS.outletCenterUrl) || "",
    };
}

function getOutletFormTarget() {
    return {
        hash: sessionStorage.getItem(STORAGE_KEYS.outletFormHash) || "",
        url: sessionStorage.getItem(STORAGE_KEYS.outletFormUrl) || "",
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

function findWorkspaceMenuCandidate({ allowHidden = false } = {}) {
    const candidates = Array.from(document.querySelectorAll("a, button"));
    return candidates.find((element) => {
        const text = normalizeText(element.textContent);
        if (text !== "route workspace") {
            return false;
        }
        return allowHidden || isElementVisible(element);
    }) || null;
}

function openWorkspaceMenuFallback() {
    const link = findWorkspaceMenuCandidate({ allowHidden: false });
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

function openWorkspaceMenuHiddenFallback() {
    const link = findWorkspaceMenuCandidate({ allowHidden: true });
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

function navigateToStoredTarget(target) {
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
    if (isSmallScreen() && openWorkspaceMenuHiddenFallback()) {
        return;
    }
    const workspaceTarget = getWorkspaceTarget();
    navigateToStoredTarget(workspaceTarget);
}

function navigateDirectToProductCenter() {
    isInternalRedirect = true;
    window.location.assign(PRODUCT_CENTER_DIRECT_ROUTE);
    window.setTimeout(() => {
        isInternalRedirect = false;
    }, 1200);
}

function navigateBackToProductCenter() {
    navigateDirectToProductCenter();
}

function navigateBackToOutletCenter() {
    const outletCenterTarget = getOutletCenterTarget();
    if (navigateToStoredTarget(outletCenterTarget)) {
        return;
    }
    if (openServerButton(OUTLET_CENTER_BUTTON)) {
        return;
    }
    isInternalRedirect = true;
    window.location.assign(OUTLET_CENTER_DIRECT_ROUTE);
    window.setTimeout(() => {
        isInternalRedirect = false;
    }, 1200);
}

function navigateBackToOutletForm() {
    const outletTarget = getOutletFormTarget();
    if (navigateToStoredTarget(outletTarget)) {
        return;
    }
    const targetUrl = outletTarget?.url || "";
    const match = targetUrl.match(/[?#&]id=(\d+)(?:&|$)/);
    if (match && match[1]) {
        isInternalRedirect = true;
        window.location.assign(`/route_core/pda/outlet/${match[1]}`);
        window.setTimeout(() => {
            isInternalRedirect = false;
        }, 1200);
        return;
    }
    navigateBackToOutletCenter();
}

function maybeRunPendingFromAppsHome() {
    const pendingButton = getPendingButton();
    if (!pendingButton) {
        return;
    }
    if (!isAppsHomePage()) {
        return;
    }
    const routeSalesTile = findRouteSalesAppTile();
    if (!routeSalesTile) {
        return;
    }
    window.setTimeout(() => {
        isInternalRedirect = true;
        dispatchClick(routeSalesTile);
        window.setTimeout(() => {
            isInternalRedirect = false;
        }, 1200);
    }, 150);
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

function findTopLeftNavigationCandidate(element) {
    if (!element?.closest) {
        return null;
    }
    const selectors = [
        ".o_control_panel .breadcrumb-item a",
        ".o_control_panel .breadcrumb-item",
        ".o_control_panel .o_breadcrumb li a",
        ".o_control_panel .o_breadcrumb li",
        ".o_control_panel_breadcrumbs .breadcrumb-item a",
        ".o_control_panel_breadcrumbs .breadcrumb-item",
        ".breadcrumb-item a",
        ".breadcrumb-item",
        ".o_control_panel a",
        ".o_control_panel button",
        "a",
        "button",
    ];
    for (const selector of selectors) {
        const match = element.closest(selector);
        if (match && isElementVisible(match)) {
            return match;
        }
    }
    return null;
}

function isOutletFormMobileTopNavClick(element, pageKind) {
    if (pageKind !== "outlet_form" || !isSmallScreen()) {
        return false;
    }
    const candidate = findTopLeftNavigationCandidate(element);
    if (!candidate || candidate.id === FLOATING_BACK_BUTTON_ID || candidate.id === INLINE_BACK_BUTTON_ID) {
        return false;
    }

    const rect = candidate.getBoundingClientRect();
    if (rect.top > 150 || rect.left > 320) {
        return false;
    }

    const text = normalizeText(candidate.textContent || "");
    const title = normalizeText(findActionTitle());
    if (!text) {
        return false;
    }

    const titleLooksLikeOutletName = !!title && title !== "outlets" && title !== "customer and outlets";
    const matchesOutletTrail = (
        text === "outlets"
        || text === "customer and outlets"
        || text.includes("outlet")
        || text.includes("customer")
        || (titleLooksLikeOutletName && text === title)
    );
    if (!matchesOutletTrail) {
        return false;
    }

    const classes = normalizeText(`${candidate.className || ""} ${candidate.parentElement?.className || ""}`);
    if (classes.includes("menu") || classes.includes("user") || classes.includes("dropdown") || classes.includes("search")) {
        return false;
    }
    return true;
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

function getBackConfig(pageKind) {
    if (STOCK_PAGE_KINDS.has(pageKind)) {
        return {
            label: "Back to Products and Stock",
            onClick: navigateBackToProductCenter,
            interceptBrowser: true,
            interceptMobileHeader: true,
        };
    }
    if (["outlet_workspace", "outlet_form"].includes(pageKind)) {
        return {
            label: "Back to Customer and Outlets",
            onClick: navigateBackToOutletCenter,
            interceptBrowser: true,
            interceptMobileHeader: true,
        };
    }
    if (["outlet_visits", "outlet_payments", "outlet_sales_orders", "outlet_returns", "outlet_transfers", "outlet_stock_from_outlet"].includes(pageKind)) {
        return {
            label: "Back to Outlet",
            onClick: navigateBackToOutletForm,
            interceptBrowser: true,
            interceptMobileHeader: true,
        };
    }
    return null;
}

function buildInlineBackButton(config, pageKind) {
    const wrapper = document.createElement("div");
    wrapper.id = INLINE_BACK_WRAPPER_ID;
    wrapper.style.display = "block";
    wrapper.style.margin = "12px 16px 8px 16px";
    wrapper.dataset.backKind = pageKind;

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
    button.innerHTML = `<i class="fa fa-arrow-left"></i><span>${config.label}</span>`;

    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        config.onClick();
    });

    wrapper.appendChild(button);
    return wrapper;
}

function buildFloatingBackButton(config, pageKind) {
    const wrapper = document.createElement("div");
    wrapper.id = FLOATING_BACK_WRAPPER_ID;
    wrapper.style.position = "fixed";
    wrapper.style.left = "12px";
    wrapper.style.top = "110px";
    wrapper.style.zIndex = "9999";
    wrapper.style.pointerEvents = "auto";
    wrapper.dataset.backKind = pageKind;

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
    button.title = config.label;
    button.innerHTML = `<i class="fa fa-arrow-left"></i><span>${config.label}</span>`;

    button.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        config.onClick();
    });

    wrapper.appendChild(button);
    return wrapper;
}

function ensureBackButton() {
    const pageKind = detectPageKind();
    const backConfig = getBackConfig(pageKind);
    if (!backConfig) {
        removeInlineBackButton();
        removeFloatingBackButton();
        return;
    }

    if (isSmallScreen()) {
        removeInlineBackButton();
        removeFloatingBackButton();
        return;
    }

    removeFloatingBackButton();
    const host = getDesktopBackHost();
    if (!host) {
        return;
    }
    let wrapper = document.getElementById(INLINE_BACK_WRAPPER_ID);
    if (!wrapper || wrapper.dataset.backKind !== pageKind) {
        removeInlineBackButton();
        wrapper = buildInlineBackButton(backConfig, pageKind);
        host.prepend(wrapper);
        return;
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
    const backConfig = getBackConfig(pageKind);
    if (!backConfig || !backConfig.interceptBrowser) {
        return;
    }
    isInternalRedirect = true;
    window.setTimeout(() => {
        backConfig.onClick();
        window.setTimeout(() => {
            isInternalRedirect = false;
        }, 900);
    }, 0);
}

function interceptMobileHeaderBack(event) {
    if (isInternalRedirect || !isSmallScreen()) {
        return;
    }
    const pageKind = detectPageKind();
    const backConfig = getBackConfig(pageKind);
    if (!backConfig || !backConfig.interceptMobileHeader) {
        return;
    }
    if (!(looksLikeMobileHeaderBackControl(event.target) || isOutletFormMobileTopNavClick(event.target, pageKind))) {
        return;
    }

    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
        event.stopImmediatePropagation();
    }
    backConfig.onClick();
}

function interceptBreadcrumbBack(event) {
    if (isInternalRedirect) {
        return;
    }
    const pageKind = detectPageKind();
    const backConfig = getBackConfig(pageKind);
    if (!backConfig) {
        return;
    }
    const breadcrumb = findTopLeftNavigationCandidate(event.target);
    if (!breadcrumb || !isElementVisible(breadcrumb)) {
        return;
    }
    const rect = breadcrumb.getBoundingClientRect();
    if (rect.top > 160) {
        return;
    }
    const text = normalizeText(breadcrumb.textContent || "");
    const title = normalizeText(findActionTitle());
    const inTopLeftZone = rect.left < (isSmallScreen() ? 320 : 420);
    if (!inTopLeftZone) {
        return;
    }

    const shouldForceOutletMobileBack = isOutletFormMobileTopNavClick(event.target, pageKind);
    const looksLikeRegularBreadcrumbBack = text && (
        text !== title
        || rect.left < 120
        || text.includes("outlet")
        || text.includes("customer")
        || text.includes("products")
        || text.includes("stock")
        || text.includes("transfer")
        || text.includes("return")
    );
    if (!(shouldForceOutletMobileBack || looksLikeRegularBreadcrumbBack)) {
        return;
    }

    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
        event.stopImmediatePropagation();
    }
    backConfig.onClick();
}

function ensureBrowserGuard(pageKind) {
    const backConfig = getBackConfig(pageKind);
    if (!backConfig || !backConfig.interceptBrowser) {
        sessionStorage.removeItem(STORAGE_KEYS.browserGuardSignature);
        return;
    }
    const signature = `${pageKind}|${window.location.pathname}|${window.location.search}|${window.location.hash}`;
    if (sessionStorage.getItem(STORAGE_KEYS.browserGuardSignature) === signature) {
        return;
    }
    sessionStorage.setItem(STORAGE_KEYS.browserGuardSignature, signature);
    try {
        window.history.pushState({ ...(window.history.state || {}), routeWorkspaceGuard: signature }, "", window.location.href);
    } catch (_error) {
        // ignore pushState edge cases
    }
}

function refreshNavigationUi() {
    rememberVisibleActionButtons();
    rememberNavigationTargets();
    maybeRunPendingFromAppsHome();
    maybeRunPendingButton();
    ensureBackButton();
    ensureBrowserGuard(detectPageKind());
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
    document.addEventListener("click", interceptBreadcrumbBack, true);
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


