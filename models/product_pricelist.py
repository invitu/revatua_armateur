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

    def action_view_related_pricelist_items(self):
        self.ensure_one()
        domain = [('pricelist_id', '=', self.id)]
        action = {
            'name': _('Pricelist Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.pricelist.item',
            'view_type': 'list',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'default_pricelist_id': self.id},
        }
        return action


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    ile1_id = fields.Many2one(comodel_name='res.country.state',
                              domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                              string='Ile 1', help='Select the Ile 1')
    ile2_id = fields.Many2one(comodel_name='res.country.state',
                              domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                              string='Ile 2', help='Select the Ile 2')
    official_price = fields.Boolean(string='Official Price', default=False)
