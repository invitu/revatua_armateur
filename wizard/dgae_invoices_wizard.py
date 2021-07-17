# Author: Damien Crier, Andrea Stirpe, Kevin Graveman, Dennis Sluijk
# Author: Julien Coux
# Copyright 2016 Camptocamp SA, Onestein B.V.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class DgaeInvoicesWizard(models.TransientModel):
    """DGAE invoices report wizard."""

    _name = "dgae.invoices.report.wizard"
    _description = "DGAE Invoices Report Wizard"

    date_at = fields.Date(required=True, default=fields.Date.context_today)
    date_from = fields.Date(string="Date From")

    def _print_report(self, report_type):
        self.ensure_one()

        data = self._prepare_report_dgae_invoices()
        report_name = "revatua_armateur.dgae_invoices"

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

    def _prepare_report_dgae_invoices(self):
        self.ensure_one()

        return {
            "date_at": self.date_at,
            "date_from": self.date_from or False,
        }
