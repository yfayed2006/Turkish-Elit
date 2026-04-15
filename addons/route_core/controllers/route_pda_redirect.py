from urllib.parse import quote_plus

from werkzeug.utils import redirect

from odoo import http
from odoo.http import request


class RoutePdaRedirectController(http.Controller):
    @http.route("/route_core/pda/product_center", type="http", auth="user", website=False)
    def route_core_open_product_center(self, **kwargs):
        env = request.env
        user = env.user
        company = env.company

        wizard = env["route.pda.home"].with_context(
            allowed_company_ids=user.company_ids.ids,
            force_company=company.id,
        ).create({
            "name": "Products and Stock",
            "user_id": user.id,
            "company_id": company.id,
        })

        action = env.ref("route_core.action_route_pda_product_center_direct", raise_if_not_found=False)
        view = env.ref("route_core.view_route_pda_product_center_form", raise_if_not_found=False)
        menu = env.ref("route_core.menu_route_salesperson_home", raise_if_not_found=False)

        params = {
            "action": action.id if action else "",
            "id": wizard.id,
            "model": "route.pda.home",
            "view_type": "form",
            "cids": company.id,
        }
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
