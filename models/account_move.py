# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round as round


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = "account.move"

    def _add_minimum_fret_move_line(self):
        """ Search the orders that are concerned by the minimum fret amount
            Then we add an invoice line for compensation
        """
        # we get minimum fret price
        minimum_fret_price = float(self.env['ir.config_parameter'].sudo(
        ).get_param('revatua_armateur.minimum_fret_price'))
        # A partir des factures, on remonte à la liste des sale order minimum fret
        moves = self.filtered(lambda i: i.move_type == 'out_invoice' and i.state == 'draft')
        for move in moves:
            minimum_fret_orders = []
            for invoice_line in move.invoice_line_ids:
                sale_line_fret_ids = invoice_line.sale_line_ids.filtered(lambda sol: sol.order_id.type_id == self.env.ref('revatua_armateur.fret_sale_type') and sol.order_id.amount_untaxed == minimum_fret_price)
                if sale_line_fret_ids:
                    for sale_line_fret in sale_line_fret_ids:
                        minimum_fret_orders.append(sale_line_fret.order_id)
            # Si we have sale orders, we add the correction move line in the move
            if minimum_fret_orders:
                minimum_fret_orders = set(minimum_fret_orders)
                correction = 0.0
                for order in minimum_fret_orders:
                    correction += order.correction
                correction_values = {
                    'product_id': self.env.ref('revatua_armateur.correction_minimum_fret').id,
                    'price_unit': correction,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                }
                move.sudo().write({'invoice_line_ids': [(0, 0, correction_values)]})


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = "account.move.line"

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
        res = super(AccountMoveLine, self)._get_price_total_and_subtotal_model(price_unit=price_unit, quantity=quantity, discount=discount, currency=currency, product=product, partner=partner, taxes=taxes, move_type=move_type)
        if self.move_id.sale_type_id == self.env.ref('revatua_armateur.fret_sale_type'):
            subtotal = round(quantity * price_unit * (1 - (discount / 100.0 or 0.0)), precision_digits=0, rounding_method='DOWN')
            res['price_total'] = res['price_subtotal'] = subtotal
        return res
