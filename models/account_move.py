# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round as round


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = "account.move.line"

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
        res = super(AccountMoveLine, self)._get_price_total_and_subtotal_model(price_unit=price_unit, quantity=quantity, discount=discount, currency=currency, product=product, partner=partner, taxes=taxes, move_type=move_type)
        if self.move_id.sale_type_id == self.env.ref('revatua_armateur.fret_sale_type'):
            subtotal = round(quantity * price_unit * (1 - (discount or 0.0 / 100.0)), precision_digits=0, rounding_method='DOWN')
            res['price_total'] = res['price_subtotal'] = subtotal
        return res
