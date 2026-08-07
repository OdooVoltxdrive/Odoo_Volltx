# -*- coding: utf-8 -*-


from odoo import api, fields, models, _ 
#from odoo.addons import decimal_precision as dp

class IsrlConcepts(models.Model):
        """ We can create concept for ISLR Venezuela."""
        _name = 'islr.concept'


        name = fields.Char(string='Retention concept', required=True, help="Name of Retention Concept, Example: Profesional fees")
        retentioned = fields.Boolean(string='Withhold', default=True, help="Check if the concept  withholding is withheld or not.")
        purchase_account_id = fields.Many2one('account.account', 
                string="Purchase income retention account", 
                help="""This account will be used as the account where the withheld
                amounts shall be charged in full (Purchase) of income tax
                for this concept""")
        sales_accountt_id = fields.Many2one(
        'account.account',
        string="Sale account withhold income",
        required=False,
        help="This account will be used as the account in sale retention")
        rate_ids = fields.One2many(
        'islr.rates', 'islr_concept_id', 'Rate',
        help="Retention Concept rate", required=False)