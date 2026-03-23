from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    scan_barcode_input = fields.Char(
        string="Scan Barcode",
        copy=False,
    )
    last_scanned_barcode = fields.Char(
        string="Last Scanned Barcode",
        readonly=True,
        copy=False,
    )

    def _get_scan_source_location(self):
        self.ensure_one()
        return self.source_location_id or self.vehicle_id.stock_location_id

    def _get_scan_outlet_location(self):
        self.ensure_one()
        return self.outlet_id.stock_location_id

    def _get_scan_allowed_locations(self):
        self.ensure_one()
        locations = self.env["stock.location"]
        source_location = self._get_scan_source_location()
        outlet_location = self._get_scan_outlet_location()

        if source_location:
            locations |= source_location
        if outlet_location:
            locations |= outlet_location

        return locations

    def _get_lot_expiry_date(self, lot):
        self.ensure_one()
        if not lot:
            return False
        for field_name in ("expiration_date", "life_date", "use_date"):
            if field_name in lot._fields and lot[field_name]:
                return fields.Date.to_date(lot[field_name])
        return False

    def _find_available_lot_from_code(self, lot_code):
        self.ensure_one()
        lot_code = (lot_code or "").strip()
        if not lot_code:
            raise UserError(_("Please scan or enter a lot/serial code first."))

        allowed_locations = self._get_scan_allowed_locations()
        if not allowed_locations:
            raise UserError(_("No stock location is available for this visit."))

        Lot = self.env["stock.lot"]
        Quant = self.env["stock.quant"]

        lot = Lot.search([("name", "=", lot_code)], limit=1)
        if not lot and "barcode" in Lot._fields:
            lot = Lot.search([("barcode", "=", lot_code)], limit=1)

        if not lot:
            raise UserError(_("No lot/serial was found with code '%s'.") % lot_code)

        quant = Quant.search(
            [
                ("location_id", "child_of", allowed_locations.ids),
                ("lot_id", "=", lot.id),
                ("quantity", ">", 0),
            ],
            limit=1,
        )
        if not quant:
            raise UserError(
                _("Lot '%s' is not currently available in the van stock or outlet stock.")
                % lot.display_name
            )
        return lot

    def _find_available_lots_for_product(self, product):
        self.ensure_one()
        allowed_locations = self._get_scan_allowed_locations()
        if not allowed_locations or not product:
            return self.env["stock.lot"]

        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", allowed_locations.ids),
                ("product_id", "=", product.id),
                ("lot_id", "!=", False),
                ("quantity", ">", 0),
            ]
        )
        return quants.mapped("lot_id")

    def _get_packaging_qty_field_name(self, record):
        self.ensure_one()
        if not record:
            return False

        candidate_fields = (
            "qty",
            "quantity",
            "contained_qty",
            "contained_quantity",
            "contained_uom_qty",
            "product_qty",
            "pack_qty",
            "qty_per_pack",
            "unit_qty",
            "units",
            "units_count",
            "factor_inv",
        )
        for field_name in candidate_fields:
            if field_name in record._fields:
                return field_name
        return False

    def _get_packaging_uom_field_name(self, record):
        self.ensure_one()
        if not record:
            return False

        candidate_fields = (
            "uom_id",
            "unit_id",
            "contained_uom_id",
            "product_uom_id",
            "reference_uom_id",
            "reference_unit_id",
        )
        for field_name in candidate_fields:
            if field_name in record._fields:
                return field_name
        return False

    def _get_packaging_qty(self, record):
        self.ensure_one()
        if not record:
            return 0.0
        qty_field = self._get_packaging_qty_field_name(record)
        if not qty_field:
            return 0.0
        return record[qty_field] or 0.0

    def _get_packaging_uom(self, record, product=False):
        self.ensure_one()
        if not record:
            return product.uom_id if product else False

        uom_field = self._get_packaging_uom_field_name(record)
        if uom_field and record[uom_field]:
            return record[uom_field]

        return product.uom_id if product else False

    def _iter_related_records(self, rec):
        self.ensure_one()
        if not rec:
            return []

        related_records = []
        for field_name, field in rec._fields.items():
            try:
                field_type = getattr(field, "type", None)
                if field_type not in ("many2one", "one2many", "many2many"):
                    continue

                value = rec[field_name]
                if not value:
                    continue

                if field_type == "many2one":
                    related_records.append(value)
                else:
                    related_records.extend(value)
            except Exception:
                continue

        return related_records

    def _is_packaging_candidate_record(self, rec):
        self.ensure_one()
        if not rec:
            return False

        if self._get_packaging_qty_field_name(rec):
            return True

        model_name = getattr(rec, "_name", "") or ""
        if "pack" in model_name or "uom" in model_name:
            for field_name in ("package_type_id", "package_type", "barcode_ids", "barcodes"):
                if field_name in rec._fields:
                    return True

        return False

    def _search_child_barcode_records(self, ChildModel, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return ChildModel.browse()

        candidate_fields = []
        for field_name in ("barcode", "name", "code", "value"):
            field = ChildModel._fields.get(field_name)
            if field and getattr(field, "type", None) in ("char", "text"):
                candidate_fields.append(field_name)

        for field_name in candidate_fields:
            try:
                recs = ChildModel.search([(field_name, "=", barcode)], limit=5)
                if recs:
                    return recs
            except Exception:
                continue

        return ChildModel.browse()

    def _find_packaging_record_in_model(self, model_name, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode or model_name not in self.env:
            return False

        Model = self.env[model_name]

        direct_barcode_field = Model._fields.get("barcode")
        if direct_barcode_field and getattr(direct_barcode_field, "type", None) in ("char", "text"):
            try:
                rec = Model.search([("barcode", "=", barcode)], limit=1)
                if rec and self._is_packaging_candidate_record(rec):
                    return rec
            except Exception:
                pass

        for field_name, field in Model._fields.items():
            field_type = getattr(field, "type", None)
            relation = getattr(field, "comodel_name", False)
            if field_type not in ("one2many", "many2many") or not relation or relation not in self.env:
                continue

            if field_name not in ("barcode_ids", "barcodes") and "barcode" not in field_name:
                continue

            ChildModel = self.env[relation]
            child_records = self._search_child_barcode_records(ChildModel, barcode)
            if not child_records:
                continue

            try:
                if field_type == "one2many":
                    inverse_name = getattr(field, "inverse_name", False)
                    if inverse_name:
                        rec = child_records[0][inverse_name]
                        if rec:
                            return rec
                else:
                    rec = Model.search([(field_name, "in", child_records.ids)], limit=1)
                    if rec:
                        return rec
            except Exception:
                continue

        return False

    def _resolve_packaging_product(self, packaging):
        self.ensure_one()
        if not packaging:
            return False

        if "product_id" in packaging._fields and packaging.product_id:
            return packaging.product_id

        if "product_tmpl_id" in packaging._fields and packaging.product_tmpl_id:
            template = packaging.product_tmpl_id
            if "product_variant_id" in template._fields and template.product_variant_id:
                return template.product_variant_id
            if "product_variant_ids" in template._fields and template.product_variant_ids:
                return template.product_variant_ids[:1]

        for Model in (self.env["product.product"], self.env["product.template"]):
            for field_name, field in Model._fields.items():
                relation = getattr(field, "comodel_name", False)
                field_type = getattr(field, "type", None)
                if relation != packaging._name or field_type not in ("many2one", "one2many", "many2many"):
                    continue

                try:
                    if field_type == "many2one":
                        rec = Model.search([(field_name, "=", packaging.id)], limit=1)
                    else:
                        rec = Model.search([(field_name, "in", packaging.ids)], limit=1)
                except Exception:
                    rec = Model.browse()

                if not rec:
                    continue

                if Model._name == "product.product":
                    return rec[:1]

                template = rec[:1]
                if "product_variant_id" in template._fields and template.product_variant_id:
                    return template.product_variant_id
                if "product_variant_ids" in template._fields and template.product_variant_ids:
                    return template.product_variant_ids[:1]

        return False

    def _find_product_packaging_by_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        preferred_models = [
            "product.packaging",
            "uom.uom",
        ]

        for model_name in preferred_models:
            packaging = self._find_packaging_record_in_model(model_name, barcode)
            if packaging:
                product = self._resolve_packaging_product(packaging)
                if product:
                    return {
                        "packaging": packaging,
                        "product": product,
                    }

        for model_name in self.env:
            if model_name in preferred_models:
                continue
            try:
                Model = self.env[model_name]
                if model_name.startswith("route."):
                    continue
                if not any(
                    field_name in Model._fields
                    for field_name in (
                        "qty",
                        "quantity",
                        "contained_qty",
                        "factor_inv",
                        "barcode_ids",
                        "barcodes",
                        "package_type_id",
                    )
                ):
                    continue

                packaging = self._find_packaging_record_in_model(model_name, barcode)
                if not packaging:
                    continue

                product = self._resolve_packaging_product(packaging)
                if product:
                    return {
                        "packaging": packaging,
                        "product": product,
                    }
            except Exception:
                continue

        return False

    def _find_route_product_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            return False

        if "route.product.barcode" not in self.env:
            return False

        Barcode = self.env["route.product.barcode"]

        domain = [("barcode", "=", barcode)]
        if "active" in Barcode._fields:
            domain.append(("active", "=", True))
        if "company_id" in Barcode._fields:
            domain.append(("company_id", "=", self.company_id.id))

        rec = Barcode.search(domain, limit=1)
        if rec:
            return rec

        domain = [("barcode", "=", barcode)]
        if "active" in Barcode._fields:
            domain.append(("active", "=", True))

        rec = Barcode.search(domain, limit=1)
        if rec:
            return rec

        rec = Barcode.search([("barcode", "=", barcode)], limit=1)
        if rec:
            return rec

        return False

    def _resolve_scanned_barcode(self, barcode):
        self.ensure_one()
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please enter or scan a barcode first."))

        product = self.env["product.product"].search(
            [("barcode", "=", barcode)],
            limit=1,
        )
        if product:
            return {
                "product": product,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "default_scan_qty": 1.0,
                "default_scanned_uom": product.uom_id,
            }

        packaging_info = self._find_product_packaging_by_barcode(barcode)
        if packaging_info:
            packaging = packaging_info["packaging"]
            product = packaging_info["product"]
            packaging_qty = self._get_packaging_qty(packaging) or 0.0
            if packaging_qty <= 0:
                raise UserError(
                    _(
                        "Packaging '%(packaging)s' was found for barcode '%(barcode)s', but its quantity is not configured correctly."
                    )
                    % {
                        "packaging": packaging.display_name,
                        "barcode": barcode,
                    }
                )

            packaging_uom = self._get_packaging_uom(packaging, product) or product.uom_id

            return {
                "product": product,
                "scan_type": "box",
                "scan_type_label": _("Box Barcode"),
                "packaging": packaging,
                "default_scan_qty": packaging_qty,
                "default_scanned_uom": packaging_uom,
            }

        route_barcode = self._find_route_product_barcode(barcode)
        if route_barcode and route_barcode.product_id:
            barcode_type = "piece"
            if "barcode_type" in route_barcode._fields and route_barcode.barcode_type:
                barcode_type = route_barcode.barcode_type

            if barcode_type == "box":
                raise UserError(
                    _(
                        "Barcode '%(barcode)s' is marked as a box barcode in Route Product Barcodes, "
                        "but no matching Odoo packaging was found.\n\n"
                        "Please define this barcode on the product packaging/unit in Odoo first."
                    )
                    % {"barcode": barcode}
                )

            qty_in_base_uom = 1.0
            if "qty_in_base_uom" in route_barcode._fields and route_barcode.qty_in_base_uom:
                qty_in_base_uom = route_barcode.qty_in_base_uom

            return {
                "product": route_barcode.product_id,
                "scan_type": "piece",
                "scan_type_label": _("Piece Barcode"),
                "packaging": False,
                "default_scan_qty": qty_in_base_uom,
                "default_scanned_uom": route_barcode.product_id.uom_id,
            }

        raise UserError(_("No product was found with barcode '%s'.") % barcode)

    def _is_product_tracked_by_lot(self, product):
        self.ensure_one()
        if not product:
            return False
        tracking_value = getattr(product, "tracking", "none") or "none"
        return tracking_value in ("lot", "serial")

    def _resolve_product_active_lot(self, product, active_lot=False):
        self.ensure_one()
        if not product:
            return False

        if not self._is_product_tracked_by_lot(product):
            return False

        if active_lot:
            if active_lot.product_id != product:
                raise UserError(
                    _(
                        "The scanned product does not belong to the active lot.\n\n"
                        "Active Lot: %(lot)s\n"
                        "Lot Product: %(lot_product)s\n"
                        "Scanned Product: %(barcode_product)s\n\n"
                        "Please clear the current lot first, then scan/select the correct lot for this product."
                    )
                    % {
                        "lot": active_lot.display_name,
                        "lot_product": active_lot.product_id.display_name,
                        "barcode_product": product.display_name,
                    }
                )
            return active_lot

        available_lots = self._find_available_lots_for_product(product)
        if not available_lots:
            raise UserError(
                _("Tracked product '%s' has no available lot in the van stock or outlet stock.")
                % product.display_name
            )

        if len(available_lots) == 1:
            return available_lots[:1]

        raise UserError(
            _("Product '%s' has more than one available lot in stock. Please scan/select the lot first.")
            % product.display_name
        )

    def _is_product_available_in_vehicle(self, product):
        self.ensure_one()
        source_location = self._get_scan_source_location()
        if not source_location or not product:
            return False

        quant = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", source_location.id),
                ("product_id", "=", product.id),
                ("quantity", ">", 0),
            ],
            limit=1,
        )
        return bool(quant)

    def _get_vehicle_available_qty_for_scan_product(self, product):
        self.ensure_one()
        source_location = self._get_scan_source_location()
        if not source_location or not product:
            return 0.0

        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", source_location.id),
                ("product_id", "=", product.id),
            ]
        )
        return sum(quants.mapped("quantity"))

    def _find_visit_line_for_product(self, product):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.product_id == product)[:1]

    def _prepare_visit_line_from_scan(self, product, counted_increase):
        self.ensure_one()
        return {
            "visit_id": self.id,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "previous_qty": 0.0,
            "counted_qty": counted_increase,
            "unit_price": product.lst_price or 0.0,
            "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
        }

    def _get_scan_counted_increase(self, product, scan_qty=1.0, scanned_uom=False):
        self.ensure_one()
        if not product:
            raise UserError(_("Product is required."))
        if scan_qty <= 0:
            raise UserError(_("Quantity must be greater than zero."))

        base_uom = product.uom_id
        scanned_uom = scanned_uom or base_uom

        try:
            return scanned_uom._compute_quantity(scan_qty, base_uom)
        except Exception as e:
            raise UserError(
                _("Could not convert the scanned quantity from the selected UoM to the product base UoM.\n\n%s")
                % str(e)
            )

    def _process_scanned_barcode(
        self,
        barcode,
        scan_qty=1.0,
        scanned_uom=False,
        active_lot=False,
    ):
        self.ensure_one()
        RouteVisitLine = self.env["route.visit.line"]

        if self.visit_process_state not in ("checked_in", "counting", "reconciled"):
            raise UserError(
                _("Barcode scanning is only allowed when the visit is Checked In, Counting, or Reconciled.")
            )

        if not self.vehicle_id:
            raise UserError(_("Please set a vehicle before scanning."))
        if not self.vehicle_id.stock_location_id:
            raise UserError(_("The selected vehicle does not have a Vehicle Stock Location."))

        self._sync_source_location_from_vehicle()
        if not self.source_location_id:
            raise UserError(_("No source location is available for this visit."))

        scan_info = self._resolve_scanned_barcode(barcode)
        product = scan_info["product"]

        effective_scan_qty = scan_qty
        effective_scanned_uom = scanned_uom or scan_info.get("default_scanned_uom")

        if scan_info.get("scan_type") == "box":
            effective_scan_qty = scan_info.get("default_scan_qty") or 1.0
            effective_scanned_uom = product.uom_id

        counted_increase = self._get_scan_counted_increase(
            product,
            scan_qty=effective_scan_qty,
            scanned_uom=effective_scanned_uom,
        )

        if not self._is_product_available_in_vehicle(product):
            raise UserError(
                _("Product '%s' is not currently available in the van stock.")
                % product.display_name
            )

        resolved_lot = self._resolve_product_active_lot(product, active_lot=active_lot)
        resolved_expiry_date = self._get_lot_expiry_date(resolved_lot) if resolved_lot else False

        line = self._find_visit_line_for_product(product)
        if line:
            line.write(
                {
                    "counted_qty": (line.counted_qty or 0.0) + counted_increase,
                    "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
                }
            )
        else:
            line = RouteVisitLine.create([self._prepare_visit_line_from_scan(product, counted_increase)])

        self.last_scanned_barcode = (barcode or "").strip()

        if self.visit_process_state == "checked_in":
            self.visit_process_state = "counting"

        return {
            "line": line,
            "product": product,
            "scan_type": scan_info["scan_type"],
            "scan_type_label": scan_info["scan_type_label"],
            "counted_increase": counted_increase,
            "base_uom": product.uom_id,
            "used_uom": effective_scanned_uom or product.uom_id,
            "resolved_lot": resolved_lot,
            "resolved_expiry_date": resolved_expiry_date,
            "packaging": scan_info.get("packaging"),
            "effective_scan_qty": effective_scan_qty,
        }

    def action_scan_barcode_input(self):
        for rec in self:
            rec._process_scanned_barcode(rec.scan_barcode_input, scan_qty=1.0)
            rec.scan_barcode_input = False
        return True

    def action_open_scan_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
                "default_quantity": 1.0,
                "default_scan_mode": "count",
            },
        }
