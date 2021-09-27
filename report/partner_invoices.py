# Copyright 2021 INVITU (https://www.invitu.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import operator
from datetime import date, datetime, timedelta

from odoo import api, models
from odoo.tools import float_is_zero


class PartnerInvoicesReport(models.AbstractModel):
    # Récupérer les voyages VALIDES entre les dates FROM & TO du wizard puis les connaissements VALIDÉs de ces voyages, puis les factures DGAE liées non-payées
    # Récupérer amount_total dans invoice avec payment_state = is not "paid"
    # dans Saleorder, .. remonter  pour récupérer poids, volume, qté(product_uom_qty) avec toatl à faire en boucle .... à voir
    # dans account.move.line, lien avec sale.order.line
    _name = "report.revatua_armateur.partner_invoices"
    _description = "Revatua Client Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        is_dgae = True and (data["partner_id"] == self.env.ref('revatua_connector.partner_dgae').id)
        partner_id = self.env['res.partner'].search([('id', '=', data["partner_id"])])
        categ_list = self._get_categ_list(data)

        return {
            "doc_model": "partner.invoices.report.wizard",
            "data": data,
            "categ_list": categ_list,
            "is_dgae": is_dgae,
            "partner_id": partner_id
        }

    def _get_categ_list(self, data):
        """
        Get list of invoices by categ_id
        """
        categ_list = []
        partner_id = data["partner_id"]

        # Select moves within date range
        if (data['date_from']):
            move_ids = self.env['account.move'].search([
                ('partner_id', '=', partner_id),
                ('invoice_date', '>=', data['date_from']),
                ('invoice_date', '<=', data['date_at']),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('state',  '=', 'posted')
            ])
        else:
            move_ids = self.env['account.move'].search([
                ('partner_id', '=', partner_id),
                ('invoice_date', '<=', data['date_at']),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('state',  '=', 'posted')
            ])

        # Get sales associated to selected moves sorted by date asc
        sales = sorted(
            self.env['sale.order'].search(
                [('invoice_ids', 'in', move_ids.ids)]),
            key=operator.attrgetter('voyage_id.date_depart'))

        for sale in sales:
            # Check if categ_id exists in final list, else create it
            categ_id = sale.order_line[0].product_id.categ_id
            categ_exists = next((i for i, item in enumerate(
                categ_list) if item['categ_id'] == categ_id), None)

            if (categ_exists is not None):
                categ_list[categ_exists]['invoices'] = self._get_invoices(
                    sale, categ_list[categ_exists]['invoices'])
            else:
                new_categ = {}
                new_categ['categ_id'] = categ_id
                new_categ['invoices'] = self._get_invoices(
                    sale, [])
                categ_list.append(new_categ)

        return categ_list

    def _get_invoices(self, sale, invoices):
        """
        Return invoice's list
        """
        conn = self._get_conn_values(sale)
        # Check if a partner_id's list already exists in invoice's list, else create it
        partner_id = sale.partner_id.id
        exists = next((i for i, item in enumerate(
            invoices) if item['partner_id'] == partner_id), None)

        if (exists is not None):
            invoices[exists]['connaissements'].append(conn)
        else:
            invoice = {}
            invoice['partner_id'] = partner_id
            invoice['expediteur'] = sale.partner_id.parent_id.name if sale.partner_id.parent_id.name else sale.partner_id.name
            invoice['connaissements'] = [conn]
            invoices.append(invoice)

        return invoices

    def _get_conn_values(self, sale):
        """
        Return an object with the connaissement's values
        """
        conn = {}
        conn['dateFacture'] = sale.invoice_ids.invoice_date
        conn['numeroFacture'] = sale.invoice_ids.name
        conn['numeroVoyage'] = sale.revatua_code
        conn['dateVoyage'] = sale.voyage_id.date_depart
        conn['destination'] = sale.ilearrivee_id.name
        conn['destinataire'] = sale.partner_shipping_id.parent_id.name if sale.partner_shipping_id.parent_id.name else sale.partner_shipping_id.name
        conn['numeroTahiti'] = sale.partner_shipping_id.parent_id.vat and sale.partner_shipping_id.parent_id.vat or sale.partner_shipping_id.vat
        for line in sale.order_line:
            conn['qty'] = conn['qty'] + float(line.product_uom_qty) if 'qty' in conn else float(line.product_uom_qty)
            conn['volume'] = conn['volume'] + float(line.volume) if 'volume' in conn else float(line.volume)
            conn['poids'] = conn['poids'] + float(line.poids) if 'poids' in conn else float(line.poids)
        # taking sale_order's value instead of account_move for we consider each sale_order having the same value as account_move
        conn['montant'] = float(sale.amount_untaxed)

        return conn
