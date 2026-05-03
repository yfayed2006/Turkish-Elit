import json
from html import escape
from urllib.parse import quote_plus

from odoo import fields, http, _
from odoo.http import request


class RouteMapFrameController(http.Controller):
    """Iframe map pages used by Route Core PDA and supervisor location screens.

    These routes intentionally return plain HTML because the map is embedded
    inside backend HTML fields. Keeping the route in an Odoo HTTP controller
    avoids the website 404 page being rendered inside the iframe.
    """

    # -------------------------------------------------------------------------
    # Generic helpers
    # -------------------------------------------------------------------------
    def _html_response(self, body, status=200):
        return request.make_response(
            body,
            headers=[
                ("Content-Type", "text/html; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
            status=status,
        )

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
            ],
            status=status,
        )

    def _safe_text(self, value, default=""):
        if value is None or value is False:
            return default
        return str(value)

    def _html_escape(self, value, default="", quote=True):
        return escape(self._safe_text(value, default), quote=quote)

    def _safe_float(self, value):
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    def _has_point(self, lat, lng):
        return bool(self._safe_float(lat) or self._safe_float(lng))

    def _format_number(self, value, digits=2):
        try:
            return ("%%.%sf" % digits) % float(value or 0.0)
        except Exception:
            return "0.00"

    def _format_money(self, value, currency=None):
        amount = self._format_number(value, 2)
        symbol = getattr(currency, "symbol", False) or ""
        return "%s %s" % (amount, symbol) if symbol else amount

    def _display_date(self, value):
        if not value:
            return ""
        try:
            if isinstance(value, str):
                return value
            return fields.Date.to_string(value)
        except Exception:
            return str(value)

    def _display_datetime(self, value):
        if not value:
            return ""
        try:
            user_tz_value = fields.Datetime.context_timestamp(request.env.user, value)
            return user_tz_value.strftime("%b %-d, %-I:%M %p")
        except Exception:
            try:
                user_tz_value = fields.Datetime.context_timestamp(request.env.user, value)
                return user_tz_value.strftime("%b %d, %I:%M %p")
            except Exception:
                return str(value)

    def _field_label(self, record, field_name, value=None):
        if not record or field_name not in record._fields:
            return self._safe_text(value)
        if value is None:
            value = record[field_name]
        field = record._fields[field_name]
        selection = field.selection
        if callable(selection):
            try:
                selection = selection(record.env[record._name])
            except Exception:
                selection = []
        return dict(selection or []).get(value, self._safe_text(value))

    def _first_field_value(self, record, names, default=0.0):
        for name in names:
            if name in record._fields:
                return record[name] or default
        return default

    def _backend_visit_url(self, visit, pda=True):
        base = "/web#id=%s&model=route.visit&view_type=form" % visit.id
        if pda:
            action = request.env.ref("route_core.action_route_visit_pda_salesperson", raise_if_not_found=False)
            if action:
                return "/web#id=%s&action=%s&model=route.visit&view_type=form" % (visit.id, action.id)
        return base

    def _google_map_url(self, lat, lng):
        if self._has_point(lat, lng):
            return "https://www.google.com/maps/search/?api=1&query=%s,%s" % (lat, lng)
        return False

    def _google_route_url(self, lat, lng):
        if self._has_point(lat, lng):
            return "https://www.google.com/maps/dir/?api=1&destination=%s,%s" % (lat, lng)
        return False

    def _maps_search_url(self, text):
        query = self._safe_text(text).strip()
        if not query:
            return False
        return "https://www.google.com/maps/search/?api=1&query=%s" % quote_plus(query)

    def _visit_bucket(self, visit):
        process = getattr(visit, "visit_process_state", False) or False
        state = getattr(visit, "state", False) or False
        if state in ("done", "cancel", "cancelled") or process in ("done", "cancel"):
            return "done"
        if state == "in_progress" or process in ("checked_in", "counting", "reconciled", "collection_done", "ready_to_close"):
            return "active"
        return "pending"

    def _visit_visual_state(self, visit):
        process = getattr(visit, "visit_process_state", False) or False
        state = getattr(visit, "state", False) or False
        if state in ("cancel", "cancelled") or process == "cancel":
            return "cancelled"
        if state == "done" or process == "done":
            return "done"
        if process == "ready_to_close":
            return "ready"
        if state == "in_progress" or process in ("checked_in", "counting", "reconciled", "collection_done"):
            return "active"
        return "pending"

    def _visit_visual_label(self, visit):
        visual_state = self._visit_visual_state(visit)
        labels = {
            "pending": _("Pending"),
            "active": _("In Progress"),
            "ready": _("Ready To Close"),
            "done": _("Done"),
            "cancelled": _("Cancelled"),
        }
        return labels.get(visual_state, self._visit_process_label(visit) or _("Pending"))

    def _visit_geo_status(self, visit):
        return getattr(visit, "geo_checkin_status", False) or getattr(visit, "geo_review_state", False) or ""

    def _visit_mode_label(self, visit):
        for field_name in ("visit_mode", "operation_mode", "outlet_operation_mode"):
            if field_name in visit._fields and visit[field_name]:
                return self._field_label(visit, field_name)
        outlet = visit.outlet_id
        if outlet and "outlet_operation_mode" in outlet._fields and outlet.outlet_operation_mode:
            return self._field_label(outlet, "outlet_operation_mode")
        return "Visit"

    def _visit_process_label(self, visit):
        if "visit_process_state" in visit._fields and visit.visit_process_state:
            return self._field_label(visit, "visit_process_state")
        if "state" in visit._fields and visit.state:
            return self._field_label(visit, "state")
        return ""

    def _route_state_badges(self, visit):
        badges = []
        visual_state = self._visit_visual_state(visit)
        badges.append({
            "label": self._visit_visual_label(visit),
            "style": visual_state,
        })

        geo_status = getattr(visit, "geo_checkin_status", False)
        if geo_status == "outside":
            badges.append({"label": "Outside Zone", "style": "outside"})
        elif geo_status == "inside":
            badges.append({"label": "Inside Zone", "style": "inside"})
        elif geo_status == "outlet_missing":
            badges.append({"label": "No Outlet GPS", "style": "warning"})
        elif geo_status == "pending":
            badges.append({"label": "No Check-in", "style": "muted"})
        return badges

    def _geo_review_badges(self, visit):
        badges = []
        state = getattr(visit, "geo_review_state", False)
        decision = getattr(visit, "geo_review_supervisor_decision", False)
        if state == "outside_no_reason":
            badges.append({"label": "Outside - No Reason", "style": "danger"})
        elif state == "outside_with_reason":
            badges.append({"label": "Outside Zone", "style": "outside"})
        elif state == "inside_zone":
            badges.append({"label": "Inside Zone", "style": "inside"})
        elif state == "outlet_missing":
            badges.append({"label": "No Outlet GPS", "style": "warning"})
        elif state == "pending_checkin":
            badges.append({"label": "No Check-in", "style": "muted"})

        if decision == "accepted":
            badges.append({"label": "Accepted", "style": "accepted"})
        elif decision == "needs_correction":
            badges.append({"label": "Needs Correction", "style": "correction"})
        elif getattr(visit, "geo_review_required", False):
            badges.append({"label": "Review", "style": "review"})
        return badges

    # -------------------------------------------------------------------------
    # Data builders
    # -------------------------------------------------------------------------
    def _salesperson_visit_payload(self, visit, index):
        outlet = visit.outlet_id
        partner = outlet.partner_id if outlet and "partner_id" in outlet._fields else False
        currency = getattr(visit, "currency_id", False) or request.env.company.currency_id
        lat = self._safe_float(getattr(outlet, "geo_latitude", 0.0)) if outlet else 0.0
        lng = self._safe_float(getattr(outlet, "geo_longitude", 0.0)) if outlet else 0.0
        due_now = self._first_field_value(
            visit,
            ("current_visit_remaining", "visit_remaining_amount", "amount_due", "total_outlet_due", "outlet_due_amount"),
            0.0,
        )
        remaining = self._first_field_value(
            visit,
            ("current_visit_remaining", "visit_remaining_amount", "remaining_amount", "amount_due"),
            0.0,
        )
        return {
            "id": visit.id,
            "index": index,
            "name": self._safe_text(visit.display_name or visit.name),
            "outlet": self._safe_text(outlet.display_name if outlet else "No outlet"),
            "customer": self._safe_text(partner.display_name if partner else ""),
            "area": self._safe_text(visit.area_id.display_name if getattr(visit, "area_id", False) else (outlet.area_id.display_name if outlet and outlet.area_id else "")),
            "salesperson": self._safe_text(visit.user_id.display_name if getattr(visit, "user_id", False) else ""),
            "vehicle": self._safe_text(visit.vehicle_id.display_name if getattr(visit, "vehicle_id", False) else ""),
            "date": self._display_date(getattr(visit, "date", False)),
            "mode": self._visit_mode_label(visit),
            "status": self._visit_process_label(visit),
            "bucket": self._visit_bucket(visit),
            "statusClass": self._visit_visual_state(visit),
            "statusLabel": self._visit_visual_label(visit),
            "geoStatus": self._visit_geo_status(visit),
            "current_step": self._visit_process_label(visit) or self._field_label(visit, "state", getattr(visit, "state", False)),
            "due_now": self._format_money(due_now, currency),
            "remaining": self._format_money(remaining, currency),
            "lat": lat,
            "lng": lng,
            "hasPoint": self._has_point(lat, lng),
            "distance": self._safe_text(getattr(visit, "geo_checkin_distance_display", False), ""),
            "badges": self._route_state_badges(visit),
            "openUrl": self._backend_visit_url(visit, pda=True),
            "outletMapUrl": self._google_map_url(lat, lng) or self._maps_search_url(self._safe_text(outlet.display_name if outlet else "")),
            "navigationUrl": self._google_route_url(lat, lng) or self._maps_search_url(self._safe_text(outlet.display_name if outlet else "")),
        }

    def _geo_visit_payload(self, visit, index):
        outlet = visit.outlet_id
        partner = outlet.partner_id if outlet and "partner_id" in outlet._fields else False
        outlet_lat = self._safe_float(getattr(outlet, "geo_latitude", 0.0)) if outlet else 0.0
        outlet_lng = self._safe_float(getattr(outlet, "geo_longitude", 0.0)) if outlet else 0.0
        checkin_lat = self._safe_float(getattr(visit, "geo_checkin_latitude", 0.0))
        checkin_lng = self._safe_float(getattr(visit, "geo_checkin_longitude", 0.0))
        decision = getattr(visit, "geo_review_supervisor_decision", False) or ""
        review_required = bool(getattr(visit, "geo_review_required", False))
        return {
            "id": visit.id,
            "index": index,
            "name": self._safe_text(visit.display_name or visit.name),
            "outlet": self._safe_text(outlet.display_name if outlet else "No outlet"),
            "customer": self._safe_text(partner.display_name if partner else ""),
            "area": self._safe_text(visit.area_id.display_name if getattr(visit, "area_id", False) else (outlet.area_id.display_name if outlet and outlet.area_id else "")),
            "salesperson": self._safe_text(visit.user_id.display_name if getattr(visit, "user_id", False) else ""),
            "vehicle": self._safe_text(visit.vehicle_id.display_name if getattr(visit, "vehicle_id", False) else ""),
            "date": self._display_date(getattr(visit, "date", False)),
            "mode": self._visit_mode_label(visit),
            "status": self._visit_process_label(visit),
            "bucket": self._visit_bucket(visit),
            "statusClass": self._visit_visual_state(visit),
            "statusLabel": self._visit_visual_label(visit),
            "geoStatus": self._visit_geo_status(visit),
            "reviewState": self._field_label(visit, "geo_review_state", getattr(visit, "geo_review_state", False)),
            "decision": decision,
            "decisionLabel": self._field_label(visit, "geo_review_supervisor_decision", decision),
            "reviewRequired": review_required,
            "distance": self._safe_text(getattr(visit, "geo_checkin_distance_display", False), ""),
            "accuracy": self._format_number(getattr(visit, "geo_checkin_accuracy_m", 0.0), 0),
            "checkinTime": self._display_datetime(getattr(visit, "geo_checkin_datetime", False)),
            "reason": self._safe_text(getattr(visit, "geo_checkin_outside_zone_reason", False), ""),
            "outletLat": outlet_lat,
            "outletLng": outlet_lng,
            "checkinLat": checkin_lat,
            "checkinLng": checkin_lng,
            "hasOutletPoint": self._has_point(outlet_lat, outlet_lng),
            "hasCheckinPoint": self._has_point(checkin_lat, checkin_lng),
            "badges": self._geo_review_badges(visit),
            "openUrl": self._backend_visit_url(visit, pda=False),
            "outletMapUrl": self._google_map_url(outlet_lat, outlet_lng) or self._maps_search_url(self._safe_text(outlet.display_name if outlet else "")),
            "checkinMapUrl": self._google_map_url(checkin_lat, checkin_lng),
        }

    # -------------------------------------------------------------------------
    # HTML renderers
    # -------------------------------------------------------------------------
    def _base_head(self, title):
        return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>%(title)s</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
:root {
    --route-primary: #82466f;
    --route-primary-dark: #6b345b;
    --route-muted: #64748b;
    --route-border: #e5e7eb;
    --route-soft: #f8fafc;
    --route-title: #0f172a;
    --route-teal: #0ea5a7;
    --route-green: #16a34a;
    --route-orange: #f59e0b;
    --route-red: #dc2626;
    --route-blue: #0284c7;
    --route-pending: #06b6d4;
    --route-active: #f97316;
    --route-ready: #22c55e;
    --route-cancelled: #64748b;
    --route-outside: #ef4444;
}
@keyframes routeCurrentPulse {
    0%% { box-shadow: 0 0 0 0 rgba(130, 70, 111, 0.26), 0 12px 24px rgba(15, 23, 42, 0.24); }
    70%% { box-shadow: 0 0 0 10px rgba(130, 70, 111, 0.00), 0 12px 24px rgba(15, 23, 42, 0.24); }
    100%% { box-shadow: 0 0 0 0 rgba(130, 70, 111, 0.00), 0 12px 24px rgba(15, 23, 42, 0.24); }
}
* { box-sizing: border-box; }
body {
    margin: 0;
    padding: 14px;
    background: #f6f7fb;
    color: var(--route-title);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
}
.route-frame { max-width: 100%%; }
.route-frame.route-split-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.18fr) minmax(310px, .82fr);
    gap: 14px;
    align-items: stretch;
    height: calc(100vh - 28px);
    height: calc(100dvh - 28px);
    max-height: calc(100vh - 28px);
    max-height: calc(100dvh - 28px);
    min-height: 520px;
    overflow: hidden;
}
.route-map-panel,
.route-cards-panel {
    background: #fff;
    border: 1px solid var(--route-border);
    border-radius: 16px;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
    overflow: hidden;
}
.route-map-panel {
    margin-bottom: 14px;
}
.route-frame.route-split-layout .route-map-panel {
    margin-bottom: 0;
    min-height: 0;
    height: 100%%;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
}
.route-frame.route-split-layout .route-map-panel .route-map-header,
.route-map-panel.route-fixed-map .route-map-header {
    display: none !important;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards {
    min-height: 0;
    height: 100%%;
    max-height: none;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards .route-cards-grid {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%%;
    overflow-y: auto;
    overflow-x: hidden;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    touch-action: pan-y;
    display: block;
    padding: 14px;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards .route-card {
    margin-bottom: 12px;
    overflow: visible;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards .route-card:last-child {
    margin-bottom: 0;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards .route-card-body {
    display: block;
    overflow: visible;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards .route-card-metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards .route-metric {
    min-height: 60px;
}
.route-frame.route-split-layout .route-cards-panel.route-side-cards .route-metric-value {
    display: block;
}
.route-map-header,
.route-cards-header {
    padding: 14px 16px;
    border-bottom: 1px solid var(--route-border);
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
}
.route-map-title,
.route-cards-title {
    font-size: 16px;
    font-weight: 900;
    margin: 0;
}
.route-map-subtitle {
    font-size: 13px;
    color: var(--route-muted);
    margin-top: 4px;
}
#map {
    width: 100%%;
    height: clamp(360px, 48vh, 460px);
    background: #eef2f7;
    touch-action: pan-x pan-y;
}
.route-frame.route-split-layout #map {
    flex: 1 1 auto;
    min-height: 0;
    height: 100%%;
}
.route-map-floating-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    z-index: 500;
    border-radius: 999px;
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.92);
    color: var(--route-title);
    border: 1px solid rgba(130, 70, 111, 0.22);
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12);
    font-size: 12px;
    font-weight: 900;
}
.route-map-empty {
    display: none;
    padding: 26px;
    text-align: center;
    color: var(--route-muted);
    font-weight: 700;
}
.route-cards-grid {
    padding: 14px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 14px;
}
.route-card {
    border: 1px solid var(--route-border);
    border-radius: 16px;
    background: linear-gradient(180deg, #fff, #fbfbfd);
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
    overflow: hidden;
    transition: border-color .18s ease, box-shadow .18s ease, transform .18s ease;
}
.route-card.route-card-active {
    border-color: var(--route-primary);
    box-shadow: 0 12px 30px rgba(130, 70, 111, 0.22);
    transform: translateY(-2px);
}
.route-card-head {
    padding: 14px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
    border-bottom: 1px solid #eef2f7;
}
.route-card-index {
    width: 32px;
    height: 32px;
    min-width: 32px;
    border-radius: 999px;
    background: var(--route-pending);
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    box-shadow: 0 6px 14px rgba(15, 23, 42, 0.18);
}
.route-card-index.pending { background: var(--route-pending); }
.route-card-index.active { background: var(--route-active); }
.route-card-index.ready { background: var(--route-ready); }
.route-card-index.done { background: var(--route-green); }
.route-card-index.cancelled { background: var(--route-cancelled); }
.route-card-index.outside-zone {
    outline: 3px solid rgba(239, 68, 68, 0.28);
    outline-offset: 2px;
}
.route-card.pending { border-left: 4px solid var(--route-pending); }
.route-card.active { border-left: 4px solid var(--route-active); }
.route-card.ready,
.route-card.done { border-left: 4px solid var(--route-green); }
.route-card.cancelled { border-left: 4px solid var(--route-cancelled); }
.route-card.outside-zone { box-shadow: 0 8px 18px rgba(239, 68, 68, 0.08); }
.route-card-title { font-size: 18px; font-weight: 900; line-height: 1.15; }
.route-card-ref { font-size: 13px; font-weight: 800; color: var(--route-muted); margin-top: 4px; }
.route-badges { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
.route-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 5px 9px;
    font-size: 12px;
    font-weight: 900;
    white-space: nowrap;
    background: #e5e7eb;
    color: #334155;
}
.route-badge.pending { background: #cffafe; color: #0e7490; }
.route-badge.active { background: #fed7aa; color: #c2410c; }
.route-badge.ready { background: #dcfce7; color: #15803d; }
.route-badge.done { background: #dcfce7; color: #15803d; }
.route-badge.cancelled { background: #e2e8f0; color: #475569; }
.route-badge.outside,
.route-badge.danger { background: #fee2e2; color: #b91c1c; }
.route-badge.inside,
.route-badge.accepted { background: #dcfce7; color: #15803d; }
.route-badge.warning { background: #fef3c7; color: #b45309; }
.route-badge.review { background: #ede9fe; color: #6d28d9; }
.route-badge.correction { background: #ffedd5; color: #c2410c; }
.route-badge.muted { background: #e2e8f0; color: #475569; }
.route-card-body { padding: 12px 14px 14px; }
.route-card-metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 12px;
}
.route-metric {
    border: 1px solid #edf0f4;
    background: var(--route-soft);
    border-radius: 12px;
    padding: 9px 10px;
    min-height: 58px;
}
.route-metric-label {
    color: var(--route-muted);
    font-size: 12px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .02em;
}
.route-metric-value {
    margin-top: 4px;
    font-size: 14px;
    font-weight: 900;
    color: #111827;
    overflow-wrap: anywhere;
}
.route-card-note {
    color: var(--route-muted);
    font-size: 13px;
    line-height: 1.35;
    margin: 4px 0 12px;
}
.route-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.route-btn {
    border: 0;
    border-radius: 10px;
    padding: 9px 12px;
    background: #e5e7eb;
    color: #111827;
    font-weight: 900;
    text-decoration: none;
    cursor: pointer;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.route-btn.primary { background: var(--route-primary); color: #fff; }
.route-btn.success { background: var(--route-green); color: #fff; }
.route-btn.warning { background: var(--route-orange); color: #111827; }
.route-btn.danger { background: var(--route-red); color: #fff; }
.route-btn:disabled { opacity: .55; cursor: default; }

.leaflet-control-layers {
    border: 1px solid rgba(130, 70, 111, 0.18) !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.14) !important;
    font-weight: 800;
}
.leaflet-control-layers-expanded {
    padding: 8px 10px 8px 8px !important;
}
.leaflet-control-layers label {
    margin-bottom: 4px;
}
.leaflet-popup-content { min-width: 210px; }
.route-popup-title { font-weight: 900; font-size: 15px; margin-bottom: 4px; }
.route-popup-ref { color: #64748b; font-size: 12px; font-weight: 800; margin-bottom: 8px; }
.route-popup-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.route-popup-actions .route-btn { padding: 7px 9px; font-size: 12px; }
.route-marker {
    width: 34px;
    height: 34px;
    border-radius: 50%% 50%% 50%% 8%%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--route-primary);
    color: #fff;
    font-weight: 900;
    font-size: 14px;
    border: 3px solid #fff;
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.30);
    transform: rotate(-45deg) scale(1);
    transform-origin: center;
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.route-marker span {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 100%%;
    height: 100%%;
    transform: rotate(45deg);
    line-height: 1;
}
.route-marker.route-marker-focus {
    transform: rotate(-45deg) scale(1.36);
    border-color: #fef08a;
    box-shadow: 0 0 0 8px rgba(130, 70, 111, 0.18), 0 12px 26px rgba(15, 23, 42, 0.38);
    z-index: 1000;
}
.route-marker.done { background: var(--route-green); }
.route-marker.active { background: var(--route-active); }
.route-marker.pending { background: var(--route-pending); }
.route-marker.outlet { background: var(--route-blue); }
.route-marker.checkin { background: var(--route-primary); }
.route-status-message {
    display: none;
    margin: 0 14px 14px;
    padding: 12px 14px;
    border-radius: 12px;
    background: #ecfeff;
    color: #155e75;
    font-weight: 800;
}
.route-map-shell {
    max-width: 100%%;
    height: calc(100vh - 28px);
    height: calc(100dvh - 28px);
    max-height: calc(100vh - 28px);
    max-height: calc(100dvh - 28px);
    min-height: 560px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow: hidden;
}
.route-map-shell > .route-frame.route-split-layout {
    flex: 1 1 auto;
    min-height: 0;
    height: auto;
    max-height: none;
}
.route-journey-panel {
    flex: 0 0 auto;
    background: linear-gradient(180deg, #fff, #fbf8fc);
    border: 1px solid rgba(130, 70, 111, 0.16);
    border-radius: 18px;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.07);
    padding: 10px 14px 12px;
    overflow: visible;
}
.route-journey-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}
.route-journey-title {
    margin: 0;
    font-size: 14px;
    line-height: 1.15;
    font-weight: 950;
    color: var(--route-title);
}
.route-journey-subtitle {
    display: none;
}
.route-journey-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    justify-content: flex-end;
}
.route-journey-stat {
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    padding: 4px 8px;
    background: #f8fafc;
    color: #334155;
    font-size: 11px;
    line-height: 1.1;
    font-weight: 950;
    white-space: nowrap;
}
.route-journey-stat.done { background: #dcfce7; color: #15803d; }
.route-journey-stat.active { background: #ffedd5; color: #c2410c; }
.route-journey-stat.pending { background: #cffafe; color: #0e7490; }
.route-journey-stat.outside { background: #fee2e2; color: #b91c1c; }
.route-journey-track {
    --journey-node-size: 40px;
    --journey-line-top: 22px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
    gap: 12px 8px;
    align-items: start;
    padding: 6px 8px 2px;
    overflow: visible;
}
.route-journey-step {
    position: relative;
    z-index: 2;
    min-width: 0;
    width: 100%%;
    text-align: center;
    text-decoration: none;
    color: inherit;
    display: block;
    padding: 2px 0 0;
    border: 0;
    background: transparent;
    font: inherit;
    cursor: pointer;
    appearance: none;
}
.route-journey-step::before,
.route-journey-step::after {
    content: "";
    position: absolute;
    z-index: 0;
    top: var(--journey-line-top);
    height: 5px;
    transform: translateY(-50%%);
    border-radius: 999px;
    background: var(--journey-connector-color, #d1d5db);
}
.route-journey-step::before {
    left: 0;
    width: calc(50%% - (var(--journey-node-size) / 2) + 5px);
}
.route-journey-step::after {
    right: 0;
    width: calc(50%% - (var(--journey-node-size) / 2) + 5px);
}
.route-journey-step:first-child::before {
    display: none;
}
.route-journey-step.done,
.route-journey-step.ready {
    --journey-connector-color: #111827;
}
.route-journey-step.pending,
.route-journey-step.active,
.route-journey-step.cancelled,
.route-journey-step.current {
    --journey-connector-color: #d1d5db;
}
.route-journey-path-layer,
.route-journey-segment,
.route-journey-truck {
    display: none !important;
}
.route-journey-node {
    position: relative;
    z-index: 2;
    width: var(--journey-node-size);
    height: var(--journey-node-size);
    margin: 0 auto 5px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 13px;
    font-weight: 950;
    background: var(--route-pending);
    border: 4px solid #fff;
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.20);
    transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.route-journey-step.done .route-journey-node { background: var(--route-green); }
.route-journey-step.ready .route-journey-node { background: var(--route-ready); }
.route-journey-step.active .route-journey-node { background: var(--route-active); }
.route-journey-step.pending .route-journey-node { background: var(--route-pending); }
.route-journey-step.cancelled .route-journey-node { background: var(--route-cancelled); }
.route-journey-step.outside-zone .route-journey-node {
    border-color: var(--route-outside);
    box-shadow: 0 0 0 5px rgba(239, 68, 68, 0.18), 0 10px 22px rgba(15, 23, 42, 0.20);
}
.route-journey-step.current .route-journey-node {
    transform: scale(1.12);
    border-color: #fef08a;
    animation: routeCurrentPulse 1.8s ease-out infinite;
}
.route-journey-step:focus-visible .route-journey-node,
.route-journey-step.route-journey-focused .route-journey-node {
    transform: scale(1.12);
    border-color: #fef08a;
    box-shadow: 0 0 0 7px rgba(130, 70, 111, 0.18), 0 12px 24px rgba(15, 23, 42, 0.24);
}
.route-journey-step.current .route-journey-node::after {
    content: "➜";
    position: absolute;
    z-index: 3;
    top: 50%%;
    left: -27px;
    width: 22px;
    height: 22px;
    transform: translateY(-50%%);
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #fff7ed;
    color: #c2410c;
    border: 2px solid #fed7aa;
    box-shadow: 0 6px 14px rgba(15, 23, 42, 0.16);
    font-size: 13px;
    font-weight: 950;
    line-height: 1;
    pointer-events: none;
}
.route-journey-label {
    font-size: 11px;
    font-weight: 950;
    line-height: 1.15;
    color: var(--route-title);
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    min-height: 13px;
}
.route-journey-status {
    margin-top: 3px;
    color: var(--route-muted);
    font-size: 10px;
    line-height: 1.1;
    font-weight: 850;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.route-marker.ready { background: var(--route-ready); }
.route-marker.cancelled { background: var(--route-cancelled); }
.route-marker.outside-zone { border-color: var(--route-outside); box-shadow: 0 0 0 5px rgba(239, 68, 68, 0.18), 0 8px 18px rgba(15, 23, 42, 0.30); }
.route-marker.no-checkin { border-color: #cbd5e1; }
@media (max-width: 767px) {
    html, body {
        width: 100%%;
        min-height: 100vh;
        min-height: 100dvh;
        overflow-x: hidden;
        overflow-y: auto;
    }
    body { padding: 0; background: #fff; }
    .route-frame.route-split-layout {
        display: flex;
        flex-direction: column;
        gap: 0;
        width: 100%%;
        height: auto;
        max-height: none;
        min-height: 0;
        overflow: visible;
    }
    .route-frame.route-split-layout .route-map-panel {
        flex: 0 0 auto;
        height: 56vh;
        height: 56dvh;
        min-height: 320px;
        max-height: 62vh;
        max-height: 62dvh;
        border-radius: 0;
        border-left: 0;
        border-right: 0;
        box-shadow: none;
        position: sticky;
        top: 0;
        z-index: 3;
    }
    .route-frame.route-split-layout #map {
        height: 100%%;
        min-height: 0;
    }
    .route-frame.route-split-layout .route-cards-panel.route-side-cards {
        flex: 0 0 auto;
        min-height: 0;
        height: auto;
        border-radius: 0;
        border-left: 0;
        border-right: 0;
        box-shadow: none;
        overflow: visible;
    }
    .route-frame.route-split-layout .route-cards-panel.route-side-cards .route-cards-header {
        display: none;
    }
    .route-map-floating-badge { top: 10px; right: 10px; }
    .route-map-header, .route-cards-header { padding: 10px 12px; align-items: flex-start; flex-direction: column; }
    .route-frame.route-split-layout .route-cards-panel.route-side-cards .route-cards-grid {
        display: block;
        padding: 10px;
        height: auto;
        overflow: visible;
        -webkit-overflow-scrolling: touch;
        overscroll-behavior: auto;
        touch-action: pan-y;
    }
    .route-frame.route-split-layout .route-cards-panel.route-side-cards .route-card {
        margin-bottom: 10px;
    }
    .route-card-head { padding: 12px; }
    .route-card-title { font-size: 16px; }
    .route-card-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
    .route-metric { padding: 8px; min-height: 54px; }
    .route-actions .route-btn { flex: 1 1 46%%; }
    .route-map-shell {
        width: 100%%;
        height: auto;
        max-height: none;
        min-height: 0;
        gap: 0;
        overflow: visible;
    }
    .route-map-shell > .route-frame.route-split-layout {
        flex: 1 1 auto;
        min-height: 0;
        height: auto;
        max-height: none;
    }
    .route-map-shell > .route-frame.route-split-layout .route-map-panel {
        flex: 0 0 auto;
        height: 56vh;
        height: 56dvh;
        min-height: 320px;
        max-height: 62vh;
        max-height: 62dvh;
    }
    .route-map-shell > .route-frame.route-split-layout .route-cards-panel.route-side-cards {
        flex: 1 1 auto;
        height: auto;
    }
    .route-journey-panel {
        border-radius: 0;
        border-left: 0;
        border-right: 0;
        padding: 8px 8px 9px;
        box-shadow: none;
        max-height: none;
        overflow: visible;
    }
    .route-journey-head {
        margin-bottom: 4px;
        gap: 6px;
    }
    .route-journey-title {
        display: none;
    }
    .route-journey-stats {
        justify-content: flex-start;
        gap: 4px;
        overflow-x: auto;
        flex-wrap: nowrap;
        padding-bottom: 2px;
        -webkit-overflow-scrolling: touch;
    }
    .route-journey-stat {
        font-size: 10px;
        padding: 3px 7px;
    }
    .route-journey-track {
        --journey-node-size: 34px;
        --journey-line-top: 18px;
        display: grid;
        grid-auto-flow: column;
        grid-auto-columns: minmax(78px, 88px);
        grid-template-columns: none;
        gap: 10px 5px;
        padding: 5px 2px 1px;
        overflow-x: auto;
        overflow-y: hidden;
        overscroll-behavior-x: contain;
        -webkit-overflow-scrolling: touch;
    }
    .route-journey-node { font-size: 11px; border-width: 3px; }
    .route-journey-step::before { height: 4px; }
    .route-journey-label { font-size: 10px; min-height: 12px; }
    .route-journey-status { font-size: 9px; }
}
</style>
</head>
<body>
""" % {"title": escape(title or "Route Map")}

    def _route_journey_html(self, visits_payload, title, subtitle):
        visits_payload = visits_payload or []
        total = len(visits_payload)
        done_count = sum(1 for visit in visits_payload if visit.get("statusClass") == "done")
        active_count = sum(1 for visit in visits_payload if visit.get("statusClass") in ("active", "ready"))
        pending_count = sum(1 for visit in visits_payload if visit.get("statusClass") == "pending")
        outside_count = sum(1 for visit in visits_payload if visit.get("geoStatus") in ("outside", "outside_no_reason", "outside_with_reason"))
        current_visit = next(
            (visit for visit in visits_payload if visit.get("statusClass") not in ("done", "cancelled")),
            False,
        )
        current_id = current_visit.get("id") if current_visit else False
        stat_html = "".join(
            [
                '<span class="route-journey-stat">%s Stops</span>' % self._html_escape(total),
                '<span class="route-journey-stat done">%s Done</span>' % self._html_escape(done_count),
                '<span class="route-journey-stat active">%s Active</span>' % self._html_escape(active_count),
                '<span class="route-journey-stat pending">%s Pending</span>' % self._html_escape(pending_count),
                '<span class="route-journey-stat outside">%s Outside</span>' % self._html_escape(outside_count) if outside_count else "",
            ]
        )
        steps = []
        for visit in visits_payload:
            state_class = self._html_escape(visit.get("statusClass") or visit.get("bucket") or "pending")
            geo_status = self._safe_text(visit.get("geoStatus") or "")
            extra_classes = []
            if visit.get("id") == current_id:
                extra_classes.append("current")
            if geo_status in ("outside", "outside_no_reason", "outside_with_reason"):
                extra_classes.append("outside-zone")
            if geo_status in ("pending", "pending_checkin"):
                extra_classes.append("no-checkin")
            class_text = " ".join([state_class] + extra_classes)
            outlet_name = self._safe_text(visit.get("outlet") or "No outlet")
            status_label = self._safe_text(visit.get("statusLabel") or visit.get("status") or "Pending")
            steps.append(
                '<button type="button" class="route-journey-step %(classes)s" data-visit-id="%(id)s" title="%(title)s">'
                '<span class="route-journey-node">%(index)s</span>'
                '<span class="route-journey-label">%(outlet)s</span>'
                '<span class="route-journey-status">%(status)s</span>'
                '</button>'
                % {
                    "classes": class_text,
                    "id": self._html_escape(visit.get("id") or "", quote=True),
                    "title": self._html_escape("%s - %s" % (outlet_name, status_label), quote=True),
                    "index": self._html_escape(visit.get("index") or ""),
                    "outlet": self._html_escape(outlet_name),
                    "status": self._html_escape(status_label),
                }
            )
        track = "".join(steps) or '<div class="route-map-empty" style="display:block; padding:10px;">No visits found for today.</div>'
        return (
            '<section class="route-journey-panel">'
            '<div class="route-journey-head">'
            '<div><h2 class="route-journey-title">%s</h2><div class="route-journey-subtitle">%s</div></div>'
            '<div class="route-journey-stats">%s</div>'
            '</div>'
            '<div class="route-journey-track">%s</div>'
            '</section>'
        ) % (self._html_escape(title), self._html_escape(subtitle), stat_html, track)

    def _render_salesperson_map_html(self, route_map, visits_payload):
        data_json = json.dumps(visits_payload, ensure_ascii=False)
        cards_html = []
        for visit in visits_payload:
            badges = "".join(
                '<span class="route-badge %s">%s</span>' % (escape(badge.get("style", "")), escape(badge.get("label", "")))
                for badge in visit.get("badges", [])
            )
            map_link = visit.get("navigationUrl") or visit.get("outletMapUrl") or "#"
            cards_html.append(
                """
<div class="route-card %(status_class)s %(geo_class)s" data-visit-id="%(id)s">
    <div class="route-card-head">
        <div style="display:flex; gap:10px; align-items:flex-start; min-width:0;">
            <span class="route-card-index %(status_class)s %(geo_class)s">%(index)s</span>
            <div style="min-width:0;">
                <div class="route-card-title">%(outlet)s</div>
                <div class="route-card-ref">%(name)s · %(date)s</div>
            </div>
        </div>
        <div class="route-badges">%(badges)s</div>
    </div>
    <div class="route-card-body">
        <div class="route-card-metrics">
            <div class="route-metric"><div class="route-metric-label">Mode</div><div class="route-metric-value">%(mode)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Area</div><div class="route-metric-value">%(area)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Due Now</div><div class="route-metric-value">%(due_now)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Remaining</div><div class="route-metric-value">%(remaining)s</div></div>
            <div class="route-metric" style="grid-column:1/-1;"><div class="route-metric-label">Current Step</div><div class="route-metric-value">%(current_step)s</div></div>
        </div>
        <div class="route-actions">
            <a class="route-btn primary" href="%(openUrl)s" target="_top">%(open_label)s</a>
            <a class="route-btn" href="%(mapUrl)s" target="_blank" rel="noopener">Navigate</a>
        </div>
    </div>
</div>
""" % {
                    "id": visit["id"],
                    "status_class": escape(visit.get("statusClass") or visit.get("bucket") or "pending"),
                    "geo_class": "outside-zone" if visit.get("geoStatus") in ("outside", "outside_no_reason", "outside_with_reason") else "",
                    "index": visit["index"],
                    "outlet": escape(visit.get("outlet") or "No outlet"),
                    "name": escape(visit.get("name") or ""),
                    "date": escape(visit.get("date") or ""),
                    "badges": badges,
                    "mode": escape(visit.get("mode") or ""),
                    "area": escape(visit.get("area") or ""),
                    "due_now": escape(visit.get("due_now") or "0.00"),
                    "remaining": escape(visit.get("remaining") or "0.00"),
                    "current_step": escape(visit.get("current_step") or ""),
                    "openUrl": escape(visit.get("openUrl") or "#", quote=True),
                    "open_label": "View Visit Summary" if visit.get("bucket") == "done" else "Open Visit",
                    "mapUrl": escape(map_link, quote=True),
                }
            )
        cards_block = "".join(cards_html) or '<div class="route-map-empty" style="display:block;">No visits found for today.</div>'
        try:
            journey_block = self._route_journey_html(
                visits_payload,
                _("Daily Visit Progress"),
                _("Quick route journey: completed stops, active stop, pending stops, and location exceptions."),
            )
        except Exception:
            journey_block = ""
        return self._base_head("Today's Route Map") + """
<div class="route-map-shell">
%(journey)s
<div class="route-frame route-split-layout">
    <section class="route-map-panel route-fixed-map">
        <div class="route-map-floating-badge">%(count)s Visits</div>
        <div id="map"></div>
        <div id="emptyMap" class="route-map-empty">No outlet location points are available for these visits.</div>
    </section>
    <section class="route-cards-panel route-side-cards">
        <div class="route-cards-header">
            <h2 class="route-cards-title">Visit Cards</h2>
            <div class="route-map-subtitle">Open the next visit, review completed visits, or navigate to the outlet.</div>
        </div>
        <div class="route-cards-grid">%(cards)s</div>
    </section>
</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const visits = %(data_json)s;
function esc(value) {
    return String(value || '').replace(/[&<>"']/g, function (char) {
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char];
    });
}
function markerClass(visit) {
    const classes = [visit.statusClass || visit.bucket || 'pending'];
    if (['outside', 'outside_no_reason', 'outside_with_reason'].includes(visit.geoStatus || '')) classes.push('outside-zone');
    if (['pending', 'pending_checkin'].includes(visit.geoStatus || '')) classes.push('no-checkin');
    return classes.join(' ');
}
function popupHtml(visit) {
    const mapLink = visit.navigationUrl || visit.outletMapUrl || '#';
    return `<div class="route-popup-title">${esc(visit.outlet)}</div>
        <div class="route-popup-ref">${esc(visit.name)} · ${esc(visit.date)}</div>
        <div><strong>Step:</strong> ${esc(visit.current_step || visit.status)}</div>
        <div><strong>Due:</strong> ${esc(visit.due_now)}</div>
        <div class="route-popup-actions">
            <a class="route-btn primary" target="_top" href="${esc(visit.openUrl)}">${visit.bucket === 'done' ? 'Summary' : 'Open Visit'}</a>
            <a class="route-btn" target="_blank" rel="noopener" href="${esc(mapLink)}">Navigate</a>
        </div>`;
}
let mapInstance = null;
const routeMarkers = {};
function markerHtml(visit, focused=false) {
    return `<div class="route-marker ${markerClass(visit)} ${focused ? 'route-marker-focus' : ''}"><span>${visit.index}</span></div>`;
}
function markerIcon(visit, focused=false) {
    const size = focused ? 48 : 36;
    const anchorX = Math.round(size / 2);
    const anchorY = Math.max(size - 2, anchorX);
    return L.divIcon({
        className: '',
        html: markerHtml(visit, focused),
        iconSize: [size, size],
        iconAnchor: [anchorX, anchorY]
    });
}
function currentRouteVisit() {
    return visits.find(visit => !['done', 'cancelled'].includes(visit.statusClass || visit.bucket || 'pending')) || visits[0] || null;
}
function scrollVisitCardIntoView(visitId) {
    const card = document.querySelector(`.route-card[data-visit-id="${String(visitId)}"]`);
    if (card) card.scrollIntoView({behavior: 'smooth', block: 'nearest', inline: 'nearest'});
}
function setActiveJourneyStep(visitId) {
    document.querySelectorAll('.route-journey-step[data-visit-id]').forEach(step => {
        step.classList.toggle('route-journey-focused', String(step.dataset.visitId) === String(visitId));
    });
}
function setRouteCardsActive(visitId, highlightCard=true) {
    document.querySelectorAll('.route-card').forEach(card => {
        if (!highlightCard) {
            card.classList.remove('route-card-active');
            return;
        }
        card.classList.toggle('route-card-active', String(card.dataset.visitId) === String(visitId));
    });
}
function setActiveVisit(visitId, panToMarker=false, openPopup=false, scrollCard=false, highlightCard=true) {
    visits.forEach(visit => {
        const isActive = String(visit.id) === String(visitId);
        const marker = routeMarkers[visit.id];
        if (marker) {
            marker.setIcon(markerIcon(visit, isActive));
            marker.setZIndexOffset(isActive ? 10000 : (visit.index || 1));
            if (isActive && panToMarker && mapInstance) {
                mapInstance.invalidateSize();
                mapInstance.panTo([visit.lat, visit.lng], {animate: true, duration: .35});
            }
            if (isActive && openPopup) marker.openPopup();
        }
    });
    setRouteCardsActive(visitId, highlightCard);
    setActiveJourneyStep(visitId);
    if (scrollCard) scrollVisitCardIntoView(visitId);
}
function installJourneyFocus() {
    document.querySelectorAll('.route-journey-step[data-visit-id]').forEach(step => {
        step.addEventListener('click', event => {
            event.preventDefault();
            const visitId = step.dataset.visitId;
            if (visitId) {
                setActiveVisit(visitId, true, true, false, false);
                window.setTimeout(() => setActiveVisit(visitId, true, true, false, false), 260);
            }
        });
    });
}
function installCardFocus() {
    const cards = Array.from(document.querySelectorAll('.route-card[data-visit-id]'));
    let currentId = null;
    function activateCard(visitId, panToMarker=false) {
        if (!visitId || String(visitId) === String(currentId)) return;
        currentId = visitId;
        setActiveVisit(visitId, panToMarker, false, false, true);
    }
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => activateCard(card.dataset.visitId, true));
        card.addEventListener('focusin', () => activateCard(card.dataset.visitId, true));
        card.addEventListener('click', event => {
            if (!event.target.closest('a')) activateCard(card.dataset.visitId, true);
        });
    });
    window.setTimeout(() => {
        const initialVisit = currentRouteVisit();
        if (initialVisit) setActiveVisit(initialVisit.id, false, false, false, false);
    }, 300);
}
function renderMap() {
    const points = visits.filter(v => v.hasPoint);
    if (!points.length || typeof L === 'undefined') {
        document.getElementById('map').style.display = 'none';
        document.getElementById('emptyMap').style.display = 'block';
        return;
    }
    mapInstance = L.map('map', { scrollWheelZoom: false });
    const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    });
    const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: 'Tiles &copy; Esri'
    });
    streetLayer.addTo(mapInstance);
    L.control.layers(
        {'Street Map': streetLayer, 'Satellite': satelliteLayer},
        {},
        {collapsed: false, position: 'topright'}
    ).addTo(mapInstance);
    const bounds = [];
    points.forEach(visit => {
        const latLng = [visit.lat, visit.lng];
        bounds.push(latLng);
        const marker = L.marker(latLng, { icon: markerIcon(visit, false), zIndexOffset: visit.index }).addTo(mapInstance).bindPopup(popupHtml(visit));
        marker.on('click', () => setActiveVisit(visit.id, false));
        routeMarkers[visit.id] = marker;
    });
    if (bounds.length === 1) {
        mapInstance.setView(bounds[0], 15);
    } else {
        mapInstance.fitBounds(bounds, { padding: [34, 34] });
    }
    window.setTimeout(() => mapInstance.invalidateSize(), 120);
    window.setTimeout(() => mapInstance.invalidateSize(), 500);
    window.addEventListener('resize', () => window.setTimeout(() => mapInstance.invalidateSize(), 120));
    const initialVisit = currentRouteVisit();
    if (initialVisit && initialVisit.hasPoint) {
        window.setTimeout(() => setActiveVisit(initialVisit.id, false, false, false), 250);
    }
}
renderMap();
installCardFocus();
installJourneyFocus();
</script>
</body>
</html>
""" % {
            "count": len(visits_payload),
            "cards": cards_block,
            "journey": journey_block,
            "data_json": data_json,
        }

    def _render_geo_map_html(self, center, visits_payload):
        data_json = json.dumps(visits_payload, ensure_ascii=False)
        cards_html = []
        for visit in visits_payload:
            badges = "".join(
                '<span class="route-badge %s">%s</span>' % (escape(badge.get("style", "")), escape(badge.get("label", "")))
                for badge in visit.get("badges", [])
            )
            action_buttons = []
            if visit.get("decision") == "accepted":
                action_buttons.append('<button class="route-btn warning review-action" data-url="/route_core/geo/live_map/review/%s/needs_correction">Needs Correction</button>' % visit["id"])
                action_buttons.append('<button class="route-btn review-action" data-url="/route_core/geo/live_map/review/%s/reset">Reset</button>' % visit["id"])
            elif visit.get("decision") == "needs_correction":
                action_buttons.append('<button class="route-btn success review-action" data-url="/route_core/geo/live_map/review/%s/accepted">Accept</button>' % visit["id"])
                action_buttons.append('<button class="route-btn review-action" data-url="/route_core/geo/live_map/review/%s/reset">Reset</button>' % visit["id"])
            elif visit.get("reviewRequired"):
                action_buttons.append('<button class="route-btn success review-action" data-url="/route_core/geo/live_map/review/%s/accepted">Accept</button>' % visit["id"])
                action_buttons.append('<button class="route-btn warning review-action" data-url="/route_core/geo/live_map/review/%s/needs_correction">Needs Correction</button>' % visit["id"])
            checkin_link = visit.get("checkinMapUrl") or "#"
            outlet_link = visit.get("outletMapUrl") or "#"
            cards_html.append(
                """
<div class="route-card %(status_class)s %(geo_class)s" data-visit-id="%(id)s">
    <div class="route-card-head">
        <div style="display:flex; gap:10px; align-items:flex-start; min-width:0;">
            <span class="route-card-index %(status_class)s %(geo_class)s">%(index)s</span>
            <div style="min-width:0;">
                <div class="route-card-title">%(outlet)s</div>
                <div class="route-card-ref">%(name)s · %(date)s</div>
            </div>
        </div>
        <div class="route-badges">%(badges)s</div>
    </div>
    <div class="route-card-body">
        <div class="route-card-metrics">
            <div class="route-metric"><div class="route-metric-label">Salesperson</div><div class="route-metric-value">%(salesperson)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Vehicle</div><div class="route-metric-value">%(vehicle)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Area</div><div class="route-metric-value">%(area)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Distance</div><div class="route-metric-value">%(distance)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Check-in</div><div class="route-metric-value">%(checkinTime)s</div></div>
            <div class="route-metric"><div class="route-metric-label">Accuracy</div><div class="route-metric-value">%(accuracy)s m</div></div>
        </div>
        %(reason)s
        <div class="route-actions">
            <a class="route-btn primary" href="%(openUrl)s" target="_top">Open Visit</a>
            <a class="route-btn" href="%(outletMapUrl)s" target="_blank" rel="noopener">Outlet Map</a>
            <a class="route-btn" href="%(checkinMapUrl)s" target="_blank" rel="noopener">Check-in Map</a>
            %(actions)s
        </div>
    </div>
</div>
""" % {
                    "id": visit["id"],
                    "status_class": escape(visit.get("statusClass") or visit.get("bucket") or "pending"),
                    "geo_class": "outside-zone" if visit.get("geoStatus") in ("outside", "outside_no_reason", "outside_with_reason") else "",
                    "index": visit["index"],
                    "outlet": escape(visit.get("outlet") or "No outlet"),
                    "name": escape(visit.get("name") or ""),
                    "date": escape(visit.get("date") or ""),
                    "badges": badges,
                    "salesperson": escape(visit.get("salesperson") or ""),
                    "vehicle": escape(visit.get("vehicle") or ""),
                    "area": escape(visit.get("area") or ""),
                    "distance": escape(visit.get("distance") or ""),
                    "checkinTime": escape(visit.get("checkinTime") or ""),
                    "accuracy": escape(visit.get("accuracy") or "0"),
                    "reason": '<div class="route-card-note"><strong>Reason:</strong> %s</div>' % escape(visit.get("reason") or "") if visit.get("reason") else "",
                    "openUrl": escape(visit.get("openUrl") or "#", quote=True),
                    "outletMapUrl": escape(outlet_link, quote=True),
                    "checkinMapUrl": escape(checkin_link, quote=True),
                    "actions": "".join(action_buttons),
                }
            )
        cards_block = "".join(cards_html) or '<div class="route-map-empty" style="display:block;">No visits match the current filters.</div>'
        try:
            journey_block = self._route_journey_html(
                visits_payload,
                _("Filtered Route Progress"),
                _("Supervisor route journey for the current filtered visits with location status highlights."),
            )
        except Exception:
            journey_block = ""
        return self._base_head("Visit Location Map") + """
<div class="route-map-shell">
%(journey)s
<div class="route-frame route-split-layout">
    <section class="route-map-panel route-fixed-map">
        <div class="route-map-floating-badge">%(count)s Visits</div>
        <div id="map"></div>
        <div id="emptyMap" class="route-map-empty">No outlet or check-in location points are available for these visits.</div>
    </section>
    <section class="route-cards-panel route-side-cards">
        <div class="route-cards-header">
            <h2 class="route-cards-title">Visit Location Cards</h2>
        </div>
        <div id="statusMessage" class="route-status-message"></div>
        <div class="route-cards-grid">%(cards)s</div>
    </section>
</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const visits = %(data_json)s;
function esc(value) {
    return String(value || '').replace(/[&<>"']/g, function (char) {
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char];
    });
}
function showMessage(message) {
    const box = document.getElementById('statusMessage');
    box.textContent = message || '';
    box.style.display = message ? 'block' : 'none';
}
function popupActions(visit) {
    let html = `<a class="route-btn primary" target="_top" href="${esc(visit.openUrl)}">Open Visit</a>`;
    if (visit.outletMapUrl) html += `<a class="route-btn" target="_blank" rel="noopener" href="${esc(visit.outletMapUrl)}">Outlet Map</a>`;
    if (visit.checkinMapUrl) html += `<a class="route-btn" target="_blank" rel="noopener" href="${esc(visit.checkinMapUrl)}">Check-in Map</a>`;
    return html;
}
function popupHtml(visit, pointType) {
    return `<div class="route-popup-title">${esc(visit.outlet)}</div>
        <div class="route-popup-ref">${esc(visit.name)} · ${esc(pointType)}</div>
        <div><strong>Salesperson:</strong> ${esc(visit.salesperson)}</div>
        <div><strong>Distance:</strong> ${esc(visit.distance)}</div>
        <div><strong>Review:</strong> ${esc(visit.reviewState)}</div>
        <div class="route-popup-actions">${popupActions(visit)}</div>`;
}
let mapInstance = null;
const visitMarkers = {};
function markerIcon(visit, pointType, focused=false) {
    const size = focused ? 48 : 36;
    const anchorX = Math.round(size / 2);
    const anchorY = Math.max(size - 2, anchorX);
    return L.divIcon({
        className: '',
        html: `<div class="route-marker ${pointType} ${visit.statusClass || visit.bucket || 'pending'} ${['outside', 'outside_no_reason', 'outside_with_reason'].includes(visit.geoStatus || '') ? 'outside-zone' : ''} ${focused ? 'route-marker-focus' : ''}"><span>${visit.index}</span></div>`,
        iconSize: [size, size],
        iconAnchor: [anchorX, anchorY]
    });
}
function addVisitMarker(map, visit, point, pointType, popupLabel) {
    const marker = L.marker(point, {
        icon: markerIcon(visit, pointType, false),
        zIndexOffset: visit.index || 1
    }).addTo(map).bindPopup(popupHtml(visit, popupLabel));
    marker._routePointType = pointType;
    marker._routePoint = point;
    marker.on('click', () => setActiveVisit(visit.id, false));
    if (!visitMarkers[visit.id]) visitMarkers[visit.id] = [];
    visitMarkers[visit.id].push(marker);
    return marker;
}
function preferredPoint(visit) {
    if (visit.hasCheckinPoint) return [visit.checkinLat, visit.checkinLng];
    if (visit.hasOutletPoint) return [visit.outletLat, visit.outletLng];
    return null;
}
function currentRouteVisit() {
    return visits.find(visit => !['done', 'cancelled'].includes(visit.statusClass || visit.bucket || 'pending')) || visits[0] || null;
}
function scrollVisitCardIntoView(visitId) {
    const card = document.querySelector(`.route-card[data-visit-id="${String(visitId)}"]`);
    if (card) card.scrollIntoView({behavior: 'smooth', block: 'nearest', inline: 'nearest'});
}
function setActiveJourneyStep(visitId) {
    document.querySelectorAll('.route-journey-step[data-visit-id]').forEach(step => {
        step.classList.toggle('route-journey-focused', String(step.dataset.visitId) === String(visitId));
    });
}
function setRouteCardsActive(visitId, highlightCard=true) {
    document.querySelectorAll('.route-card').forEach(card => {
        if (!highlightCard) {
            card.classList.remove('route-card-active');
            return;
        }
        card.classList.toggle('route-card-active', String(card.dataset.visitId) === String(visitId));
    });
}
function setActiveVisit(visitId, panToMarker=false, openPopup=false, scrollCard=false, highlightCard=true) {
    visits.forEach(visit => {
        const isActive = String(visit.id) === String(visitId);
        const markers = visitMarkers[visit.id] || [];
        markers.forEach(marker => {
            marker.setIcon(markerIcon(visit, marker._routePointType || 'outlet', isActive));
            marker.setZIndexOffset(isActive ? 10000 : (visit.index || 1));
            if (isActive && openPopup) marker.openPopup();
        });
        if (isActive && panToMarker && mapInstance) {
            const point = preferredPoint(visit);
            if (point) {
                mapInstance.invalidateSize();
                mapInstance.panTo(point, {animate: true, duration: .35});
            }
        }
    });
    setRouteCardsActive(visitId, highlightCard);
    setActiveJourneyStep(visitId);
    if (scrollCard) scrollVisitCardIntoView(visitId);
}
function installJourneyFocus() {
    document.querySelectorAll('.route-journey-step[data-visit-id]').forEach(step => {
        step.addEventListener('click', event => {
            event.preventDefault();
            const visitId = step.dataset.visitId;
            if (visitId) {
                setActiveVisit(visitId, true, true, false, false);
                window.setTimeout(() => setActiveVisit(visitId, true, true, false, false), 260);
            }
        });
    });
}
function installCardFocus() {
    const cards = Array.from(document.querySelectorAll('.route-card[data-visit-id]'));
    let currentId = null;
    function activateCard(visitId, panToMarker=false) {
        if (!visitId || String(visitId) === String(currentId)) return;
        currentId = visitId;
        setActiveVisit(visitId, panToMarker, false, false, true);
    }
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => activateCard(card.dataset.visitId, true));
        card.addEventListener('focusin', () => activateCard(card.dataset.visitId, true));
        card.addEventListener('click', event => {
            if (!event.target.closest('a')) activateCard(card.dataset.visitId, true);
        });
    });
    window.setTimeout(() => {
        const initialVisit = currentRouteVisit();
        if (initialVisit) setActiveVisit(initialVisit.id, false, false, false, false);
    }, 300);
}

function renderMap() {
    const hasAnyPoint = visits.some(v => v.hasOutletPoint || v.hasCheckinPoint);
    if (!hasAnyPoint || typeof L === 'undefined') {
        document.getElementById('map').style.display = 'none';
        document.getElementById('emptyMap').style.display = 'block';
        return;
    }
    mapInstance = L.map('map', { scrollWheelZoom: false });
    const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    });
    const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: 'Tiles &copy; Esri'
    });
    streetLayer.addTo(mapInstance);
    L.control.layers(
        {'Street Map': streetLayer, 'Satellite': satelliteLayer},
        {},
        {collapsed: false, position: 'topright'}
    ).addTo(mapInstance);
    const bounds = [];
    visits.forEach(visit => {
        if (visit.hasOutletPoint) {
            const outletPoint = [visit.outletLat, visit.outletLng];
            bounds.push(outletPoint);
            addVisitMarker(mapInstance, visit, outletPoint, 'outlet', 'Outlet');
        }
        if (visit.hasCheckinPoint) {
            const checkPoint = [visit.checkinLat, visit.checkinLng];
            bounds.push(checkPoint);
            addVisitMarker(mapInstance, visit, checkPoint, 'checkin', 'Check-in');
        }
        if (visit.hasOutletPoint && visit.hasCheckinPoint && visit.distance) {
            L.polyline([[visit.outletLat, visit.outletLng], [visit.checkinLat, visit.checkinLng]], {
                color: '#82466f', weight: 3, opacity: 0.65, dashArray: '7 7'
            }).addTo(mapInstance);
        }
    });
    if (bounds.length === 1) {
        mapInstance.setView(bounds[0], 15);
    } else {
        mapInstance.fitBounds(bounds, { padding: [30, 30] });
    }
    window.setTimeout(() => mapInstance.invalidateSize(), 120);
    window.setTimeout(() => mapInstance.invalidateSize(), 500);
    window.addEventListener('resize', () => window.setTimeout(() => mapInstance.invalidateSize(), 120));
    const initialVisit = currentRouteVisit();
    if (initialVisit && (initialVisit.hasCheckinPoint || initialVisit.hasOutletPoint)) {
        window.setTimeout(() => setActiveVisit(initialVisit.id, false, false, false), 250);
    }
}
async function sendReviewAction(url) {
    showMessage('Saving location review decision...');
    try {
        const response = await fetch(url, {method: 'POST', credentials: 'include'});
        const data = await response.json();
        if (!response.ok || !data.ok) {
            showMessage(data.message || 'Could not update the location review decision.');
            return;
        }
        showMessage(data.message || 'Location review updated.');
        window.setTimeout(() => window.location.reload(), 650);
    } catch (error) {
        showMessage('Could not update the location review decision. Please refresh and try again.');
    }
}
document.querySelectorAll('.review-action').forEach(button => {
    button.addEventListener('click', function () {
        const url = this.getAttribute('data-url');
        if (url) sendReviewAction(url);
    });
});
renderMap();
installCardFocus();
installJourneyFocus();
</script>
</body>
</html>
""" % {
            "count": len(visits_payload),
            "cards": cards_block,
            "journey": journey_block,
            "data_json": data_json,
        }

    # -------------------------------------------------------------------------
    # Public iframe routes
    # -------------------------------------------------------------------------
    @http.route("/route_core/pda/today_route_map/frame/<int:route_map_id>", type="http", auth="user", website=False)
    def route_today_route_map_frame(self, route_map_id, **kwargs):
        route_map = request.env["route.salesperson.route.map"].browse(route_map_id).exists()
        if not route_map:
            return self._html_response("<html><body><p>Route map not found. Please refresh Today's Route Map.</p></body></html>", status=404)
        visits = request.env["route.visit"].search(route_map._get_visit_domain(), order="date asc, id asc")
        payload = [self._salesperson_visit_payload(visit, index) for index, visit in enumerate(visits, start=1)]
        return self._html_response(self._render_salesperson_map_html(route_map, payload))

    @http.route("/route_core/geo/live_map/frame/<int:center_id>", type="http", auth="user", website=False)
    def route_geo_live_map_frame(self, center_id, **kwargs):
        center = request.env["route.geo.control.center"].browse(center_id).exists()
        if not center:
            return self._html_response("<html><body><p>Visit Location Map not found. Please refresh the page.</p></body></html>", status=404)
        visits = request.env["route.visit"].search(center._get_filtered_visit_domain(), order="date desc, geo_checkin_datetime desc, id desc")
        payload = [self._geo_visit_payload(visit, index) for index, visit in enumerate(visits, start=1)]
        return self._html_response(self._render_geo_map_html(center, payload))

    @http.route("/route_core/geo/live_map/review/<int:visit_id>/<string:decision>", type="http", auth="user", methods=["POST"], csrf=False, website=False)
    def route_geo_live_map_review_action(self, visit_id, decision, **kwargs):
        visit = request.env["route.visit"].browse(visit_id).exists()
        if not visit:
            return self._json_response({"ok": False, "message": "Visit not found."}, status=404)
        try:
            if decision == "accepted":
                visit.action_geo_review_accept()
                message = "Location review accepted."
            elif decision == "needs_correction":
                visit.action_geo_review_needs_correction()
                message = "Location review marked as needs correction."
            elif decision == "reset":
                visit.action_geo_review_reset_decision()
                message = "Location review decision reset."
            else:
                return self._json_response({"ok": False, "message": "Unsupported location review action."}, status=400)
        except Exception as error:
            return self._json_response({"ok": False, "message": self._safe_text(error)}, status=400)
        return self._json_response({"ok": True, "message": message})

