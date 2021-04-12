# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _


class Pricelist(models.Model):
    _inherit = "product.pricelist"

    type = fields.Selection(
        selection=[
            ('standard', 'Standard'),
            ('fret', 'Fret'),
        ],
        default='standard',
        string='Type',
        help='Select the pricelist type')

    # def _compute_price_rule_get_items(self, products_qty_partner, date, uom_id, prod_tmpl_ids, prod_ids, categ_ids):
        # self.ensure_one()
        # res = super(Pricelist, self)._compute_price_rule_get_items(products_qty_partner, date, uom_id, prod_tmpl_ids, prod_ids, categ_ids)
        # if self.type == 'fret':
            # __import__('pdb').set_trace()
            # print(res)
            # on recupere la sale_order concernée
            # order_ids = self.env.context.get('active_ids', [])
            # order_rec = self.env['sale.order'].browse(order_ids)
            # on recup ile depart et ile arrivee
            # on filtre la liste en fonction du depart/arrivée
            # on renvoit la nouvelle liste

            # return res
        # else:
            # return res



class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    ile1_id = fields.Many2one(comodel_name='res.country.state',
                              domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                              string='Ile 1', help='Select the Ile 1')
    ile2_id = fields.Many2one(comodel_name='res.country.state',
                              domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                              string='Ile 2', help='Select the Ile 2')
