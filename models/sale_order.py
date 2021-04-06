# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'


def action_confirm(self):
    raise UserError(_('test'))


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    contenant_id = fields.Many2one(comodel_name='product.product',
                                   string="Contenant",
                                   domain="[('est_contenant', '=', True)]")
    unite_volume = fields.Many2one(comodel_name='uom.uom',
                                   string="Unité de volume",
                                   domain="[('category_id', '=', 'Volume')]")
    unite_poids = fields.Many2one(comodel_name='uom.uom',
                                  string="Unité de poids",
                                  domain="[('category_id', '=', 'Weight')]")
    volume = fields.Integer(string="Volume")
    poids = fields.Integer(string="Poids")
    longueur = fields.Integer(string="Longueur")
    largeur = fields.Integer(string="Largeur")
    hauteur = fields.Integer(string="Hauteur")

    @api.onchange('contenant_id')
    def product_id_change(self):
        if not self.product_id:
            return
        # je vais dans le produit contenant
        volume = self.contenant_id.volume
        # je prends le champ volume
        self.volume = volume

        res = super(SaleOrderLine, self).product_id_change()
        return res

    @api.onchange('longueur','largeur','hauteur')
    def dimensions_change(self):
        calcul_volume = self.longueur * self.largeur * self.hauteur
        self.volume = calcul_volume

    # @api.onchange('product_id')
    # def product_id_change(self):

        # res = super(SaleOrderLine, self).product_id_change()
        # return res
