# Copyright 2021 INVITU (https://www.invitu.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class PartnerInvoicesWizard(models.TransientModel):
    """Partner invoices report wizard."""

    _name = "partner.invoices.report.wizard"
    _description = "Partner Invoices Report Wizard"

    date_at = fields.Date(required=True, default=fields.Date.context_today)
    date_from = fields.Date(string="Date From")

    def _default_partner(self):
        return self.env.ref('revatua_connector.partner_dgae').id

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        default=_default_partner)

    def _print_report(self, report_type):
        self.ensure_one()

        data = self._prepare_report_partner_invoices()
        report_name = "revatua_armateur.partner_invoices"

        return (
            self.env["ir.actions.report"]
            .search(
                [("report_name", "=", report_name),
                 ("report_type", "=", report_type)],
                limit=1,
            )
            .report_action(self, data=data)
        )

    def button_export_html(self):
        self.ensure_one()
        report_type = "qweb-html"
        return self._print_report(report_type)

    def button_export_pdf(self):
        self.ensure_one()
        report_type = "qweb-pdf"
        return self._print_report(report_type)

    def _prepare_report_partner_invoices(self):
        self.ensure_one()

        return {
            "date_at": self.date_at,
            "date_from": self.date_from or False,
            "partner_id": self.partner_id.id,
        }
