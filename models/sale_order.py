# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.onchange('partner_id', 'partner_shipping_id')
    def _compute_island(self):
        self.iledepart_id = self.partner_id.state_id or False
        self.ilearrivee_id = self.partner_shipping_id.state_id or False

    iledepart_id = fields.Many2one(comodel_name='res.country.state',
                                   string='Ile de Départ',
                                   domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                                   help='Île de départ (on sélectionne par défaut l\'île de l\'expéditeur)')
    ilearrivee_id = fields.Many2one(comodel_name='res.country.state',
                                    string='Ile d\'arrivée',
                                    domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                                    help='Île d\'arrivée (on sélectionne par défaut l\'île du destinataire)')
    voyage_id = fields.Many2one(comodel_name='voyage', string='Voyage', help='Choisissez le voyage')
    type_facturation = fields.Selection([
        ('expediteur', 'Fret sur l\'expéditeur'),
        ('destinataire', 'Fret sur le destinataire'),
        ('dgae', 'La DGAE')
    ], string='Qui est facturé ?', help='Sélectionnez le type de facturation', default='expediteur')

    def order_is_not_fret(self):
        if self.type_id == self.env.ref('fret.sale.type'):
            return False
        else:
            return True

    @api.onchange('iledepart_id', 'ilearrivee_id')
    def set_domain_for_voyage(self):
        trajet_from_ids = self.env['trajet'].search([
            ('ile_depart_id', '=', self.iledepart_id.id),
            ('date_depart', '>', datetime.now()),
        ]).ids
        trajet_to_ids = self.env['trajet'].search([
            ('ile_arrivee_id', '=', self.ilearrivee_id.id),
            ('date_depart', '>', datetime.now()),
        ]).ids

        voyage_list = self.env['voyage'].search([
            ('trajet_ids', 'in', trajet_from_ids),
            ('trajet_ids', 'in', trajet_to_ids),
            ('state', '=', 'confirm'),
        ]).ids

        res = {}
        res['domain'] = {'voyage_id': [('id', 'in', voyage_list)]}
        return res

    @api.onchange('type_facturation')
    def set_adresse_facturation(self):
        if self.type_facturation == 'expediteur':
            addr = self.partner_id.address_get(['invoice'])
            self.partner_invoice_id = addr['invoice']
        elif self.type_facturation == 'destinataire':
            addr = self.partner_shipping_id.address_get(['invoice'])
            self.partner_invoice_id = addr['invoice']
        else:
            self.partner_invoice_id = self.env.ref('revatua_connector.partner_dgae')


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    contenant_id = fields.Many2one(comodel_name='product.product',
                                   string="Contenant",
                                   groups="revatua_connector.group_revatua_user",
                                   domain="[('est_contenant', '=', True)]")
    unite_volume = fields.Many2one(comodel_name='uom.uom',
                                   string="Unité de volume",
                                   groups="revatua_connector.group_revatua_user",
                                   readonly=True,
                                   default=lambda self: self.env.ref('uom.product_uom_cubic_meter'),
                                   domain=lambda self: [('category_id', '=', self.env.ref('uom.product_uom_categ_vol').id)])
    unite_poids = fields.Many2one(comodel_name='uom.uom',
                                  string="Unité de poids",
                                  groups="revatua_connector.group_revatua_user",
                                  readonly=True,
                                  default=lambda self: self.env.ref('uom.product_uom_kgm'),
                                  domain=lambda self: [('category_id', '=', self.env.ref('uom.product_uom_categ_kgm').id)])
    volume = fields.Float(string='Volume', digits='Volume', help='Volume is computed from dimensions but can be overwritten')
    poids = fields.Float(string='Poids', digits='Stock Weight', help='Weight is always in kg')
    longueur = fields.Integer(string="Longueur", help='Longueur en cm')
    largeur = fields.Integer(string="Largeur", help='Largeur en cm')
    hauteur = fields.Integer(string="Hauteur", help='Hauteur en cm')

    @api.onchange('contenant_id')
    def contenant_id_change(self):
        if not self.contenant_id:
            return
        self.volume = self.contenant_id.volume

    @api.onchange('product_id')
    def product_id_change(self):
        self.ensure_one()
        # Version a l'arrache complet... il faut faire gaffe !!!
        res = super(SaleOrderLine, self).product_id_change()
        if self.order_id.pricelist_id.type == 'fret' and self.product_id:
            date = self.order_id.validity_date or self.order_id.date_order or self._context.get('date') or fields.Datetime.now()
            vals = {}
            iles_ids = (self.order_id.iledepart_id.id, self.order_id.ilearrivee_id.id)
            # on cherche le prix dans la priicelist
            # on shunte la méthode originale et on réécrit dans le contexte Fret
            self.env.cr.execute(
                """
                SELECT
                    item.id
                FROM
                    product_pricelist_item AS item
                WHERE
                    (item.pricelist_id = %s)
                    AND (item.categ_id = %s)
                    AND (item.date_start IS NULL OR item.date_start<=%s)
                    AND (item.date_end IS NULL OR item.date_end>=%s)
                    AND (item.ile1_id in %s)
                    AND (item.ile2_id in %s)
                """,
                (self.order_id.pricelist_id.id, self.product_id.categ_id.id, date, date, iles_ids, iles_ids)
            )

            item_ids = [x[0] for x in self.env.cr.fetchall()]
            pricelistitems = self.env['product.pricelist.item'].browse(item_ids)
            # Ici on considère qu'on a qu'un seul résultat et que le prix est en mode fixed price...etc... bref, on est vraiment dans du specifique
            price = pricelistitems and pricelistitems[0].fixed_price or 0.0
            # Ici on shunte encore tout, on considère que l'unité n'a pas changé...etc bref...
            pricevolume = price * self.volume
            priceweight = price * self.poids / 1000

            vals['price_unit'] = max(pricevolume, priceweight)
            self.update(vals)
        return res

    @api.onchange('product_uom_qty')
    def product_uom_change(self):
        # On prend le dessus, si c'est du fret, on laisse pas le comportement standard....
        if self.order_id.pricelist_id.type == 'fret':
            vals = {}
            vals['price_unit'] = self.price_unit
            self.update(vals)
        else:
            # Si c'est pas du fret, c'est cool, on laisse faire
            super(SaleOrderLine, self).product_uom_change()
        return

    @api.onchange('longueur', 'largeur', 'hauteur')
    def dimensions_change(self):
        self.volume = self.longueur * self.largeur * self.hauteur/1000000

    def _get_display_price(self, product):
        # WIP HERE
        if self.order_id.pricelist_id.type == 'fret':
            product = product.with_context(
                iledepart=self.order_id.iledepart_id,
                ilearrivee=self.order_id.ilearrivee_id
            )
        res = super(SaleOrderLine, self)._get_display_price(product)
        return res
