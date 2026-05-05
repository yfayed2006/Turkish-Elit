import re
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisitWhatsappShareWizard(models.TransientModel):
    _name = "route.visit.whatsapp.share.wizard"
    _description = "Route Visit WhatsApp Share Wizard"

    visit_id = fields.Many2one("route.visit", string="Visit", required=True, readonly=True)
    phone_number = fields.Char(string="WhatsApp Number", required=True)
    message_preview = fields.Text(string="Message Preview", readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id") or self.env.context.get("active_id")
        visit = self.env["route.visit"].browse(visit_id).exists() if visit_id else self.env["route.visit"]
        if visit:
            vals.setdefault("visit_id", visit.id)
            vals.setdefault("message_preview", visit._route_build_whatsapp_share_message_preview())
        return vals

    @staticmethod
    def _normalize_whatsapp_number(number):
        return re.sub(r"\D", "", number or "")

    def action_share_receipt(self):
        self.ensure_one()
        phone = self._normalize_whatsapp_number(self.phone_number)
        if not phone:
            raise UserError(_("Please enter a valid WhatsApp number."))
        visit = self.visit_id
        if not visit:
            raise UserError(_("No visit is linked to this share request."))
        if visit._is_direct_sales_stop():
            pdf_url = visit._get_direct_stop_receipt_public_url()
            message = visit._build_direct_stop_whatsapp_message(pdf_url=pdf_url)
        else:
            pdf_url = visit._get_consignment_receipt_public_url()
            message = visit._build_consignment_whatsapp_message(pdf_url=pdf_url)
        return {
            "type": "ir.actions.act_url",
            "url": "https://wa.me/%s?text=%s" % (phone, quote(message, safe="")),
            "target": "new",
        }
