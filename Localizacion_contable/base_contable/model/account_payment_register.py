# -*- coding: utf-8 -*-


import logging
from datetime import datetime, date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'
    _description = 'Register Payment'

    amount_igtf=fields.Float()
    tasa = fields.Float(string='Tipo de Cambio', digits=(12, 4),default=0)
    journal_igtf_id = fields.Many2one('account.journal')
    metodo_pago_igtf = fields.Many2one('account.payment.method.line')
    tipo_doc = fields.Char(compute='_compute_tipo_doc')
    aplica_igtf = fields.Boolean(compute='_compute_igtf')

    @api.onchange('journal_id')
    def _compute_igtf(self):
        self.aplica_igtf=self.journal_id.aplica_igtf


    @api.onchange('payment_date')
    def actualiza_tasa(self):
        valor=1
        busca=self.env['res.currency.rate'].search([('name', '<=', self.payment_date), ('currency_id', '=', 1)], limit=1)
        if busca:
            valor=busca.inverse_company_rate
        self.tasa=valor

    @api.depends('payment_date','tasa','currency_id','amount')
    def _compute_tipo_doc(self):
        valor='x'
        for move_line in self.line_ids:
            move_id=move_line.move_id
        if move_id.move_type in ('out_invoice','out_receipt','in_refund'):
            valor='inbound'
        if move_id.move_type in ('in_invoice','in_receipt','out_refund'):
            valor='outbound'
        self.tipo_doc=valor

    @api.onchange('payment_date','tasa','currency_id','amount')
    def calcula_igtf(self):
        for move_line in self.line_ids:
            move_id=move_line.move_id
        if self.currency_id!=self.env.company.currency_id and move_id.journal_id.nota_entrega!=True:
            self.amount_igtf=self.tasa*self.amount*self.env.company.percentage_cli_igtf/100

    def action_create_payments(self):
        super().action_create_payments()
        self.registra_pago_igtf()



    def registra_pago_igtf(self):
        if self.journal_id.aplica_igtf==True:
            if self.currency_id!=self.env.company.currency_id:
                #move_id=self.env['account.move'].search([('name','=',self.communication)])
                for move_line in self.line_ids:
                    move_id=move_line.move_id
                tasa=1
                busca=self.env['res.currency.rate'].search([('name', '<=', self.payment_date), ('currency_id', '=', 1)], limit=1)
                if busca:
                    valor=busca.inverse_company_rate
                tasa=valor
                if not self.journal_igtf_id and move_id.journal_id.nota_entrega!=True:
                    raise UserError (_('No se a seleccionado un diario de Banco para el igtf'))
                #if move_id.journal_id.nota_entrega!=True and self.payment_method_line_id.payment_method_id.calculo_igtf==True:
                if move_id.journal_id.nota_entrega!=True and  self.journal_id.aplica_igtf==True:
                    #raise UserError (_('xxx=%s')%move_id.journal_id.nota_entrega)
                    """asiento_igtf=self.registro_movimiento_asiento_igtf(self.amount_igtf)
                    self.registro_movimiento_linea_igtf(asiento_igtf.id)
                    asiento_igtf.action_post()"""
                    asiento_igtf=self.pago_igtf()
                    valsx=({
                        'move_id':move_id.id,
                        'account_journal_id':self.journal_igtf_id.id,
                        'moneda':self.currency_id.id,
                        'monta_a_pagar':self.amount,
                        'account_payment_method_id':self.payment_method_line_id.id,
                        'tasa':tasa,
                        'monta_a_pagar_bs':self.tasa*self.amount,
                        'asiento_igtf':asiento_igtf.id if asiento_igtf else '',
                        })
                    reg_pago=self.env['account.payment.fact'].create(valsx)
                #raise UserError(_('xxxx=%s')%move_id)

    def get_name_igtf_clie(self):
        '''metodo que crea el Nombre del asiento contable si la secuencia no esta creada, crea una con el
        nombre: '''

        self.ensure_one()
        SEQUENCE_CODE = 'IGTF_CLI'
        company_id = self.env.company
        IrSequence = self.env['ir.sequence'].with_context(force_company=company_id.id)
        name = IrSequence.next_by_code(SEQUENCE_CODE)

        # si aún no existe una secuencia para esta empresa, cree una
        if not name:
            IrSequence.sudo().create({
                'prefix': 'IGTF/Divisas/',
                'name': 'Impuesto ITF %s' % company_id.id,
                'code': SEQUENCE_CODE,
                'implementation': 'no_gap',
                'padding': 8,
                'number_increment': 1,
                'company_id': company_id.id,
            })
            name = IrSequence.next_by_code(SEQUENCE_CODE)
        return name

    def pago_igtf(self):
        vals=({
            'payment_type':self.payment_type,
            'partner_type':"supplier" if self.payment_type=='outbound' else "customer",
            'partner_id':self.partner_id.id,
            'amount':self.amount_igtf,
            'date':self.payment_date,
            'memo':"Pago igtf de la factura: "+self.communication,
            'journal_id':self.journal_igtf_id.id,
            'payment_method_line_id':self.metodo_pago_igtf.id,
            })
        pago_igtf=self.env['account.payment'].create(vals)
        pago_igtf.action_post()
        #self.env.company.account_igtf_id.id
        for line in pago_igtf.move_id.line_ids:
            if self.payment_type=="inbound":
                if line.account_id==self.partner_id.property_account_receivable_id:
                    #raise UserError (_('AA=%s')%self.payment_type)
                    line.account_id=self.env.company.account_igtf_id.id
            if self.payment_type=="outbound":
                if line.account_id==self.partner_id.property_account_payable_id:
                    #raise UserError (_('BB=%s')%self.payment_type)
                    line.account_id=self.env.company.account_igtf_p_id.id
        return pago_igtf.move_id

    def registro_movimiento_asiento_igtf(self,amont_totall):
        #raise UserError(_('darrell = %s')%self.partner_id.vat_retention_rate)
        name = self.get_name_igtf_clie()
        signed_amount_total=0
        signed_amount_total=amont_totall
        id_journal=self.journal_igtf_id.id
        value = {
            'name': name,
            'date': self.payment_date, #listo
            #'amount_total':self.vat_retentioned,# LISTO
            'partner_id': self.company_id.partner_id.id, #LISTO
            'journal_id':self.journal_igtf_id.id,  #self.env.company.journal_transi_id.id, #id_journal,
            'ref': "Pago de igtf %s" % (self.communication),
            #'amount_total':signed_amount_total,# LISTO
            'amount_total_signed':signed_amount_total,# LISTO
            'move_type': "entry",# estte campo es el que te deja cambiar y almacenar valores
            'company_id':self.env.company.id,#loca14
            'currency_id':self.env.company.currency_id.id, #self.currency_id.id if self.currency_id.id!=self.company_currency_id.id else "",
        }
        #raise UserError(_('value= %s')%value)
        move_obj = self.env['account.move']
        move_id = move_obj.create(value)    
        return move_id

    def registro_movimiento_linea_igtf(self,id_movv):
        #raise UserError(_('ID MOVE = %s')%id_movv)
        name = "IGTF del pago: "#+self.communication
        valores = self.amount_igtf #retencion #self.conv_div_extranjera(self.vat_retentioned) #VALIDAR CONDICION
        #raise UserError(_('valores = %s')%valores)
        cero = 0.0
        
        if not self.metodo_pago_igtf.payment_account_id:
            raise UserError(_('Metodo de pago para igtf no tiene asociado una cuenta contable'))
        ### para clientes
        if self.payment_type=="inbound":
            cuenta_haber=self.env.company.account_igtf_id.id  #cuenta_igtf.id
            cuenta_debe=self.metodo_pago_igtf.payment_account_id.id #self.journal_id.default_account_id.id #cuenta_otra.id

        ### para proveedores
        if self.payment_type=="outbound":
            cuenta_haber=self.metodo_pago_igtf.payment_account_id.id  #self.journal_id.default_account_id.id
            cuenta_debe=self.env.company.account_igtf_id.id #cuenta_igtf.id

        balances=cero-valores
        value = {
             'name': name,
             'ref' : "Pago de igtf ",
             'move_id': int(id_movv),
             'date': self.payment_date,
             'partner_id': self.env.company.partner_id.id,
             'account_id': cuenta_haber,
             #'currency_id':self.invoice_id.currency_id.id,
             #'amount_currency': 0.0,
             #'date_maturity': False,
             'credit': valores,
             'debit': 0.0, # aqi va cero   EL DEBITO CUNDO TIENE VALOR, ES QUE EN ACCOUNT_MOVE TOMA UN VALOR
             'balance':-valores, # signo negativo
             'price_unit':balances,
             'price_subtotal':balances,
             'price_total':balances,
             'currency_id':self.currency_id.id if self.currency_id.id!=self.company_currency_id.id else "",
             'amount_currency': -1*self.amount if self.currency_id.id!=self.company_currency_id.id else "",

        }

        move_line_obj = self.env['account.move.line']
        move_line_id1 = move_line_obj.create(value)

        balances=valores-cero
        value['name'] = " "
        value['account_id'] = cuenta_debe
        value['credit'] = 0.0 # aqui va cero
        value['debit'] = valores
        value['balance'] = valores
        value['price_unit'] = balances
        value['price_subtotal'] = balances
        value['price_total'] = balances
        value['currency_id'] = self.currency_id.id if self.currency_id.id!=self.company_currency_id.id else ""
        value['amount_currency'] = self.amount if self.currency_id.id!=self.company_currency_id.id else ""

        move_line_id2 = move_line_obj.create(value)

