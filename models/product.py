# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ProductCategory(models.Model):
    _inherit = 'product.category'

    code_revatua = fields.Char(string='Code Revatua', size=64,
                             help='Code Revatua')
