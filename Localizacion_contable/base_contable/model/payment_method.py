# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models,_
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    journal_ids=fields.One2many('account.payment.method_journal','payment_method_id')
    company_id = fields.Many2one('res.company','Company',default=lambda self: self.env.company.id)
    calculo_igtf=fields.Boolean(default=False)


    def asociar(self):
        for line in self.journal_ids:
            if line.status!='Ejecutado':
                diario=line.journal_id
                valores=({
                    'payment_method_id':self.id,
                    'journal_id':line.journal_id.id,
                    'name':self.name,
                    })
                result=''
                if self.payment_type=='inbound':
                    result=line.journal_id.inbound_payment_method_line_ids.create(valores)
                if self.payment_type=='outbound':
                    result=line.journal_id.outbound_payment_method_line_ids.create(valores)
                if result:
                    line.status="Ejecutado"

    def limpia(self):
        for line in self.journal_ids:
            line.unlink()




class LineJournal(models.Model):

    _name = 'account.payment.method_journal'

    payment_method_id = fields.Many2one('account.payment.method')
    journal_id = fields.Many2one('account.journal')
    company_org_journal_id=fields.Many2one('res.company', compute='_compute_company')
    status = fields.Char()

    def _compute_company(self):
        for selff in self:
            selff.company_org_journal_id=selff.journal_id.company_id.id