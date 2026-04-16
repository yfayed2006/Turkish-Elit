from urllib.parse import quote_plus

from werkzeug.utils import redirect

from odoo import http
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
