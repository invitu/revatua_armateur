# Copyright 2021 INVITU (https://www.invitu.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import operator
from datetime import date, datetime, timedelta

from odoo import api, models
from odoo.tools import float_is_zero


class DgaeInvoicesReport(models.AbstractModel):
    # Récupérer les voyages VALIDES entre les dates FROM & TO du wizard puis les connaissements VALIDÉs de ces voyages, puis les factures DGAE liées non-payées
    # Récupérer amount_total dans invoice avec payment_state = is not "paid"
    # dans Saleorder, .. remonter  pour récupérer poids, volume, qté(product_uom_qty) avec toatl à faire en boucle .... à voir
    # dans account.move.line, lien avec sale.order.line
    _name = "report.revatua_armateur.dgae_invoices"
    _description = "DGAE Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        invoices = self._get_invoices(data)
        return {
            "doc_model": "dgae.invoices.report.wizard",
            "data": data,
            "invoices": invoices,
        }

    def _get_invoices(self, data):
        """
        Get list of invoices
        """
        invoices = []
        dgae_id = self.env.ref('revatua_connector.partner_dgae').id

        # Select moves within date range
        if (data['date_from']):
            move_ids = self.env['account.move'].search([
                ('partner_id', '=', dgae_id),
                ('invoice_date', '>=', data['date_from']),
                ('invoice_date', '<=', data['date_at']),
                ('state',  '=', 'posted')
            ])
        else:
            move_ids = self.env['account.move'].search([
                ('partner_id', '=', dgae_id),
                ('invoice_date', '<=', data['date_at']),
                ('state',  '=', 'posted')
            ])

        # Get sales associated to selected moves
        sales = self.env['sale.order'].search(
            [('invoice_ids', 'in', move_ids.ids)])

        # Format list of invoices to return
        for sale in sales:
            conn = {}
            conn['numeroVoyage'] = sale.revatua_code
            conn['dateVoyage'] = sale.voyage_id.date_depart
            conn['destination'] = sale.ilearrivee_id.name
            conn['destinataire'] = sale.partner_shipping_id.parent_id.name if sale.partner_shipping_id.parent_id.name else sale.partner_shipping_id.name
            conn['numeroTahiti'] = sale.partner_id.vat
            # montant du sale_order et non de account_move car on considère qu'à chaque sale_order, on a un account_move du même montant
            conn['montant'] = int(sale.amount_untaxed)

            for line in sale.order_line:
                conn['qty'] = int(conn.get('qty', 0) + line.product_uom_qty)
                conn['volume'] = float(conn.get('volume', 0) + line.volume)
                conn['poids'] = float(conn.get('poids', 0) + line.poids)

            partner_id = sale.partner_id.id
            exists = next((i for i, item in enumerate(
                invoices) if item['partner_id'] == partner_id), None)
            if exists is not None:
                invoices[exists]['connaissements'].append(conn)
            else:
                invoice = {}
                invoice['partner_id'] = partner_id
                invoice['expediteur'] = sale.partner_id.parent_id.name if sale.partner_id.parent_id.name else sale.partner_id.name
                invoice['connaissements'] = [conn]
                invoices.append(invoice)

        return invoices
