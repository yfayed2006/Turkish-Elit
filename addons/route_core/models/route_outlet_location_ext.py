from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Outlet Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        help="Internal stock location used for this outlet consignment/location mapping.",
    )
    consignment_stock_location_mode = fields.Selection(
        [("auto_create", "Create Automatically"), ("select_existing", "Select Existing")],
        string="Consignment Stock Location Mode",
        default="auto_create",
        help="Choose whether the outlet stock location should be created automatically under the consignment root path or selected from existing internal locations.",
    )
    auto_stock_location_preview = fields.Char(
        string="Auto Stock Location Path",
        compute="_compute_auto_stock_location_preview",
        readonly=True,
    )

    @api.depends(
        "outlet_operation_mode",
        "consignment_stock_location_mode",
        "company_id",
        "name",
        "code",
        "route_city_id",
        "area_id",
    )
    def _compute_auto_stock_location_preview(self):
        for record in self:
            if record.outlet_operation_mode != "consignment" or record.consignment_stock_location_mode != "auto_create":
                record.auto_stock_location_preview = False
                continue
            parts = [record._get_consignment_root_display_name()]
            if record.route_city_id:
                parts.append(record._sanitize_location_segment(record.route_city_id.name))
            if record.area_id:
                parts.append(record._sanitize_location_segment(record.area_id.name))
            parts.append(record._get_outlet_location_leaf_name())
            record.auto_stock_location_preview = " / ".join([part for part in parts if part])

    @api.onchange("outlet_operation_mode")
    def _onchange_consignment_stock_location_mode(self):
        for record in self:
            if record.outlet_operation_mode == "consignment":
                if not record.consignment_stock_location_mode:
                    record.consignment_stock_location_mode = "auto_create"
            else:
                record.consignment_stock_location_mode = "auto_create"
                record.stock_location_id = False

    @api.constrains("outlet_operation_mode", "consignment_stock_location_mode", "stock_location_id")
    def _check_consignment_stock_location_setup(self):
        for record in self:
            if record.outlet_operation_mode != "consignment":
                continue
            if record.consignment_stock_location_mode == "select_existing" and not record.stock_location_id:
                raise ValidationError(_("Please choose Outlet Stock Location or switch Consignment Stock Location Mode to Create Automatically."))

    def _sanitize_location_segment(self, value):
        value = (value or "").strip()
        return value.replace("/", "-") if value else False

    def _get_outlet_location_leaf_name(self):
        self.ensure_one()
        code = (self.code or "").strip()
        name = (self.name or _("New Outlet")).strip()
        if code:
            return f"{code} - {name}"
        return name

    def _get_consignment_root_display_name(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        root = company.route_default_consignment_root_location_id
        if root:
            return root.complete_name or root.display_name or root.name
        warehouse = company.route_default_source_warehouse_id
        if warehouse and warehouse.view_location_id:
            return "%s / %s" % ((warehouse.view_location_id.complete_name or warehouse.view_location_id.display_name or warehouse.view_location_id.name), _("Consignment Outlets"))
        return _("Consignment Outlets")

    def _get_route_default_source_warehouse(self, company):
        warehouse = company.route_default_source_warehouse_id
        if warehouse:
            return warehouse
        return self.env["stock.warehouse"].sudo().search([("company_id", "=", company.id)], limit=1)

    def _get_or_create_consignment_root_location(self, company):
        company = company.sudo()
        root = company.route_default_consignment_root_location_id
        if root and root.exists():
            return root

        warehouse = self._get_route_default_source_warehouse(company)
        parent_location = warehouse.view_location_id if warehouse and warehouse.view_location_id else False
        vals = {
            "name": _("Consignment Outlets"),
            "usage": "view",
            "company_id": company.id,
            "active": True,
        }
        if parent_location:
            vals["location_id"] = parent_location.id
        root = self.env["stock.location"].sudo().create(vals)
        self.env["ir.config_parameter"].sudo().set_param(
            company._route_feature_param_key("default_consignment_root_location_id"),
            str(root.id),
        )
        return root

    def _get_or_create_child_location(self, parent_location, name, usage, company):
        name = self._sanitize_location_segment(name) or _("Undefined")
        domain = [
            ("location_id", "=", parent_location.id),
            ("name", "=", name),
            ("usage", "=", usage),
            ("company_id", "=", company.id),
        ]
        location = self.env["stock.location"].sudo().search(domain, limit=1)
        if location:
            return location
        return self.env["stock.location"].sudo().create({
            "name": name,
            "usage": usage,
            "location_id": parent_location.id,
            "company_id": company.id,
            "active": True,
        })

    def _ensure_auto_consignment_stock_location(self):
        for record in self:
            if record.outlet_operation_mode != "consignment" or record.stock_location_id:
                continue
            company = record.company_id or self.env.company
            root = record._get_or_create_consignment_root_location(company)
            city_name = record.route_city_id.name or record.city or _("No City")
            area_name = record.area_id.name or record.route_area_name or _("No Area")
            city_location = record._get_or_create_child_location(root, city_name, "view", company)
            area_location = record._get_or_create_child_location(city_location, area_name, "view", company)
            leaf_name = record._get_outlet_location_leaf_name()
            outlet_location = record._get_or_create_child_location(area_location, leaf_name, "internal", company)
            record.with_context(skip_route_outlet_stock_sync=True).write({"stock_location_id": outlet_location.id})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_outlet_stock_location_setup()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get("skip_route_outlet_stock_sync"):
            self._sync_outlet_stock_location_setup()
        return result

    def _sync_outlet_stock_location_setup(self):
        balance_model = self.env["outlet.stock.balance"].sudo()
        for record in self:
            if record.outlet_operation_mode != "consignment":
                if record.stock_location_id:
                    record.with_context(skip_route_outlet_stock_sync=True).write({"stock_location_id": False})
                if "outlet_id" in balance_model._fields:
                    balance_model.search([("outlet_id", "=", record.id)]).unlink()
                continue
            if record.consignment_stock_location_mode == "auto_create":
                record._ensure_auto_consignment_stock_location()
            record._sync_outlet_stock_balance_records()


    def _get_balance_model(self):
        self.ensure_one()
        return self.env["outlet.stock.balance"].sudo()

    def _prepare_outlet_balance_rows(self):
        self.ensure_one()
        rows = {}
        if self.outlet_operation_mode != "consignment" or not self.stock_location_id:
            return rows

        quant_model = self.env["stock.quant"].sudo()
        quants = quant_model.search([
            ("location_id", "child_of", self.stock_location_id.id),
            ("quantity", ">", 0),
        ])

        for quant in quants:
            product = quant.product_id
            if not product:
                continue

            row = rows.setdefault(product.id, {
                "product_id": product.id,
                "qty": 0.0,
                "unit_price": 0.0,
                "lot_names": set(),
                "nearest_expiry_date": False,
                "nearest_alert_date": False,
            })

            row["qty"] += quant.quantity or 0.0
            if not row["unit_price"]:
                row["unit_price"] = (
                    getattr(product, "lst_price", 0.0)
                    or getattr(product, "list_price", 0.0)
                    or getattr(product, "standard_price", 0.0)
                    or 0.0
                )

            lot = getattr(quant, "lot_id", False)
            if lot:
                if lot.name:
                    row["lot_names"].add(lot.name)
                expiry_date = (
                    getattr(lot, "expiration_date", False)
                    or getattr(lot, "use_date", False)
                    or getattr(lot, "life_date", False)
                    or False
                )
                alert_date = (
                    getattr(lot, "alert_date", False)
                    or getattr(lot, "removal_date", False)
                    or False
                )
                if expiry_date and (not row["nearest_expiry_date"] or expiry_date < row["nearest_expiry_date"]):
                    row["nearest_expiry_date"] = expiry_date
                if alert_date and (not row["nearest_alert_date"] or alert_date < row["nearest_alert_date"]):
                    row["nearest_alert_date"] = alert_date

        return rows

    def _sync_outlet_stock_balance_records(self):
        balance_model = self.env["outlet.stock.balance"].sudo()
        balance_fields = balance_model._fields
        now_value = fields.Datetime.now()

        for record in self:
            existing_balances = balance_model.search([("outlet_id", "=", record.id)]) if "outlet_id" in balance_fields else balance_model.browse()

            if record.outlet_operation_mode != "consignment" or not record.stock_location_id:
                if existing_balances:
                    existing_balances.unlink()
                continue

            rows = record._prepare_outlet_balance_rows()
            existing_map = {balance.product_id.id: balance for balance in existing_balances if getattr(balance, "product_id", False)}
            touched_product_ids = set()

            for product_id, row in rows.items():
                touched_product_ids.add(product_id)
                vals = {}
                if "outlet_id" in balance_fields:
                    vals["outlet_id"] = record.id
                if "product_id" in balance_fields:
                    vals["product_id"] = product_id
                if "qty" in balance_fields:
                    vals["qty"] = row["qty"]
                if "unit_price" in balance_fields:
                    vals["unit_price"] = row["unit_price"]
                if "lot_names" in balance_fields:
                    vals["lot_names"] = ", ".join(sorted(row["lot_names"])) if row["lot_names"] else False
                if "nearest_expiry_date" in balance_fields:
                    vals["nearest_expiry_date"] = row["nearest_expiry_date"]
                if "nearest_alert_date" in balance_fields:
                    vals["nearest_alert_date"] = row["nearest_alert_date"]
                if "last_visit_id" in balance_fields:
                    vals["last_visit_id"] = record.last_visit_id.id if getattr(record, "last_visit_id", False) else False
                if "last_updated_at" in balance_fields:
                    vals["last_updated_at"] = now_value
                if "company_id" in balance_fields:
                    vals["company_id"] = (record.company_id or self.env.company).id

                existing = existing_map.get(product_id)
                if existing:
                    existing.write(vals)
                else:
                    balance_model.create(vals)

            obsolete_balances = existing_balances.filtered(lambda bal: bal.product_id.id not in touched_product_ids)
            if obsolete_balances:
                obsolete_balances.unlink()

        return True

    def get_stock_location(self):
        self.ensure_one()
        return self.stock_location_id

    def has_stock_location(self):
        self.ensure_one()
        return bool(self.stock_location_id)
