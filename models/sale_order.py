# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.tools.float_utils import float_round as round
from odoo.exceptions import UserError
from datetime import datetime
import base64
import json


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.onchange('partner_id', 'partner_shipping_id')
    def _compute_island(self):
        self.iledepart_id = self.partner_id.state_id or False
        self.ilearrivee_id = self.partner_shipping_id.state_id or False

    @api.depends('order_line.price_total')
    def _amount_all(self):
        for order in self:
            super(SaleOrder, self)._amount_all()
            if order.type_id == self.env.ref('revatua_armateur.fret_sale_type'):
                minimum_fret_price = float(self.env['ir.config_parameter'].sudo(
                ).get_param('revatua_armateur.minimum_fret_price'))
                if order.amount_untaxed < minimum_fret_price:
                    order.update({
                        'amount_untaxed': minimum_fret_price,
                        'amount_tax': order.amount_tax,
                        'amount_total': minimum_fret_price + order.amount_tax,
                    })

    def write(self, values):
        res = super(SaleOrder, self).write(values)
        if self.type_id == self.env.ref('revatua_armateur.fret_sale_type')\
                and any(f in values.keys() for f in (
                    'partner_shipping_id', 'type_facturation', 'iledepart_id',
                    'ilearrivee_id', 'voyage_id', 'order_line'
                )) and self.id_revatua and 'sale' in self.mapped('state'):
            url = "connaissements/" + self.id_revatua
            payload = self.compute_payload()
            payload['version'] = self.version
            order_response = self.env['revatua.api'].api_put(url, payload)
            self.version = order_response.json()["version"]
            # recup pdf
            self.manage_pdf(order_response)
            # on génère le libellé pour la référence client qui sera ensuite transférée dans la facture
            self.manage_client_ref()
        return res

    partner_invoice_id = fields.Many2one(tracking=True)
    partner_shipping_id = fields.Many2one(tracking=True)
    iledepart_id = fields.Many2one(comodel_name='res.country.state',
                                   string='Ile de Départ',
                                   tracking=True,
                                   domain=lambda self: [
                                       ('country_id', '=', self.env.ref('base.pf').id)],
                                   help='Île de départ (on sélectionne par défaut l\'île de l\'expéditeur)')
    ilearrivee_id = fields.Many2one(comodel_name='res.country.state',
                                    string='Ile d\'arrivée',
                                    tracking=True,
                                    domain=lambda self: [
                                        ('country_id', '=', self.env.ref('base.pf').id)],
                                    help='Île d\'arrivée (on sélectionne par défaut l\'île du destinataire)')
    voyage_id_domain = fields.Char(
        compute="_compute_voyage_id_domain", readonly=True, store=False)
    voyage_id = fields.Many2one(comodel_name='voyage', string='Voyage',
                                tracking=True,
                                help='Choisissez le voyage')
    type_facturation = fields.Selection([
        ('expediteur', 'Fret sur l\'expéditeur'),
        ('destinataire', 'Fret sur le destinataire'),
        ('dgae', 'La DGAE'),
        ('aventure', 'En Aventure')
    ],
        tracking=3,
        string='Qui est facturé ?', help='Sélectionnez le type de facturation', default='expediteur')
    revatua_code = fields.Char(string='Code Revatua', size=64, copy=False,
                               readonly=True)
    id_revatua = fields.Char(string='ID Revatua', size=64, copy=False,
                             readonly=True)
    version = fields.Char(string='Revatua Version', size=64, copy=False,
                          tracking=True,
                          readonly=True)

    @api.onchange('partner_invoice_id')
    def onchange_partner_invoice_id(self):
        if self.type_id == self.env.ref('revatua_armateur.fret_sale_type'):
            pricelist = self.partner_invoice_id.property_product_pricelist
            self.payment_term_id = self.partner_invoice_id.property_payment_term_id
            if pricelist.type == 'fret':
                self.pricelist_id = pricelist.id
            else:
                self.pricelist_id = self.env.ref('revatua_armateur.fretlist0').id

    @api.depends('iledepart_id', 'ilearrivee_id')
    def _compute_voyage_id_domain(self):
        for order in self:
            trajet_from_ids = self.env['trajet'].search([
                ('ile_depart_id', '=', order.iledepart_id.id),
                ('date_depart', '>', datetime.now()),
            ]).ids
            trajet_to_ids = self.env['trajet'].search([
                ('ile_arrivee_id', '=', order.ilearrivee_id.id),
                ('date_depart', '>', datetime.now()),
            ]).ids

            voyage_list = self.env['voyage'].search([
                ('trajet_ids', 'in', trajet_from_ids),
                ('trajet_ids', 'in', trajet_to_ids),
                ('state', '=', 'confirm'),
            ]).ids
            order.voyage_id_domain = json.dumps(
                [('id', 'in', voyage_list)]
            )

    def update_prices(self):
        self.ensure_one()
        if self.pricelist_id.type == 'fret':
            for line in self.order_line.filtered(lambda line: not line.display_type):
                line.product_id_volume_poids_change()
            self.show_update_pricelist = False
            self.message_post(body=_("Product prices have been recomputed according to pricelist <b>%s<b> ", self.pricelist_id.display_name))
        else:
            super(SaleOrder, self).update_prices()

    @api.onchange('type_facturation')
    def set_adresse_facturation(self):
        if self.type_facturation == 'expediteur':
            addr = self.partner_id.address_get(['invoice'])
            self.partner_invoice_id = addr['invoice']
        elif self.type_facturation == 'destinataire':
            addr = self.partner_shipping_id.address_get(['invoice'])
            self.partner_invoice_id = addr['invoice']
        else:
            self.partner_invoice_id = self.env.ref(
                'revatua_connector.partner_dgae')

    def _get_order_lines(self):
        lines = []
        for line in self.order_line:
            datas = {}
            if line.unit_compute:
                poidstotal = line.poids * line.product_uom_qty
                volumetotal = line.volume * line.product_uom_qty
            else:
                poidstotal = line.poids
                volumetotal = line.volume
            datas = {
                "nbColis": line.product_uom_qty,
                "description": line.name,
                "codeSH": line.product_id.nomenclaturepfcustoms_id.code,
                "codeTarif": line.product_id.categ_id.code_revatua,
                "stockage": "CALE",
                "poids": poidstotal,
                "unitePoids": line.unite_poids.code_revatua,
                "volume": volumetotal,
                "uniteVolume": line.unite_volume.code_revatua,
                "matieredangereuse": "true" and line.product_id.matiere_dangereuse or "false",
            }
            if not line.official_price:
                datas["montantLibre"] = line.price_subtotal
            if line.contenant_id.id:
                datas["contenant"] = line.contenant_id.name
            lines.append(datas)

        return lines

    def _get_expediteur(self):
        expediteur = {}
        for order in self:
            if order.partner_id.company_type == 'company' and not order.partner_id.vat:
                raise UserError(
                    _("The expediteur is a company you must fill vat number."))
            expediteur['denomination'] = order.partner_id.name
            if order.partner_id.vat:
                expediteur['numeroTahiti'] = order.partner_id.vat
        return expediteur

    def _get_destinataire(self):
        destinataire = {}
        for order in self:
            if order.partner_shipping_id.company_type == 'company' and not order.partner_shipping_id.vat:
                raise UserError(
                    _("The destinataire is a company you must fill vat number."))
            destinataire['denomination'] = order.partner_shipping_id.name
            if order.partner_shipping_id.vat:
                destinataire['numeroTahiti'] = order.partner_shipping_id.vat
        return destinataire

    def _get_pdf(self, order, event):
        url = "connaissements/" + str(order) + "/pdf/" + str(event)
        pdf = self.env['revatua.api'].api_get(url)
        return pdf.content

    def compute_payload(self):
        expediteur = self._get_expediteur()
        destinataire = self._get_destinataire()
        lines = self._get_order_lines()
        nbrcolis = 0.0
        for line in lines:
            nbrcolis = nbrcolis + line['nbColis']
            # nbrcolis = sum(d['nbColis'] for d in lines.values() if d)
            if self.type_facturation == 'expediteur':
                paiement = "EXPEDITEUR"
            elif self.type_facturation == 'destinataire':
                paiement = "FAD"
            elif self.type_facturation == 'dgae':
                paiement = "DGAE"
            elif self.type_facturation == 'aventure':
                paiement = "AVENTURE"
            payload = {
                "numeroVoyage": self.voyage_id.name,
                "paiement": paiement,
                "ileDepart": self.iledepart_id.name,
                "ileArrivee": self.ilearrivee_id.name,
                "expediteur": expediteur,
                "destinataire": destinataire,
                # "nombreColisAEmbarquer": nbrcolis,
                "detailConnaissementDTO": lines,
            }
            return payload

    def manage_pdf(self, order_response):
        # recup pdf
        # on recupere l'evenement officialisé
        event_id = order_response.json()["dernierEtatOfficialise"]["id"]
        pdf_name = order_response.json(
        )["dernierEtatOfficialise"]["nomFichier"]
        pdf = self._get_pdf(self.id_revatua, event_id)
        # on enregistre le pdf
        # TODO : il faut faire un message avec PJ pour que ca parte au client
        self.env['ir.attachment'].create({
            'name': pdf_name,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': 'sale.order',
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })

    def manage_client_ref(self):
        self.client_order_ref = "Connaissement n°" + self.revatua_code +\
            " - Expéditeur: " + self.partner_id.name +\
            " - Destinataire: " + self.partner_shipping_id.name +\
            " - " + self.iledepart_id.name + "/" + self.ilearrivee_id.name +\
            " - Voyage: " + self.voyage_id.display_name

    def action_confirm(self):
        for order in self:
            if order.type_id == self.env.ref('revatua_armateur.fret_sale_type') and not order.id_revatua:
                payload = order.compute_payload()
                order_response = order.env['revatua.api'].api_post(
                    "connaissements", payload)
                order.id_revatua = order_response.json()["id"]
                # Confirmation dans Revatua
                url = "connaissements/" + order.id_revatua + "/changeretat"
                payload2 = {
                    "evenementConnaissementEnum": "OFFICIALISE"
                }
                order_confirm = order.env['revatua.api'].api_patch(
                    url, payload2)
                order.version = order_confirm.json()["version"]
                order.revatua_code = order_confirm.json()["numero"]
                # recup pdf
                order.manage_pdf(order_confirm)
                # on génère le libellé pour la référence client qui sera ensuite transférée dans la facture
                order.manage_client_ref()
            elif order.type_id == self.env.ref('revatua_armateur.fret_sale_type') and order.id_revatua:
                # Confirmation dans Revatua
                url = "connaissements/" + order.id_revatua + "/changeretat"
                payload2 = {
                    "evenementConnaissementEnum": "OFFICIALISE"
                }
                order_confirm = order.env['revatua.api'].api_patch(
                    url, payload2)
                order.version = order_confirm.json()["version"]
                # recup pdf
                self.manage_pdf(order_confirm)
                # on génère le libellé pour la référence client qui sera ensuite transférée dans la facture
                self.manage_client_ref()
        return super(SaleOrder, self).action_confirm()

    def action_cancel(self):
        for order in self:
            if order.type_id == self.env.ref('revatua_armateur.fret_sale_type') and order.id_revatua:
                url = "connaissements/" + order.id_revatua + "/changeretat"
                payload = {
                    "evenementConnaissementEnum": "ANNULE",
                    "motif": "BLA"
                }
                order_confirm = order.env['revatua.api'].api_patch(
                    url, payload)
                order.version = order_confirm.json()["version"]
        return super(SaleOrder, self).action_cancel()

    def action_draft(self):
        for order in self:
            if order.type_id == self.env.ref('revatua_armateur.fret_sale_type') and order.id_revatua:
                raise UserError(
                    _("The order has been cancelled on revatua, we cannot go back to draft state. It's definitely dead."))
        return super(SaleOrder, self).action_draft()

    @api.model
    def connaissement_sync(self):
        connaissements = self._get_connaissements()

        for conn in connaissements:
            order_vals = {
                'type_id': self.env.ref('revatua_armateur.fret_sale_type').id,
                'id_revatua': conn['id'],
                'revatua_code': conn['numero'],
                'version': conn['version'],
                'partner_id': self._set_expediteur(conn['expediteur']),
                'partner_shipping_id': self._set_destinataire(conn['destinataire']),
            }

            if (conn['paiement'] == 'EXPEDITEUR'):
                order_vals['type_facturation'] = 'expediteur'
            elif (conn['paiement'] == 'FAD'):
                order_vals['type_facturation'] = 'destinataire'
            elif(conn['paiement'] == 'DGAE'):
                order_vals['type_facturation'] = 'dgae'
            elif(conn['paiement'] == 'AVENTURE'):
                order_vals['type_facturation'] = 'aventure'

            order_vals['iledepart_id'] = self.env['res.country.state'].search([
                ('id_revatua', '=', conn['ileDepart']['id'])
            ]).id

            order_vals['ilearrivee_id'] = self.env['res.country.state'].search([
                ('id_revatua', '=', conn['ileArrivee']['id'])
            ]).id

            order_vals['voyage_id'] = self.env['voyage'].search([
                ('name', '=', conn['voyage']['numero'])
            ]).id

            # Create connaissement
            new_order = self.create(order_vals)
            pricelist = new_order.partner_invoice_id.property_product_pricelist
            new_order.pricelist_id = pricelist.id and pricelist.type == 'fret'\
                or self.env.ref('revatua_armateur.fretlist0').id

            for line in conn['detailConnaissements']:
                # on crée le sale_order_line avant pour y appliquer la méthode de calcul des prix
                # on check les inconsistences de product (correspondance categ et codesh)
                # si on a une inconsistence, on cree une ligne commentaire
                line_values = self._check_product_categ_codesh(line)
                if line_values:
                    line_values['order_id'] = new_order.id
                    new_line = self.env['sale.order.line'].create(line_values)
                    line_values = {}
                # si on a une ligne de data, on continue le traitement
                line_values = self._prepare_sale_order_line(line)
                line_values['order_id'] = new_order.id
                new_line = self.env['sale.order.line'].create(line_values)
                new_line.product_id_volume_poids_change()

            # Confirmation dans Revatua
            url = "connaissements/" + str(conn['id']) + "/changeretat"
            payload = {
                "evenementConnaissementEnum": "OFFICIALISE_SOUS_RESERVE"
            }
            order_confirm = self.env['revatua.api'].api_patch(
                url, payload)
            new_order.version = order_confirm.json()["version"]

    def _get_connaissements(self):
        url = "connaissements/demandes/armateurs"
        connaissements = self.env['revatua.api'].api_get(url)

        return json.loads(connaissements.content)["content"]

    def _set_expediteur(self, values):
        # on récupère l'expéditeur par priorité ou on crée un nouveau partner si inexistant
        expediteur = None
        if (values['numeroTahiti']):
            expediteur = self.env['res.partner'].search([
                ('vat', '=', values['numeroTahiti'])
            ]).id

        if (values['mail'] and not expediteur):
            expediteur = self.env['res.partner'].search([
                ('email', '=', values['mail'])
            ]).id

        if (values['telephone'] and not expediteur):
            expediteur = self.env['res.partner'].search([
                '|',
                ('mobile', '=', values['telephone']),
                ('phone', '=', values['telephone'])
            ]).id

        if (not expediteur):
            new_partner = {
                'name': values['denomination'],
                'email': values['mail'],
                'is_company': False
            }

            if (values['numeroTahiti']):
                new_partner.update({
                    'is_company': True,
                    'vat': values['numeroTahiti']
                })

            if (values['telephone'] and values['telephone'][0] == '8'):
                new_partner['mobile'] = values['telephone']
            else:
                new_partner['phone'] = values['telephone']

            expediteur = self.env['res.partner'].create(new_partner).id

        return expediteur

    def _set_destinataire(self, values):
        # on récupère le destinataire par priorité ou on crée un nouveau partner si inexistant
        destinataire = None
        if (values['numeroTahiti']):
            destinataire = self.env['res.partner'].search([
                ('vat', '=', values['numeroTahiti'])
            ]).id

        if (values['mail'] and not destinataire):
            destinataire = self.env['res.partner'].search([
                ('email', '=', values['mail'])
            ]).id

        if (values['telephone'] and not destinataire):
            destinataire = self.env['res.partner'].search([
                '|',
                ('mobile', '=', values['telephone']),
                ('phone', '=', values['telephone'])
            ]).id

        if (not destinataire):
            new_partner = {
                'name': values['denomination'],
                'email': values['mail'],
                'is_company': False
            }

            if (values['numeroTahiti']):
                new_partner.update({
                    'is_company': True,
                    'vat': values['numeroTahiti']
                })

            if (values['telephone'] and values['telephone'][0] == '8'):
                new_partner['mobile'] = values['telephone']
            else:
                new_partner['phone'] = values['telephone']

            destinataire = self.env['res.partner'].create(new_partner).id
        return destinataire

    def _check_product_categ_codesh(self, values):
        """
        Check inconsistence between product, categ_id and codesh.
        Returns a comment order line if it's not consistent
        """
        res = {}
        product_ids = self.env['product.product'].search([
            ('nomenclaturepfcustoms_id.code',
             'like', values['codeSH']['nomenclature']),
            ('categ_id.code_revatua',
             '=', values['codeTarif']['code']),
        ])
        # S'il n'y a aucun produit qui match, on renvoie un commentaire
        if not product_ids:
            res['display_type'] = 'line_note'
            res['name'] = _('ATTENTION Received data is wrong : designation %(product)s is received with nomenclature %(codesh)s(%(codeshname)s) and category %(categ)s.',
                            product=values['description'],
                            codesh=values['codeSH']['nomenclature'],
                            codeshname=values['codeSH']['libelle'],
                            categ=values['codeTarif']['libelle'],
                            )
        return res

    def _prepare_sale_order_line(self, values):
        """
        Prepare the dict of values to create the new sale order line for a detail connaissement.
        """

        basic_poids = self.env['uom.uom'].search(
            [('id', '=', self.env.ref('uom.product_uom_kgm').id)])
        basic_volume = self.env['uom.uom'].search(
            [('id', '=', self.env.ref('uom.product_uom_cubic_meter').id)])
        res = {'product_uom_qty': values['nbColis']}

        if (values['codeSH']['nomenclature']):
            product_id = self.env['product.product'].search([
                ('nomenclaturepfcustoms_id.code',
                 'like', values['codeSH']['nomenclature'])
            ]).id
            res['product_id'] = product_id

        if (values['contenant']):
            contenant = self.env['product.product'].search([
                ('id_revatua', '=', values['contenant']['id'])
            ]).id
            res['contenant_id'] = contenant

        if (values['uniteVolume']):
            unite_volume = self.env['uom.uom'].search([
                ('code_revatua', '=', values['uniteVolume'])
            ])
            res['volume'] = unite_volume._compute_quantity(
                values['volume'], basic_volume)

        if (values['unitePoids']):
            unite_poids = self.env['uom.uom'].search([
                ('code_revatua', '=', values['unitePoids'])
            ])
            res['poids'] = unite_poids._compute_quantity(
                values['poids'], basic_poids)

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
                                   default=lambda self: self.env.ref(
                                       'uom.product_uom_cubic_meter'),
                                   domain=lambda self: [('category_id', '=', self.env.ref('uom.product_uom_categ_vol').id)])
    unite_poids = fields.Many2one(comodel_name='uom.uom',
                                  string="Unité de poids",
                                  groups="revatua_connector.group_revatua_user",
                                  readonly=True,
                                  default=lambda self: self.env.ref(
                                      'uom.product_uom_kgm'),
                                  domain=lambda self: [('category_id', '=', self.env.ref('uom.product_uom_categ_kgm').id)])
    volume = fields.Float(string='Volume (m3)', digits='Volume',
                          help='Volume is computed from dimensions but can be overwritten. Always in m3')
    poids = fields.Float(string='Poids (kg)', digits='Stock Weight',
                         help='Weight is always in kg')
    longueur = fields.Integer(string="Longueur (cm)", help='Longueur en cm')
    largeur = fields.Integer(string="Largeur (cm)", help='Largeur en cm')
    hauteur = fields.Integer(string="Hauteur (cm)", help='Hauteur en cm')
    unit_compute = fields.Boolean(string='Unit Compute',
                                  default=False,
                                  help='On coche quand on veut un calcul unitaire')
    official_price = fields.Boolean(string='Official Price',
                                    readonly=True,
                                    default=False)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        res = super(SaleOrderLine, self)._compute_amount()
        for line in self:
            if line.order_id.type_id == self.env.ref('revatua_armateur.fret_sale_type'):
                line.price_subtotal = round(line.product_uom_qty * line.price_unit * (
                    1 - (line.discount or 0.0) / 100.0), precision_digits=0, rounding_method='DOWN')
        return res

    @api.onchange('contenant_id')
    def contenant_id_change(self):
        if not self.contenant_id:
            return
        self.volume = self.contenant_id.volume

    @api.onchange('product_id', 'volume', 'poids', 'unit_compute', 'product_uom_qty')
    def product_id_volume_poids_change(self):
        self.ensure_one()
        # Version a l'arrache complet... il faut faire gaffe !!!
        res = super(SaleOrderLine, self).product_id_change()
        if self.order_id.pricelist_id.type == 'fret' and self.product_id:
            date = self.order_id.validity_date or self.order_id.date_order or self._context.get(
                'date') or fields.Datetime.now()
            vals = {}
            discount = 0.0
            iles_ids = (self.order_id.iledepart_id.id,
                        self.order_id.ilearrivee_id.id)
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
                (self.order_id.pricelist_id.id, self.product_id.categ_id.id,
                 date, date, iles_ids, iles_ids)
            )

            item_ids = [x[0] for x in self.env.cr.fetchall()]
            pricelistitems = self.env['product.pricelist.item'].browse(
                item_ids)
            if pricelistitems:
                pricelistitem_id = pricelistitems[0]
            # Ici on considère qu'on a qu'un seul résultat et que le prix est en mode fixed price...etc... bref, on est vraiment dans du specifique
            # On gère le rule.base == pricelist
            if pricelistitems and pricelistitem_id.base == 'pricelist':
                # On récupère les items de la list dépendante
                base_pricelist_id = pricelistitem_id.base_pricelist_id.id
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
                    (base_pricelist_id, self.product_id.categ_id.id,
                     date, date, iles_ids, iles_ids)
                )
                item_tmp_ids = [x[0] for x in self.env.cr.fetchall()]
                pricelistitems_tmp = self.env['product.pricelist.item'].browse(
                    item_tmp_ids)
                # on calcule le prix avec la liste dépendante (une seule dépendance possible)
                pricetmp = pricelistitems_tmp[0].fixed_price or 0.0
                # on calcule le prix définitif avec la formule
                price_limit = pricetmp
                price = (pricetmp - (pricetmp *
                         (pricelistitem_id.price_discount / 100))) or 0.0
                if pricelistitem_id.price_round:
                    price = tools.float_round(
                        price, precision_rounding=pricelistitem_id.price_round)

                if pricelistitem_id.price_surcharge:
                    price_surcharge = pricelistitem_id.price_surcharge
                    price += price_surcharge

                if pricelistitem_id.price_min_margin:
                    price_min_margin = pricelistitem_id.price_min_margin
                    price = max(price, price_limit + price_min_margin)

                if pricelistitem_id.price_max_margin:
                    price_max_margin = pricelistitem_id.price_max_margin
                    price = min(price, price_limit + price_max_margin)

                if pricelistitem_id.pricelist_id.discount_policy == 'without_discount' and pricetmp:
                    discount = max(0, (pricetmp - price) * 100 / pricetmp)
                    price = pricetmp

            elif pricelistitems and pricelistitem_id.fixed_price:
                price = pricelistitem_id.fixed_price
            else:
                price = 0.0
            # Ici on shunte encore tout, on considère que l'unité n'a pas changé...etc bref...

            # Special Case for product that have a fixed volume or fixed price
            # On récupère le poids et le volume de la fiche article
            if self.product_id.volume != 0.0:
                self.volume = self.product_id.volume
                self.unit_compute = True
            if self.product_id.weight != 0.0:
                self.poids = self.product_id.weight
                self.unit_compute = True
            pricevolume = price * self.volume
            priceweight = price * self.poids / 1000

            # on tague le champ official price
            vals['official_price'] = pricelistitems and pricelistitem_id.official_price

            # on voit si le volume est en global ou à l'unité
            if self.unit_compute:
                vals['price_unit'] = max(pricevolume, priceweight)
            elif not self.unit_compute:
                vals['price_unit'] = max(pricevolume, priceweight)/self.product_uom_qty
            vals['discount'] = discount

            # Special Case for Gaz 13kg and Gaz 50kg
            if self.product_id.categ_id in (
                    self.env.ref('revatua_armateur.product_cat_gazbtl13'),
                    self.env.ref('revatua_armateur.product_cat_gazbtl50'),
            ):
                vals['unit_compute'] = True
                vals['price_unit'] = price

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
