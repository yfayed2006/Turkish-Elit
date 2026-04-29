import json
import time
from html import escape
from urllib.parse import quote_plus

from werkzeug.utils import redirect

from odoo import fields, http
from odoo.http import request


class RoutePdaRedirectController(http.Controller):
    def _build_web_redirect(self, *, model, record_id, view_xmlid=None, action_xmlid=None, menu_xmlid=None):
        env = request.env
        company = env.company

        action = env.ref(action_xmlid, raise_if_not_found=False) if action_xmlid else False
        view = env.ref(view_xmlid, raise_if_not_found=False) if view_xmlid else False
        menu = env.ref(menu_xmlid, raise_if_not_found=False) if menu_xmlid else False

        params = {
            "id": record_id,
            "model": model,
            "view_type": "form",
            "cids": company.id,
        }
        if action:
            params["action"] = action.id
        if view:
            params["view_id"] = view.id
        if menu:
            params["menu_id"] = menu.id

        fragment = "&".join(
            f"{quote_plus(str(key))}={quote_plus(str(value))}"
            for key, value in params.items()
            if value not in (False, None, "")
        )
        return redirect(f"/web#{fragment}")

    def _create_home_wizard(self, title):
        env = request.env
        user = env.user
        company = env.company
        wizard = env["route.pda.home"].with_context(
            allowed_company_ids=user.company_ids.ids,
            force_company=company.id,
        ).create({
            "name": title,
            "user_id": user.id,
            "company_id": company.id,
        })
        return wizard

    @http.route("/route_core/pda/product_center", type="http", auth="user", website=False)
    def route_core_open_product_center(self, **kwargs):
        wizard = self._create_home_wizard("Products and Stock")
        return self._build_web_redirect(
            model="route.pda.home",
            record_id=wizard.id,
            view_xmlid="route_core.view_route_pda_product_center_form",
            action_xmlid="route_core.action_route_pda_product_center_direct",
            menu_xmlid="route_core.menu_route_salesperson_home",
        )

    @http.route("/route_core/pda/outlet_center", type="http", auth="user", website=False)
    def route_core_open_outlet_center(self, **kwargs):
        wizard = self._create_home_wizard("Customer and Outlets")
        return self._build_web_redirect(
            model="route.pda.home",
            record_id=wizard.id,
            view_xmlid="route_core.view_route_pda_outlet_center_form",
            menu_xmlid="route_core.menu_route_salesperson_home",
        )

    @http.route("/route_core/pda/outlet/<int:outlet_id>", type="http", auth="user", website=False)
    def route_core_open_outlet_form(self, outlet_id, **kwargs):
        outlet = request.env["route.outlet"].browse(outlet_id).exists()
        if not outlet:
            return redirect("/route_core/pda/outlet_center")
        return self._build_web_redirect(
            model="route.outlet",
            record_id=outlet.id,
            view_xmlid="route_core.view_route_outlet_pda_form",
            action_xmlid="route_core.action_route_outlet",
            menu_xmlid="route_core.menu_route_outlet",
        )


class RouteGeoLiveMapController(http.Controller):
    def _selection_label(self, record, field_name, value):
        if not value or field_name not in record._fields:
            return ""
        selection = record._fields[field_name].selection
        if callable(selection):
            selection = selection(record.env[record._name])
        return dict(selection or []).get(value, value)

    def _has_point(self, latitude, longitude):
        return bool(latitude or longitude)

    def _format_datetime(self, env, value):
        if not value:
            return ""
        try:
            user_dt = fields.Datetime.context_timestamp(env.user, value)
            return user_dt.strftime("%b %d, %I:%M %p")
        except Exception:
            return str(value)

    def _google_map_url(self, latitude, longitude):
        if not self._has_point(latitude, longitude):
            return "#"
        return "https://www.google.com/maps/search/?api=1&query=%s,%s" % (latitude, longitude)

    def _visit_payload(self, center, visit):
        checkin_lat = visit.geo_checkin_latitude or 0.0
        checkin_lng = visit.geo_checkin_longitude or 0.0
        outlet = visit.outlet_id
        outlet_lat = outlet.geo_latitude if outlet else 0.0
        outlet_lng = outlet.geo_longitude if outlet else 0.0
        has_checkin = self._has_point(checkin_lat, checkin_lng)
        has_outlet = self._has_point(outlet_lat, outlet_lng)
        geo_state = visit.geo_review_state or ""
        decision = visit.geo_review_supervisor_decision or ""
        main_lat = checkin_lat if has_checkin else outlet_lat
        main_lng = checkin_lng if has_checkin else outlet_lng
        return {
            "id": visit.id,
            "name": visit.display_name or visit.name or "",
            "outlet": outlet.display_name if outlet else "",
            "salesperson": visit.user_id.display_name or "",
            "vehicle": visit.vehicle_id.display_name or "",
            "area": visit.area_id.display_name or "",
            "customer": visit.partner_id.display_name or "",
            "distance": visit.geo_checkin_distance_display or "",
            "accuracy": "%.2f m" % (visit.geo_checkin_accuracy_m or 0.0) if visit.geo_checkin_accuracy_m else "",
            "reason": visit.geo_checkin_outside_zone_reason or "",
            "checkin_time": self._format_datetime(center.env, visit.geo_checkin_datetime),
            "geo_state": geo_state,
            "geo_state_label": self._selection_label(visit, "geo_review_state", geo_state),
            "decision": decision,
            "decision_label": self._selection_label(visit, "geo_review_supervisor_decision", decision),
            "process": self._selection_label(visit, "visit_process_state", visit.visit_process_state) or visit.visit_process_state or "",
            "has_checkin": has_checkin,
            "has_outlet": has_outlet,
            "lat": main_lat,
            "lng": main_lng,
            "checkin_lat": checkin_lat,
            "checkin_lng": checkin_lng,
            "outlet_lat": outlet_lat,
            "outlet_lng": outlet_lng,
            "visit_url": "/web#id=%s&model=route.visit&view_type=form" % visit.id,
            "outlet_map_url": self._google_map_url(outlet_lat, outlet_lng),
            "checkin_map_url": self._google_map_url(checkin_lat, checkin_lng),
            "accept_url": "/route_core/geo/live_map/decision/%s/%s/accept" % (center.id, visit.id),
            "correction_url": "/route_core/geo/live_map/decision/%s/%s/needs_correction" % (center.id, visit.id),
            "reset_url": "/route_core/geo/live_map/decision/%s/%s/reset" % (center.id, visit.id),
        }

    def _render_live_map_html(self, center, message=""):
        visits = center.geo_visit_ids
        payload = [self._visit_payload(center, visit) for visit in visits]
        mapped = [visit for visit in payload if visit.get("lat") or visit.get("lng")]
        data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        title = escape(center.name or "Visit Location Map")
        subtitle = escape("%s • %s filtered visits • %s mapped" % (center.visit_date or "", len(payload), len(mapped)))
        message_html = ""
        if message:
            message_html = '<div class="toast-note">%s</div>' % escape(message)
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
:root {{ --route-primary:#7b4b6f; --route-green:#28a745; --route-orange:#f0a000; --route-red:#dc3545; --route-gray:#6c757d; --route-blue:#0d6efd; }}
html, body {{ height:100%; margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif; color:#111827; background:#f5f6f7; }}
.route-map-page {{ height:100vh; display:flex; flex-direction:column; }}
.route-map-header {{ padding:10px 12px; background:#fff; border-bottom:1px solid #d9dee3; display:flex; justify-content:space-between; gap:12px; align-items:center; }}
.route-map-title {{ font-size:17px; font-weight:800; line-height:1.2; }}
.route-map-subtitle {{ font-size:12px; color:#6b7280; margin-top:2px; }}
.route-map-legend {{ display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }}
.legend-pill {{ display:inline-flex; align-items:center; gap:5px; border:1px solid #e5e7eb; background:#fff; border-radius:999px; padding:4px 8px; font-size:12px; font-weight:700; }}
.legend-dot {{ width:10px; height:10px; border-radius:999px; display:inline-block; }}
.route-map-body {{ flex:1; display:grid; grid-template-columns:minmax(0,1fr) 340px; min-height:0; }}
#map {{ min-height:480px; height:100%; background:#e5e7eb; }}
.route-map-side {{ background:#fff; border-left:1px solid #d9dee3; overflow:auto; padding:10px; }}
.visit-card {{ border:1px solid #e5e7eb; border-radius:12px; padding:10px; margin-bottom:10px; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
.visit-card:hover {{ border-color:var(--route-primary); cursor:pointer; }}
.visit-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }}
.visit-title {{ font-weight:800; font-size:15px; }}
.visit-ref {{ color:#6b7280; font-size:13px; margin-top:2px; }}
.badge {{ display:inline-flex; align-items:center; justify-content:center; border-radius:999px; padding:3px 8px; font-size:11px; font-weight:800; white-space:nowrap; border:1px solid transparent; }}
.badge-gray {{ color:#111827; background:#eef0f2; border-color:#d8dbe0; }}
.badge-green {{ color:#fff; background:var(--route-green); }}
.badge-orange {{ color:#111827; background:var(--route-orange); }}
.badge-red {{ color:#fff; background:var(--route-red); }}
.badge-blue {{ color:#fff; background:var(--route-blue); }}
.visit-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:7px 10px; margin-top:10px; font-size:13px; }}
.label {{ color:#6b7280; display:block; }}
.value {{ font-weight:750; }}
.actions {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }}
.map-btn {{ display:inline-flex; align-items:center; text-decoration:none; color:#111827; background:#e9ecef; border:0; border-radius:6px; padding:6px 8px; font-weight:800; font-size:12px; }}
.map-btn.primary {{ color:#fff; background:var(--route-primary); }}
.map-btn.green {{ color:#fff; background:var(--route-green); }}
.map-btn.orange {{ color:#111827; background:var(--route-orange); }}
.map-btn.light {{ background:#fff; border:1px solid #d9dee3; }}
.toast-note {{ background:#e8f5e9; color:#14532d; border:1px solid #bbf7d0; border-radius:8px; margin:8px 12px; padding:8px 10px; font-weight:700; }}
.marker-dot {{ width:28px; height:28px; border-radius:50% 50% 50% 0; transform:rotate(-45deg); border:2px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,.35); display:flex; align-items:center; justify-content:center; color:#fff; font-weight:900; }}
.marker-dot span {{ transform:rotate(45deg); font-size:12px; }}
.marker-green {{ background:var(--route-green); }}
.marker-orange {{ background:var(--route-orange); color:#111827; }}
.marker-red {{ background:var(--route-red); }}
.marker-blue {{ background:var(--route-blue); }}
.marker-gray {{ background:var(--route-gray); }}
.popup-title {{ font-weight:900; font-size:15px; margin-bottom:4px; }}
.popup-row {{ font-size:12px; margin:2px 0; }}
.popup-actions {{ display:flex; flex-wrap:wrap; gap:5px; margin-top:8px; }}
.no-map {{ height:100%; display:flex; align-items:center; justify-content:center; text-align:center; padding:24px; color:#6b7280; font-weight:700; }}
@media (max-width: 900px) {{
  .route-map-header {{ align-items:flex-start; flex-direction:column; }}
  .route-map-legend {{ justify-content:flex-start; }}
  .route-map-body {{ grid-template-columns:1fr; grid-template-rows:55vh auto; }}
  .route-map-side {{ border-left:0; border-top:1px solid #d9dee3; max-height:none; }}
}}
</style>
</head>
<body>
<div class="route-map-page">
  <div class="route-map-header">
    <div><div class="route-map-title">Visit Location Map</div><div class="route-map-subtitle">{subtitle}</div></div>
    <div class="route-map-legend">
      <span class="legend-pill"><span class="legend-dot" style="background:var(--route-green)"></span>Inside/Accepted</span>
      <span class="legend-pill"><span class="legend-dot" style="background:var(--route-orange)"></span>Outside/Correction</span>
      <span class="legend-pill"><span class="legend-dot" style="background:var(--route-blue)"></span>No Check-in</span>
      <span class="legend-pill"><span class="legend-dot" style="background:var(--route-gray)"></span>No Location</span>
    </div>
  </div>
  {message_html}
  <div class="route-map-body">
    <div id="map"><div class="no-map">Loading map...</div></div>
    <aside class="route-map-side" id="visitList"></aside>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const visits = {data_json};
function escapeHtml(value) {{ return String(value || '').replace(/[&<>'"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}}[c])); }}
function markerColor(v) {{
  if (v.decision === 'needs_correction') return 'orange';
  if (v.decision === 'accepted') return 'green';
  if (v.geo_state === 'inside_zone') return 'green';
  if (v.geo_state === 'outside_no_reason' || v.geo_state === 'outside_with_reason') return 'orange';
  if (v.geo_state === 'pending_checkin') return 'blue';
  return 'gray';
}}
function badgeClass(v) {{
  if (v.decision === 'needs_correction') return 'badge-orange';
  if (v.decision === 'accepted') return 'badge-green';
  if (v.geo_state === 'inside_zone') return 'badge-green';
  if (v.geo_state === 'outside_no_reason' || v.geo_state === 'outside_with_reason') return 'badge-orange';
  if (v.geo_state === 'pending_checkin') return 'badge-blue';
  return 'badge-gray';
}}
function statusText(v) {{ return v.decision_label || v.geo_state_label || 'Location Status'; }}
function actionButtons(v) {{
  let html = `<a class="map-btn primary" href="${{v.visit_url}}" target="_top">Open Visit</a>`;
  if (v.has_outlet) html += `<a class="map-btn" href="${{v.outlet_map_url}}" target="_blank">Outlet Map</a>`;
  if (v.has_checkin) html += `<a class="map-btn" href="${{v.checkin_map_url}}" target="_blank">Check-in Map</a>`;
  if (v.decision !== 'accepted') html += `<a class="map-btn green" href="${{v.accept_url}}">Accept</a>`;
  if (v.decision !== 'needs_correction') html += `<a class="map-btn orange" href="${{v.correction_url}}">Needs Correction</a>`;
  if (v.decision) html += `<a class="map-btn light" href="${{v.reset_url}}">Reset</a>`;
  return html;
}}
function visitCard(v) {{
  return `<article class="visit-card" data-visit-id="${{v.id}}">
    <div class="visit-top"><div><div class="visit-title">${{escapeHtml(v.outlet || v.name)}}</div><div class="visit-ref">${{escapeHtml(v.name)}}</div></div><span class="badge ${{badgeClass(v)}}">${{escapeHtml(statusText(v))}}</span></div>
    <div class="visit-grid">
      <div><span class="label">Salesperson</span><span class="value">${{escapeHtml(v.salesperson)}}</span></div>
      <div><span class="label">Vehicle</span><span class="value">${{escapeHtml(v.vehicle)}}</span></div>
      <div><span class="label">Area</span><span class="value">${{escapeHtml(v.area)}}</span></div>
      <div><span class="label">Distance</span><span class="value">${{escapeHtml(v.distance)}}</span></div>
      <div><span class="label">Check-in</span><span class="value">${{escapeHtml(v.checkin_time || 'No check-in')}}</span></div>
      <div><span class="label">Accuracy</span><span class="value">${{escapeHtml(v.accuracy || '-')}}</span></div>
    </div>
    ${{v.reason ? `<div class="popup-row" style="margin-top:8px"><span class="label">Reason</span>${{escapeHtml(v.reason)}}</div>` : ''}}
    <div class="actions">${{actionButtons(v)}}</div>
  </article>`;
}}
function popupHtml(v) {{
  return `<div><div class="popup-title">${{escapeHtml(v.outlet || v.name)}}</div>
    <div class="popup-row"><b>${{escapeHtml(v.name)}}</b></div>
    <div class="popup-row">${{escapeHtml(statusText(v))}}</div>
    <div class="popup-row">Salesperson: ${{escapeHtml(v.salesperson)}}</div>
    <div class="popup-row">Vehicle: ${{escapeHtml(v.vehicle)}}</div>
    <div class="popup-row">Distance: ${{escapeHtml(v.distance)}}</div>
    ${{v.reason ? `<div class="popup-row">Reason: ${{escapeHtml(v.reason)}}</div>` : ''}}
    <div class="popup-actions">${{actionButtons(v)}}</div></div>`;
}}
function renderList() {{
  const list = document.getElementById('visitList');
  if (!visits.length) {{ list.innerHTML = '<div class="no-map">No visits match the current filters.</div>'; return; }}
  list.innerHTML = visits.map(visitCard).join('');
}}
function initMap() {{
  renderList();
  const mappable = visits.filter(v => v.lat || v.lng);
  if (!mappable.length) {{
    document.getElementById('map').innerHTML = '<div class="no-map">No map coordinates for the current filtered visits.</div>';
    return;
  }}
  const map = L.map('map', {{ zoomControl: true }});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }}).addTo(map);
  const bounds = [];
  const markerByVisit = {{}};
  for (const v of mappable) {{
    const color = markerColor(v);
    const icon = L.divIcon({{ className:'', html:`<div class="marker-dot marker-${{color}}"><span>${{v.decision === 'needs_correction' ? '!' : (v.decision === 'accepted' ? '✓' : '•')}}</span></div>`, iconSize:[28,28], iconAnchor:[14,28], popupAnchor:[0,-25] }});
    const marker = L.marker([v.lat, v.lng], {{ icon }}).addTo(map).bindPopup(popupHtml(v));
    markerByVisit[v.id] = marker;
    bounds.push([v.lat, v.lng]);
    if (v.has_checkin && v.has_outlet) {{
      L.circleMarker([v.outlet_lat, v.outlet_lng], {{ radius:5, color:'#7b4b6f', fillColor:'#fff', fillOpacity:1, weight:2 }}).addTo(map).bindPopup(`<b>Outlet Location</b><br/>${{escapeHtml(v.outlet)}}`);
      L.polyline([[v.checkin_lat, v.checkin_lng], [v.outlet_lat, v.outlet_lng]], {{ color:'#7b4b6f', weight:2, opacity:.55, dashArray:'5,6' }}).addTo(map);
      bounds.push([v.outlet_lat, v.outlet_lng]);
    }}
  }}
  if (bounds.length === 1) {{ map.setView(bounds[0], 15); }} else {{ map.fitBounds(bounds, {{ padding:[28,28] }}); }}
  document.querySelectorAll('[data-visit-id]').forEach(el => {{
    el.addEventListener('click', (ev) => {{
      if (ev.target.closest('a')) return;
      const id = parseInt(el.getAttribute('data-visit-id'), 10);
      const marker = markerByVisit[id];
      if (marker) {{ map.setView(marker.getLatLng(), Math.max(map.getZoom(), 15)); marker.openPopup(); }}
    }});
  }});
}}
window.addEventListener('load', () => {{
  renderList();
  if (!window.L) {{
    document.getElementById('map').innerHTML = '<div class="no-map">The map library could not load. Visit cards and Google Map buttons are still available.</div>';
    return;
  }}
  initMap();
}});
</script>
</body>
</html>'''
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/route_core/geo/live_map/frame/<int:center_id>", type="http", auth="user", website=False)
    def route_core_geo_live_map_frame(self, center_id, **kwargs):
        center = request.env["route.geo.control.center"].browse(center_id).exists()
        if not center:
            return request.make_response(
                "<html><body><p>Visit Location Map session was not found. Please reopen Visit Location Control.</p></body></html>",
                headers=[("Content-Type", "text/html; charset=utf-8")],
            )
        return self._render_live_map_html(center, message=kwargs.get("message") or "")

    @http.route("/route_core/geo/live_map/decision/<int:center_id>/<int:visit_id>/<string:decision>", type="http", auth="user", website=False, csrf=False)
    def route_core_geo_live_map_decision(self, center_id, visit_id, decision, **kwargs):
        visit = request.env["route.visit"].browse(visit_id).exists()
        message = "Location review updated."
        if visit:
            if decision == "accept":
                visit.action_geo_review_accept()
                message = "Location review accepted."
            elif decision == "needs_correction":
                visit.action_geo_review_needs_correction()
                message = "Location review marked as needs correction."
            elif decision == "reset":
                visit.action_geo_review_reset_decision()
                message = "Location review decision reset."
        return redirect("/route_core/geo/live_map/frame/%s?message=%s&ts=%s" % (center_id, quote_plus(message), int(time.time())))


class RouteSalespersonTodayMapController(http.Controller):
    def _selection_label(self, record, field_name, value):
        if not value or field_name not in record._fields:
            return ""
        selection = record._fields[field_name].selection
        if callable(selection):
            selection = selection(record.env[record._name])
        return dict(selection or []).get(value, value)

    def _has_point(self, latitude, longitude):
        return bool(latitude or longitude)

    def _format_datetime(self, env, value):
        if not value:
            return ""
        try:
            user_dt = fields.Datetime.context_timestamp(env.user, value)
            return user_dt.strftime("%b %d, %I:%M %p")
        except Exception:
            return str(value)

    def _map_url(self, provider, latitude, longitude):
        if not self._has_point(latitude, longitude):
            return "#"
        if provider == "openstreetmap":
            return "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=17/%s/%s" % (latitude, longitude, latitude, longitude)
        return "https://www.google.com/maps/search/?api=1&query=%s,%s" % (latitude, longitude)

    def _navigation_url(self, provider, latitude, longitude):
        if not self._has_point(latitude, longitude):
            return "#"
        if provider == "openstreetmap":
            return "https://www.openstreetmap.org/?mlat=%s&mlon=%s#map=17/%s/%s" % (latitude, longitude, latitude, longitude)
        return "https://www.google.com/maps/dir/?api=1&destination=%s,%s" % (latitude, longitude)

    def _visit_bucket(self, visit):
        process = visit.visit_process_state or False
        state = visit.state or False
        if state in ("done", "cancel", "cancelled") or process in ("done", "cancel"):
            return "done"
        if state == "in_progress" or process in ("checked_in", "counting", "reconciled", "collection_done", "ready_to_close"):
            return "active"
        return "pending"

    def _can_start_from_map(self, visit):
        if visit.visit_process_state != "draft" or visit.state in ("done", "cancel", "cancelled"):
            return False
        if not getattr(visit, "route_geo_enabled", False):
            return True
        policy = visit.route_geo_checkin_policy or "disabled"
        status = visit.geo_checkin_status or "disabled"
        if policy in ("disabled", "review_only"):
            return True
        if policy == "block_start":
            return status == "inside"
        if policy == "require_reason":
            if status == "inside":
                return True
            if status == "outside" and (visit.geo_checkin_outside_zone_reason or "").strip():
                return True
        return False

    def _start_block_hint(self, visit):
        if visit.visit_process_state != "draft":
            return "Visit already started or finished."
        if not getattr(visit, "route_geo_enabled", False):
            return "Ready to start."
        policy = visit.route_geo_checkin_policy or "disabled"
        status = visit.geo_checkin_status or "disabled"
        if policy in ("disabled", "review_only"):
            return "Ready to start."
        if status == "pending":
            return "Capture location before start."
        if status == "outlet_missing":
            return "Outlet location missing."
        if policy == "block_start" and status == "outside":
            return "Outside zone: start blocked."
        if policy == "require_reason" and status == "outside" and not (visit.geo_checkin_outside_zone_reason or "").strip():
            return "Outside zone: reason required."
        return "Open visit to continue."

    def _visit_payload(self, route_map, visit, index):
        outlet = visit.outlet_id
        lat = outlet.geo_latitude if outlet else 0.0
        lng = outlet.geo_longitude if outlet else 0.0
        provider = route_map.route_map_provider or "google"
        bucket = self._visit_bucket(visit)
        can_start = self._can_start_from_map(visit)
        geo_status = visit.geo_checkin_status or "disabled"
        start_hint = self._start_block_hint(visit)
        return {
            "id": visit.id,
            "index": index,
            "name": visit.display_name or visit.name or "",
            "outlet": outlet.display_name if outlet else "",
            "customer": visit.partner_id.display_name or "",
            "area": visit.area_id.display_name or "",
            "vehicle": visit.vehicle_id.display_name or "",
            "process": self._selection_label(visit, "visit_process_state", visit.visit_process_state) or visit.visit_process_state or "",
            "bucket": bucket,
            "geo_status": geo_status,
            "geo_status_label": self._selection_label(visit, "geo_checkin_status", geo_status) or geo_status,
            "distance": visit.geo_checkin_distance_display or "",
            "checkin_time": self._format_datetime(route_map.env, visit.geo_checkin_datetime),
            "outside_reason": visit.geo_checkin_outside_zone_reason or "",
            "lat": lat,
            "lng": lng,
            "has_point": self._has_point(lat, lng),
            "navigate_url": self._navigation_url(provider, lat, lng),
            "outlet_map_url": self._map_url(provider, lat, lng),
            "visit_url": "/web#id=%s&model=route.visit&view_type=form" % visit.id,
            "start_url": "/route_core/pda/today_route_map/start/%s/%s" % (route_map.id, visit.id),
            "can_start": can_start,
            "start_hint": start_hint,
        }

    def _render_today_route_map_html(self, route_map, message="", message_type="info"):
        visits = route_map.route_visit_ids
        payload = [self._visit_payload(route_map, visit, index + 1) for index, visit in enumerate(visits)]
        mapped = [visit for visit in payload if visit.get("has_point")]
        data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        title = escape(route_map.name or "Today's Route Map")
        subtitle = escape("%s • %s visits • %s mapped" % (route_map.visit_date or "", len(payload), len(mapped)))
        message_html = ""
        if message:
            css_class = "toast-note toast-%s" % (message_type or "info")
            message_html = '<div class="%s">%s</div>' % (css_class, escape(message))
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
:root {{ --route-primary:#7b4b6f; --green:#16a34a; --blue:#0ea5e9; --orange:#f59e0b; --red:#ef4444; --gray:#64748b; --line:#e5e7eb; }}
html,body {{ height:100%; margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif; color:#111827; background:#f8fafc; }}
.route-map-page {{ min-height:100vh; display:flex; flex-direction:column; }}
.route-map-header {{ background:#fff; border:1px solid #e9d5ff; border-left:6px solid var(--route-primary); padding:10px 12px; display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
.route-map-title {{ font-size:18px; font-weight:900; line-height:1.2; }}
.route-map-subtitle {{ margin-top:3px; color:#64748b; font-size:12px; font-weight:700; }}
.legend {{ display:flex; flex-wrap:wrap; gap:6px; justify-content:flex-end; }}
.legend-pill {{ border:1px solid var(--line); background:#fff; border-radius:999px; padding:4px 8px; font-size:12px; font-weight:800; display:inline-flex; align-items:center; gap:5px; }}
.legend-dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
.route-map-body {{ flex:1; display:grid; grid-template-columns:minmax(0,1fr) 380px; min-height:0; }}
#map {{ min-height:520px; background:#e5e7eb; }}
.visit-side {{ background:#fff; border-left:1px solid var(--line); overflow:auto; padding:10px; }}
.visit-card {{ border:1px solid var(--line); border-radius:14px; padding:10px; margin-bottom:10px; background:#fff; box-shadow:0 1px 2px rgba(15,23,42,.04); }}
.visit-card:hover {{ border-color:var(--route-primary); cursor:pointer; }}
.visit-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }}
.visit-title {{ font-size:15px; font-weight:900; line-height:1.25; }}
.visit-ref {{ color:#64748b; font-size:12px; margin-top:2px; }}
.badge {{ border-radius:999px; padding:3px 8px; font-size:11px; font-weight:900; white-space:nowrap; }}
.badge-pending {{ background:#e0f2fe; color:#075985; }}
.badge-active {{ background:#fef3c7; color:#92400e; }}
.badge-done {{ background:#dcfce7; color:#166534; }}
.badge-outside {{ background:#fee2e2; color:#991b1b; }}
.badge-missing {{ background:#f1f5f9; color:#475569; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:7px 9px; margin-top:9px; font-size:12px; }}
.label {{ color:#64748b; display:block; font-weight:700; }}
.value {{ font-weight:850; color:#111827; }}
.actions {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px; margin-top:10px; }}
.map-btn {{ display:flex; align-items:center; justify-content:center; min-height:34px; text-decoration:none; border-radius:8px; font-size:12px; font-weight:900; background:#eef2f7; color:#111827; padding:6px 8px; border:1px solid transparent; }}
.map-btn.primary {{ background:var(--route-primary); color:#fff; }}
.map-btn.green {{ background:var(--green); color:#fff; }}
.map-btn.light {{ background:#fff; color:#111827; border-color:var(--line); }}
.hint {{ margin-top:8px; font-size:12px; color:#64748b; font-weight:700; }}
.toast-note {{ margin:8px 10px; border-radius:10px; padding:9px 10px; font-weight:850; font-size:13px; border:1px solid #bfdbfe; background:#eff6ff; color:#1e3a8a; }}
.toast-success {{ background:#ecfdf5; color:#14532d; border-color:#bbf7d0; }}
.toast-danger {{ background:#fef2f2; color:#991b1b; border-color:#fecaca; }}
.marker-dot {{ width:30px; height:30px; border-radius:50% 50% 50% 0; transform:rotate(-45deg); border:2px solid #fff; box-shadow:0 2px 7px rgba(15,23,42,.35); display:flex; align-items:center; justify-content:center; color:#fff; font-weight:900; }}
.marker-dot span {{ transform:rotate(45deg); font-size:12px; }}
.marker-pending {{ background:var(--blue); }}
.marker-active {{ background:var(--orange); color:#111827; }}
.marker-done {{ background:var(--green); }}
.marker-outside {{ background:var(--red); }}
.marker-missing {{ background:var(--gray); }}
.popup-title {{ font-weight:900; font-size:15px; margin-bottom:4px; }}
.popup-row {{ margin:3px 0; font-size:12px; }}
.no-map {{ height:100%; display:flex; align-items:center; justify-content:center; text-align:center; padding:22px; color:#64748b; font-weight:800; }}
@media (max-width: 900px) {{
  .route-map-header {{ flex-direction:column; padding:10px; }}
  .legend {{ justify-content:flex-start; }}
  .route-map-body {{ display:block; }}
  #map {{ height:46vh; min-height:320px; }}
  .visit-side {{ border-left:0; border-top:1px solid var(--line); padding:10px; }}
  .actions {{ grid-template-columns:1fr 1fr; }}
}}
@media (max-width: 420px) {{
  .route-map-title {{ font-size:16px; }}
  .route-map-subtitle {{ font-size:11px; }}
  .legend-pill {{ font-size:11px; padding:4px 7px; }}
  .grid {{ grid-template-columns:1fr 1fr; gap:8px 12px; }}
  .visit-card {{ padding:12px; border-radius:16px; }}
  .visit-title {{ font-size:15px; }}
  .map-btn {{ min-height:40px; font-size:12px; }}
}}
</style>
</head>
<body>
<div class="route-map-page">
  <div class="route-map-header">
    <div><div class="route-map-title">Today Route Map</div><div class="route-map-subtitle">{subtitle}</div></div>
    <div class="legend">
      <span class="legend-pill"><span class="legend-dot" style="background:var(--blue)"></span>Pending</span>
      <span class="legend-pill"><span class="legend-dot" style="background:var(--orange)"></span>In Progress</span>
      <span class="legend-pill"><span class="legend-dot" style="background:var(--green)"></span>Done</span>
      <span class="legend-pill"><span class="legend-dot" style="background:var(--red)"></span>Outside Zone</span>
    </div>
  </div>
  {message_html}
  <div class="route-map-body">
    <div id="map"><div class="no-map">Loading map...</div></div>
    <aside class="visit-side" id="visitList"></aside>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const visits = {data_json};
function escapeHtml(value) {{ return String(value || '').replace(/[&<>'"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}}[c])); }}
function color(v) {{ if (v.geo_status === 'outside') return 'outside'; if (v.bucket === 'done') return 'done'; if (v.bucket === 'active') return 'active'; if (!v.has_point) return 'missing'; return 'pending'; }}
function badgeText(v) {{ if (v.geo_status === 'outside') return 'Outside Zone'; if (v.bucket === 'done') return 'Done'; if (v.bucket === 'active') return 'In Progress'; if (!v.has_point) return 'No Location'; return 'Pending'; }}
function actions(v) {{
  let html = `<a class="map-btn primary" href="${{v.visit_url}}" target="_top">Open Visit</a>`;
  if (v.has_point) html += `<a class="map-btn" href="${{v.navigate_url}}" target="_blank">Navigate</a>`;
  if (v.can_start) html += `<a class="map-btn green" href="${{v.start_url}}">Start Visit</a>`;
  if (v.has_point) html += `<a class="map-btn light" href="${{v.outlet_map_url}}" target="_blank">Outlet Map</a>`;
  return html;
}}
function card(v) {{
  const c = color(v);
  return `<article class="visit-card" data-visit-id="${{v.id}}">
    <div class="visit-top"><div><div class="visit-title">${{escapeHtml(v.index + '. ' + (v.outlet || v.name))}}</div><div class="visit-ref">${{escapeHtml(v.name)}}</div></div><span class="badge badge-${{c}}">${{escapeHtml(badgeText(v))}}</span></div>
    <div class="grid">
      <div><span class="label">Customer</span><span class="value">${{escapeHtml(v.customer || '-')}}</span></div>
      <div><span class="label">Area</span><span class="value">${{escapeHtml(v.area || '-')}}</span></div>
      <div><span class="label">Vehicle</span><span class="value">${{escapeHtml(v.vehicle || '-')}}</span></div>
      <div><span class="label">Process</span><span class="value">${{escapeHtml(v.process || '-')}}</span></div>
      <div><span class="label">Location</span><span class="value">${{escapeHtml(v.geo_status_label || '-')}}</span></div>
      <div><span class="label">Distance</span><span class="value">${{escapeHtml(v.distance || '-')}}</span></div>
    </div>
    <div class="hint">${{escapeHtml(v.start_hint || '')}}</div>
    <div class="actions">${{actions(v)}}</div>
  </article>`;
}}
function popup(v) {{ return `<div><div class="popup-title">${{escapeHtml(v.outlet || v.name)}}</div><div class="popup-row">${{escapeHtml(v.process || '')}} • ${{escapeHtml(v.geo_status_label || '')}}</div><div class="popup-row">Area: ${{escapeHtml(v.area || '-')}}</div><div class="popup-row">Distance: ${{escapeHtml(v.distance || '-')}}</div><div class="actions">${{actions(v)}}</div></div>`; }}
function renderList() {{ const list = document.getElementById('visitList'); list.innerHTML = visits.length ? visits.map(card).join('') : '<div class="no-map">No visits are scheduled for today.</div>'; }}
function initMap() {{
  renderList();
  const mappable = visits.filter(v => v.has_point);
  if (!mappable.length) {{ document.getElementById('map').innerHTML = '<div class="no-map">No outlet coordinates for today. Open Customer and Outlets to set locations.</div>'; return; }}
  const map = L.map('map', {{ zoomControl:true }});
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom:19, attribution:'&copy; OpenStreetMap contributors' }}).addTo(map);
  const bounds = [];
  const markers = {{}};
  for (const v of mappable) {{
    const c = color(v);
    const icon = L.divIcon({{ className:'', html:`<div class="marker-dot marker-${{c}}"><span>${{v.index}}</span></div>`, iconSize:[30,30], iconAnchor:[15,30], popupAnchor:[0,-26] }});
    const marker = L.marker([v.lat, v.lng], {{ icon }}).addTo(map).bindPopup(popup(v));
    markers[v.id] = marker;
    bounds.push([v.lat, v.lng]);
  }}
  if (bounds.length === 1) map.setView(bounds[0], 15); else map.fitBounds(bounds, {{ padding:[30,30] }});
  document.querySelectorAll('[data-visit-id]').forEach(el => el.addEventListener('click', ev => {{
    if (ev.target.closest('a')) return;
    const marker = markers[parseInt(el.getAttribute('data-visit-id'), 10)];
    if (marker) {{ map.setView(marker.getLatLng(), Math.max(map.getZoom(), 15)); marker.openPopup(); }}
  }}));
}}
window.addEventListener('load', () => {{ renderList(); if (!window.L) {{ document.getElementById('map').innerHTML = '<div class="no-map">Map library could not load. Visit cards and Navigate buttons are still available.</div>'; return; }} initMap(); }});
</script>
</body>
</html>'''
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/route_core/pda/today_route_map/frame/<int:route_map_id>", type="http", auth="user", website=False)
    def route_core_today_route_map_frame(self, route_map_id, **kwargs):
        route_map = request.env["route.salesperson.route.map"].browse(route_map_id).exists()
        if not route_map:
            return request.make_response(
                "<html><body><p>Today Route Map session was not found. Please reopen Route Workspace.</p></body></html>",
                headers=[("Content-Type", "text/html; charset=utf-8")],
            )
        if route_map.user_id != request.env.user and not request.env.user.has_group("route_core.group_route_supervisor") and not request.env.user.has_group("route_core.group_route_management"):
            return request.make_response(
                "<html><body><p>You can only open your own route map.</p></body></html>",
                headers=[("Content-Type", "text/html; charset=utf-8")],
            )
        return self._render_today_route_map_html(route_map, message=kwargs.get("message") or "", message_type=kwargs.get("message_type") or "info")

    @http.route("/route_core/pda/today_route_map/start/<int:route_map_id>/<int:visit_id>", type="http", auth="user", website=False, csrf=False)
    def route_core_today_route_map_start_visit(self, route_map_id, visit_id, **kwargs):
        route_map = request.env["route.salesperson.route.map"].browse(route_map_id).exists()
        visit = request.env["route.visit"].browse(visit_id).exists()
        message = "Visit could not be started."
        message_type = "danger"
        if route_map and visit and visit.user_id == request.env.user and visit.date == route_map.visit_date:
            try:
                if not self._can_start_from_map(visit):
                    message = self._start_block_hint(visit)
                    message_type = "danger"
                else:
                    visit.action_ux_start_visit() if hasattr(visit, "action_ux_start_visit") else visit.action_start_visit()
                    message = "Visit started. Open Visit to continue execution."
                    message_type = "success"
            except Exception as exc:
                message = str(exc)
                message_type = "danger"
        return redirect("/route_core/pda/today_route_map/frame/%s?message=%s&message_type=%s&ts=%s" % (route_map_id, quote_plus(message), quote_plus(message_type), int(time.time())))
