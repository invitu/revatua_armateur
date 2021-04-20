# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from datetime import datetime


class WizardPriceilistGetRevatua(models.TransientModel):
    _name = 'wizard.pricelist.get.revatua'
    _description = 'Wizard that gets the pricelist from revatua and compute it'

    date = fields.Date(string='Date', help='Enter the date of the validity')

    def get_tarif(self):
        date = datetime.strftime(self.date, '%Y-%m-%d')
        url = 'tarifs/actif?dateTarif='+date+'&detailTarif=true'

        tarif_response = self.env['revatua.api'].api_get(url)
        version = tarif_response.json()["version"]
        idrevatua = tarif_response.json()["id"]
        datetarif = tarif_response.json()["dateApplication"]
        tarifmini = tarif_response.json()["tarifMinimum"]
        detailtarif = tarif_response.json()["detailTarifs"]
        print(version)
        print(idrevatua)
        print(datetarif)
        print(tarifmini)
        print(detailtarif)
        #on récupère la pricelist
        pricelists = self.env['product.pricelist'].browse(self._context.get('active_ids', []))
        for dic in detailtarif:
            codetarif = dic['codeTarif']
            categ_revatua = self.env['product.category'].search(
                [('code_revatua', '=', codetarif)])

            ile1 = self.env['res.country.state'].search(
                [
                    ('name', '=', dic['nomIleDepart']),
                    ('country_id', '=', self.env.ref('base.pf').id),
                ])
            ile2 = self.env['res.country.state'].search(
                [
                    ('name', '=', dic['nomIleArrivee']),
                    ('country_id', '=', self.env.ref('base.pf').id),
                ])
            montant = dic['montant']
            print(categ_revatua)
            print(ile1)
            print(ile2)
            print(montant)
            # Now we add tarif lines in pricelist
            # on ajoute les items
            if categ_revatua:
                for pricelist in pricelists:
                    pricelist.write({
                        'item_ids': [(0, 0, {
                            'ile1_id': ile1.id,
                            'ile2_id': ile2.id,
                            'applied_on': '2_product_category',
                            'categ_id': categ_revatua.id,
                            'compute_price': 'fixed',
                            'fixed_price': montant,
                            'date_start': datetarif,
                        })]
                    })
            else:
                raise UserError(_('Category %s does not exist') % codetarif)
