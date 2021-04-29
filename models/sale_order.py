# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime
import base64


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
        ('dgae', 'La DGAE'),
        ('aventure', 'En Aventure')
    ], string='Qui est facturé ?', help='Sélectionnez le type de facturation', default='expediteur')
    revatua_code = fields.Char(string='Code Revatua', size=64,)
    id_revatua = fields.Char(string='ID Revatua', size=64,)
    version = fields.Char(string='Revatua Version', size=64,)

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

    def _get_order_lines(self):
        lines = []
        for line in self.order_line:
            if not line.official_price:
                lines.append({
                    "nbColis": line.product_uom_qty,
                    "contenant": line.contenant_id.name,
                    "description": line.name,
                    "codeSH": line.product_id.nomenclaturepfcustoms_id.name,
                    "codeTarif": line.product_id.categ_id.code_revatua,
                    "stockage": "CALE",
                    "poids": line.poids,
                    "unitePoids": line.unite_poids.code_revatua,
                    "volume": line.volume,
                    "uniteVolume": line.unite_volume.code_revatua,
                    "montantLibre": line.price_subtotal,
                    "matieredangereuse": "true" and line.product_id.matiere_dangereuse or "false",
                })
            else:
                lines.append({
                    "nbColis": line.product_uom_qty,
                    "contenant": line.contenant_id.name,
                    "description": line.name,
                    "codeSH": line.product_id.nomenclaturepfcustoms_id.name,
                    "codeTarif": line.product_id.categ_id.code_revatua,
                    "stockage": "CALE",
                    "poids": line.poids,
                    "unitePoids": line.unite_poids.code_revatua,
                    "volume": line.volume,
                    "uniteVolume": line.unite_volume.code_revatua,
                    "matieredangereuse": "true" and line.product_id.matiere_dangereuse or "false",
                })

        return lines

    def _get_expediteur(self):
        expediteur = {}
        for order in self:
            expediteur['denomination'] = order.partner_id.name
            if order.partner_id.mobile or order.partner_id.phone:
                expediteur['telephone'] = order.partner_id.mobile or order.partner_id.phone
            if order.partner_id.email:
                expediteur['mail'] = order.partner_id.email
            if order.partner_id.vat:
                expediteur['numeroTahiti'] = order.partner_id.vat
        return expediteur

    def _get_destinataire(self):
        destinataire = {}
        for order in self:
            destinataire['denomination'] = order.partner_shipping_id.name
            if order.partner_shipping_id.mobile or order.partner_shipping_id.phone:
                destinataire['telephone'] = order.partner_shipping_id.mobile or order.partner_shipping_id.phone
            if order.partner_shipping_id.email:
                destinataire['mail'] = order.partner_shipping_id.email
            if order.partner_shipping_id.vat:
                destinataire['numeroTahiti'] = order.partner_shipping_id.vat
        return destinataire

    def _get_pdf(self, order, event):
        url = "connaissements/" + str(order) + "/pdf/" + str(event)
        pdf = self.env['revatua.api'].api_get(url)
        return pdf.content

    def action_confirm(self):
        for order in self:
            expediteur = order._get_expediteur()
            destinataire = order._get_destinataire()
            lines = order._get_order_lines()
            nbrcolis = 0.0
            for line in lines:
                nbrcolis = nbrcolis + line['nbColis']
            # nbrcolis = sum(d['nbColis'] for d in lines.values() if d)
            if order.type_facturation == 'expediteur':
                paiement = "EXPEDITEUR"
            elif order.type_facturation == 'destinataire':
                paiement = "FAD"
            elif order.type_facturation == 'dgae':
                paiement = "DGAE"
            elif order.type_facturation == 'aventure':
                paiement = "AVENTURE"
            payload = {
                "numeroVoyage": order.voyage_id.name,
                "paiement": paiement,
                "ileDepart": order.iledepart_id.name,
                "ileArrivee": order.ilearrivee_id.name,
                "expediteur": expediteur,
                "destinataire": destinataire,
                # "nombreColisAEmbarquer": nbrcolis,
                "detailConnaissementDTO": lines,
            }
            order_response = order.env['revatua.api'].api_post("connaissements", payload)
            order.version = order_response.json()["version"]
            order.id_revatua = order_response.json()["id"]
            # Confirmation dans Revatua
            url = "connaissements/" + order.id_revatua + "/changeretat"
            payload2 = {
                "evenementConnaissementEnum": "OFFICIALISE"
            }
            order_confirm = order.env['revatua.api'].api_patch(url, payload2)
            order.revatua_code = order_confirm.json()["numero"]
            # recup pdf
            # on recupere l'evenement officialisé
            event_id = order_confirm.json()["dernierEtatOfficialise"]["id"]
            pdf_name = order_confirm.json()["dernierEtatOfficialise"]["nomFichier"]
            pdf = order._get_pdf(order.id_revatua, event_id)
            self.env['ir.attachment'].create({
                'name': pdf_name,
                'type': 'binary',
                'datas': base64.b64encode(pdf),
                'res_model': 'sale.order',
                'res_id': order.id,
                'mimetype': 'application/pdf'
            })
            # on génère le libellé pour la référence client qui sera ensuite transférée dans la facture
            order.client_order_ref = "Connaissement n°" + order.revatua_code +\
                " - Expéditeur: " + order.partner_id.name +\
                " - Destinataire: " + order.partner_shipping_id.name +\
                " - " + order.iledepart_id.name + "/" + order.ilearrivee_id.name +\
                " - Voyage: " + order.voyage_id.display_name

            res = super(SaleOrder, self).action_confirm()
            return res


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
    unit_compute = fields.Boolean(string='Unit Compute',
                                  default=False,
                                  help='On coche quand on veut un calcul unitaire')
    official_price = fields.Boolean(string='Official Price',
                                    readonly=True,
                                    default=False)

    @api.onchange('unit_compute')
    def compute_unit_price(self):
        if not self.unit_compute:
            new_price_unit = self.price_unit / self.product_uom_qty
        elif self.unit_compute:
            new_price_unit = self.price_unit * self.product_uom_qty
        self.update({'price_unit': new_price_unit})

    @api.onchange('contenant_id')
    def contenant_id_change(self):
        if not self.contenant_id:
            return
        self.volume = self.contenant_id.volume

    @api.onchange('product_id', 'volume', 'poids')
    def product_id_volume_poids_change(self):
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

            # on tague le champ official price
            vals['official_price'] = pricelistitems and pricelistitems[0].official_price

            # on voit si le volume est en global ou à l'unité
            if self.unit_compute:
                vals['price_unit'] = max(pricevolume, priceweight)
            elif not self.unit_compute:
                vals['price_unit'] = max(pricevolume, priceweight)/self.product_uom_qty
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
