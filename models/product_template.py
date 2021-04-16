# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    matiere_dangereuse = fields.Boolean(string='Est une matière dangereuse',
                                        help='Cochez cette case s\'il s\'agit d\'une matière dangereuse')
