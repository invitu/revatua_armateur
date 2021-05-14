# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api
from datetime import datetime
import pytz


class Trajet(models.Model):
    _name = 'trajet'
    _description = "Liste des périples constituant le voyage"

    name = fields.Char(string='Nom')
    version = fields.Datetime(string='Version')
    id_revatua = fields.Integer(string='ID Revatua', help='ID Unique de trajet')
    date_depart = fields.Datetime(copy=True, string="Date/heure de départ")
    ile_depart_id = fields.Many2one('res.country.state', copy=True,
                                    domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                                    string='Ile de départ')
    lieu_depart_id = fields.Many2one('res.partner', copy=True, string='Lieu de départ')
    date_arrivee = fields.Datetime(copy=True, string="Date/heure d'arivée")
    ile_arrivee_id = fields.Many2one('res.country.state', copy=True,
                                     domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                                     string="Ile d'arivée")
    lieu_arrivee_id = fields.Many2one('res.partner', copy=True, string="Lieu d'arivée")
    voyage_id = fields.Many2one('voyage', string='Voyage',
                                ondelete='cascade',
                                required=True,
                                )

    @api.onchange('ile_depart_id')
    def ile_depart_id_change(self):
        if not self.ile_depart_id:
            return
        self.name = self.ile_depart_id.name


class Navire(models.Model):
    _name = 'navire'
    _description = 'Navire concerné'

    name = fields.Char(string='Nom', help='Nom du navire')
    version = fields.Datetime(string='Version')
    id_revatua = fields.Integer(string='ID Revatua', help='Identifiant technique unique du navire')
    abbreviation = fields.Char(string='Abbréviation', help='Abbréviation du nom du navire')
    vehicule_roulant = fields.Boolean(string='Embarquement de voitures', help="Accepte l'embarquement de véhicules")
    armateur_id = fields.Many2one(comodel_name='armateur', string='Armateur')
    licences_ids = fields.Many2many(comodel_name='licence', string='Licences', help='Licences du navire')
    croisiere = fields.Boolean(string='Croisière', help='Le navire est-il un navire de croisière')


class Voyage(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'voyage'
    _order = 'date_depart'

    name = fields.Char('Numéro de voyage',
                       readonly=True,
                       copy=False,
                       help='Le numéro de voyage, identifiant unique')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirm', 'Confirmed'),
            ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, default='draft')
    version = fields.Char('Version', help="La version des données - pour gérer les problèmes de concurrence")
    navire_id = fields.Many2one(comodel_name='navire', string='Navire',
                                readonly=True,
                                states={
                                    'draft': [('readonly', False)],
                                    'confirm': [('readonly', False)],
                                },
                                )
    date_depart = fields.Datetime(string='Date de depart',
                                  readonly=True,
                                  states={
                                      'draft': [('readonly', False)],
                                      'confirm': [('readonly', False)],
                                  },
                                  help='Date de départ du premier trajet du voyage')
    ile_depart_id = fields.Many2one(comodel_name='res.country.state', string='Ile de départ',
                                    readonly=True,
                                    domain=lambda self: [('country_id', '=', self.env.ref('base.pf').id)],
                                    states={
                                        'draft': [('readonly', False)],
                                        'confirm': [('readonly', False)],
                                    },
                                    )
    lieu_debarquement_depart_id = fields.Many2one(
        comodel_name='res.partner', string='Lieu de debarquement pour le départ',
        readonly=True,
        states={
            'draft': [('readonly', False)],
            'confirm': [('readonly', False)],
        },
    )
    date_arrivee = fields.Datetime(string="Date d'arivée",
                                   readonly=True,
                                   states={
                                       'draft': [('readonly', False)],
                                       'confirm': [('readonly', False)],
                                   },
                                   help="Date d'arrivée du dernier trajet du voyage")
    trajet_ids = fields.One2many(
        comodel_name='trajet', inverse_name='voyage_id', string='Trajets',
        readonly=True,
        copy=True,
        states={
            'draft': [('readonly', False)],
            'confirm': [('readonly', False)],
        },
    )

    def name_get(self):
        result = []
        for voyage in self:
            date_depart = fields.Datetime.from_string(voyage.date_depart)
            if date_depart:
                date = fields.Datetime.context_timestamp(voyage, date_depart).strftime('%a %d/%m/%Y %H:%M')
            else:
                date = '2021-01-01'
            print(date)
            islands = []
            for trajet in voyage.trajet_ids:
                islands.append(trajet.ile_depart_id.name)
            print(islands)
            result.append((voyage.id, '%s %s : (%s)' %
                           (date,
                            islands, voyage.name
                            )))
        return result

    def _get_periple(self):
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')

        periple = []
        for line in self.trajet_ids:
            datedpttz = line.date_depart.astimezone(timezone)
            datearrtz = line.date_arrivee.astimezone(timezone)
            periple.append({
                "dateDepart": datedpttz.strftime("%Y-%m-%d"),
                "heureDepart": datedpttz.strftime("%H:%M"),
                "idIleDepart": line.ile_depart_id.id_revatua,
                "idlieudepart": line.lieu_depart_id.id_revatua,
                "dateArrivee": datearrtz.strftime("%Y-%m-%d"),
                "heureArrivee": datearrtz.strftime("%H:%M"),
                "idIleArrivee": line.ile_arrivee_id.id_revatua,
                "idlieuarrivee":  line.lieu_arrivee_id.id_revatua
            })
        return periple

    def action_confirm(self):
        for voyage in self:
            timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
            if not voyage.name:
                periple = voyage._get_periple()
                payload = {
                    "idNavire": voyage.navire_id.id_revatua,
                    "periple": periple,
                }
                voyage_response = voyage.env['revatua.api'].api_post("voyages", payload)
                voyage.name = voyage_response.json()["numero"]
                voyage.version = voyage_response.json()["version"]
                voyage.date_depart = timezone.localize(datetime.combine(
                    datetime.strptime(voyage_response.json()["dateDepart"], '%Y-%m-%d'),
                    datetime.strptime(voyage_response.json()["heureDepart"], '%H:%M:%S').time(),
                )).astimezone(pytz.utc).replace(tzinfo=None)
                voyage.date_arrivee = timezone.localize(datetime.combine(
                    datetime.strptime(voyage_response.json()["dateRetour"], '%Y-%m-%d'),
                    datetime.strptime(voyage_response.json()["heureRetour"], '%H:%M:%S').time(),
                )).astimezone(pytz.utc).replace(tzinfo=None)
                voyage.ile_depart_id = self.env['res.country.state'].search([
                    ('name', '=', voyage_response.json()["ileDepart"])
                ], limit=1).id
            else:
                payload = {
                    "annule": False,
                }
                url = 'voyages/' + voyage.name
                voyage_response = voyage.env['revatua.api'].api_put(url, payload)
            voyage.state = 'confirm'

    def action_cancel(self):
        if self.name:
            url = 'voyages/' + self.name
            voyage_response = self.env['revatua.api'].api_patch(url)
        self.state = 'cancel'

    def write(self, values):
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        res = super(Voyage, self).write(values)
        if self.name and values.get('trajet_ids'):
            periple = self._get_periple()
            version = self.version
            payload = {
                "idNavire": self.navire_id.id_revatua,
                "periple": periple,
                "version": version,
            }
            print(payload)
            url = 'voyages/' + self.name
            voyage_response = self.env['revatua.api'].api_put(url, payload)
            self.version = voyage_response.json()["version"]
            self.date_depart = timezone.localize(datetime.combine(
                datetime.strptime(voyage_response.json()["dateDepart"], '%Y-%m-%d'),
                datetime.strptime(voyage_response.json()["heureDepart"], '%H:%M:%S').time(),
            )).astimezone(pytz.utc).replace(tzinfo=None)
            self.date_arrivee = timezone.localize(datetime.combine(
                datetime.strptime(voyage_response.json()["dateRetour"], '%Y-%m-%d'),
                datetime.strptime(voyage_response.json()["heureRetour"], '%H:%M:%S').time(),
            )).astimezone(pytz.utc).replace(tzinfo=None)
        return res
