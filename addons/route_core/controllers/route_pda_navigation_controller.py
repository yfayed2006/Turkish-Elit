from urllib.parse import urlencode

from odoo import http
from odoo.http import request


class RoutePdaNavigationController(http.Controller):
    """Small backend redirects used by the mobile navigation guard.

    The JavaScript guard uses stable URLs for back buttons.  Without these
    routes, the browser can fall through to the website and show a 404 page.
    These routes redirect back into the Odoo web client with the correct model
    and view instead of relying on a stale client controller stack.
    """

    def _web_hash_redirect(self, **params):
        clean = {key: value for key, value in params.items() if value not in (False, None, "")}
        return request.redirect("/web#%s" % urlencode(clean))

    def _open_home_view(self, view_xmlid):
        home = request.env["route.pda.home"].create({})
        home._refresh_dashboard_snapshot()
        view = request.env.ref(view_xmlid, raise_if_not_found=False)
        return self._web_hash_redirect(
            id=home.id,
            model="route.pda.home",
            view_type="form",
            view_id=view.id if view else False,
        )

    @http.route("/route_core/pda/product_center", type="http", auth="user", website=False)
    def route_pda_product_center(self, **kwargs):
        return self._open_home_view("route_core.view_route_pda_product_center_form")

    @http.route("/route_core/pda/outlet_center", type="http", auth="user", website=False)
    def route_pda_outlet_center(self, **kwargs):
        return self._open_home_view("route_core.view_route_pda_outlet_center_form")

    @http.route("/route_core/pda/outlet/<int:outlet_id>", type="http", auth="user", website=False)
    def route_pda_outlet_profile(self, outlet_id, **kwargs):
        outlet = request.env["route.outlet"].browse(outlet_id).exists()
        if not outlet:
            return self.route_pda_outlet_center(**kwargs)
        view = request.env.ref("route_core.view_route_outlet_financial_profile_form", raise_if_not_found=False)
        return self._web_hash_redirect(
            id=outlet.id,
            model="route.outlet",
            view_type="form",
            view_id=view.id if view else False,
        )
