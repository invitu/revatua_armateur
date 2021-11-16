# Copyright 2021 INVITU (https://www.invitu.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import operator
from datetime import date, datetime, timedelta, time

from odoo import api, models
from odoo.tools import float_is_zero
import pytz


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
        move_ids = self.env['account.move'].search([
            '|',
            ('partner_id', '=', partner_id),
            ('partner_id', 'child_of', partner_id),
            ('payment_state', 'in', ('not_paid', 'partial')),
            ('state',  '=', 'posted')
        ])

        # Get sales associated to selected moves sorted by date asc
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        if (data['date_from']):
            sales = sorted(
                self.env['sale.order'].search(
                    [
                        ('invoice_ids', 'in', move_ids.ids),
                        ('voyage_id.date_depart', '>=', datetime.combine(datetime.strptime(
                            data['date_from'], '%Y-%m-%d'), time.min).replace(tzinfo=timezone).astimezone(pytz.timezone('UTC'))),
                        ('voyage_id.date_depart', '<=', datetime.combine(datetime.strptime(
                            data['date_at'], '%Y-%m-%d'), time.max).replace(tzinfo=timezone).astimezone(pytz.timezone('UTC'))),
                        ('type_id', '=', self.env.ref('revatua_armateur.fret_sale_type').id),
                    ]),
                key=operator.attrgetter('voyage_id.date_depart'))
        else:
            sales = sorted(
                self.env['sale.order'].search(
                    [
                        ('invoice_ids', 'in', move_ids.ids),
                        ('voyage_id.date_depart', '<=', datetime.combine(datetime.strptime(
                            data['date_at'], '%Y-%m-%d'), time.max).replace(tzinfo=timezone).astimezone(pytz.timezone('UTC'))),
                        ('type_id', '=', self.env.ref('revatua_armateur.fret_sale_type').id),
                    ]),
                key=operator.attrgetter('voyage_id.date_depart'))

        for sale in sales:
            # Note that there must be only one invoice related to a sale_order
            associated_invoice_id = next(move_id for move_id in move_ids if (move_id.id in sale.invoice_ids.ids))
            # Check if categ_id exists in final list, else create it
            categ_id = sale.order_line[0].product_id.categ_id
            categ_exists = next((i for i, item in enumerate(
                categ_list) if item['categ_id'] == categ_id), None)

            if (categ_exists is not None):
                categ_list[categ_exists]['invoices'] = self._get_invoices(
                    sale, categ_list[categ_exists]['invoices'], associated_invoice_id)
            else:
                new_categ = {}
                new_categ['categ_id'] = categ_id
                new_categ['invoices'] = self._get_invoices(
                    sale, [], associated_invoice_id)
                categ_list.append(new_categ)

        return categ_list

    def _get_invoices(self, sale, invoices, invoice_id):
        """
        Return invoice's list
        """
        conn = self._get_conn_values(sale)
        conn['dateFacture'] = invoice_id.invoice_date
        conn['numeroFacture'] = invoice_id.name
        conn['montant'] = float(invoice_id.amount_total)
        if (invoice_id.partner_id == self.env.ref('revatua_connector.partner_dgae')):
            port_tax = next((line.price_subtotal for line in invoice_id.invoice_line_ids
                             if line.product_id == self.env.ref('revatua_armateur.port_tax')), 0.0)
            conn['montant'] -= port_tax

        # Check if a partner_id's list already exists in invoice's list, else create it
        partner_id = sale.partner_id.id
        exists = next((i for i, item in enumerate(
            invoices) if item['partner_id'] == partner_id), None)

        if (exists is not None):
            invoices[exists]['connaissements'].append(conn)
        else:
            invoice = {}
            invoice['partner_id'] = partner_id
            invoice['expediteur'] = sale.partner_id.parent_id.name and sale.partner_id.parent_id.name or sale.partner_id.name
            invoice['connaissements'] = [conn]
            invoices.append(invoice)

        return invoices

    def _get_conn_values(self, sale):
        """
        Return an object with the connaissement's values
        """
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        conn = {}
        conn['numeroVoyage'] = sale.revatua_code
        conn['dateVoyage'] = sale.voyage_id.date_depart.astimezone(timezone)
        conn['destination'] = sale.ilearrivee_id.name
        conn['destinataire'] = sale.partner_shipping_id.parent_id.name and sale.partner_shipping_id.parent_id.name or sale.partner_shipping_id.name
        conn['numeroTahiti'] = sale.partner_shipping_id.parent_id.vat and sale.partner_shipping_id.parent_id.vat or sale.partner_shipping_id.vat
        for line in sale.order_line:
            if line.product_id.is_fret:
                conn['qty'] = ('qty' in conn) and (
                    conn['qty'] + float(line.product_uom_qty)) or float(line.product_uom_qty)
                conn['volume'] = ('volume' in conn) and (
                    conn['volume'] + float(line.volume)) or float(line.volume)
                conn['poids'] = ('poids' in conn) and (
                    conn['poids'] + float(line.poids)) or float(line.poids)

        return conn
