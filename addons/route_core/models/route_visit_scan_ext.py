from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    # Compatibility fields for any older inherited views
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

    def _get_product_from_scanned_barcode(self, barcode):
        self.ensure_one()

        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Please enter or scan a barcode first."))

        product = self.env["product.product"].search(
            [("barcode", "=", barcode)],
            limit=1,
        )

        if not product:
            raise UserError(_("No product was found with barcode '%s'.") % barcode)

        return product

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

    def _prepare_visit_line_from_scan(self, product):
        self.ensure_one()

        return {
            "visit_id": self.id,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "previous_qty": 0.0,
            "counted_qty": 1.0,
            "unit_price": product.lst_price or 0.0,
            "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
        }

    def _process_scanned_barcode(self, barcode):
        self.ensure_one()

        RouteVisitLine = self.env["route.visit.line"]

        if self.visit_process_state not in ("checked_in", "counting", "reconciled"):
            raise UserError(
                _(
                    "Barcode scanning is only allowed when the visit is Checked In, Counting, or Reconciled."
                )
            )

        if not self.vehicle_id:
            raise UserError(_("Please set a vehicle before scanning."))

        if not self.vehicle_id.stock_location_id:
            raise UserError(_("The selected vehicle does not have a Vehicle Stock Location."))

        self._sync_source_location_from_vehicle()

        if not self.source_location_id:
            raise UserError(_("No source location is available for this visit."))

        barcode = (barcode or "").strip()
        product = self._get_product_from_scanned_barcode(barcode)

        if not self._is_product_available_in_vehicle(product):
            raise UserError(
                _("Product '%s' is not currently available in the van stock.")
                % product.display_name
            )

        line = self._find_visit_line_for_product(product)

        if line:
            line.write({
                "counted_qty": (line.counted_qty or 0.0) + 1.0,
                "vehicle_available_qty": self._get_vehicle_available_qty_for_scan_product(product),
            })
        else:
            line = RouteVisitLine.create([self._prepare_visit_line_from_scan(product)])

        self.last_scanned_barcode = barcode

        if self.visit_process_state == "checked_in":
            self.visit_process_state = "counting"

        return line

    def action_scan_barcode_input(self):
        for rec in self:
            rec._process_scanned_barcode(rec.scan_barcode_input)
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
            },
        }
