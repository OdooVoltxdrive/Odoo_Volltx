# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, date_utils
from odoo.tools.misc import formatLang, format_date
from contextlib import ExitStack, contextmanager



class WizardPagosFacturas(models.TransientModel):
    _name = 'wizard.payment.fact'

    move_id = fields.Many2one('account.move')#
    tasa = fields.Float(digits=(12, 4))#
    monta_a_pagar = fields.Float()#
    moneda = fields.Many2one('res.currency')#
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)
    account_journal_id = fields.Many2one('account.journal',string="Diario")#
    account_payment_method_id = fields.Many2one('account.payment.method.line')#
    ban=fields.Integer(default=0)
    method_payment_type = fields.Char()
    fecha = fields.Date(string='Fecha')

    @api.depends('fecha')
    @api.onchange('fecha')
    def _compute_tasa(self):
        result=1
        for selff in self:
            lista=selff.env['res.currency.rate'].search([('currency_id','=',selff.company_id.currency_sec_id.id),('name','<=',selff.fecha)],order='name desc',limit=1)
            if lista:
                result=lista.inverse_company_rate
            selff.tasa=result

    def action_register_ext_payment(self):
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return ''
        #raise UserError(_('valor=%s')%active_ids[0])
        self.move_id=active_ids[0]
        #self.monto=self.sale_order_id.amount_total_doc
        return {
            'name': _('Register Payment'),
            'res_model': len(active_ids) == 1 and 'wizard.payment.fact',
            'view_mode': 'form',
            'view_id': len(active_ids) != 1 and self.env.ref('base_contable.vista_from_pago_prog').id,
            'context': self.env.context,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    @api.onchange('company_id')
    def id_fact(self):
        active_ids = self.env.context.get('active_ids')
        #raise UserError(_('valor=%s')%active_ids[0])
        self.move_id=active_ids[0]
        self.tasa=self.move_id.tasa
        self.monta_a_pagar=self.move_id.amount_total+self.igtf(self.move_id)-self.abonado(self.move_id)
        self.moneda=self.move_id.currency_id.id
        self.fecha=self.move_id.invoice_date
        if self.move_id.move_type in ('in_invoice','in_refund','in_receipt'):
            self.method_payment_type='inbound'
        if self.move_id.move_type in ('out_invoice','out_refund','out_receipt'):
            self.method_payment_type='outbound'

    def abonado(self,move_id):
        acum=0
        for det in move_id.igtf_ids.search([('move_id','=',move_id.id)]):
            acum=acum+det.monta_a_pagar_bs/self.tasa if self.move_id.currency_id!=self.company_id.currency_id else acum+det.monta_a_pagar_bs
        return acum

    def igtf(self,move_id):
        valor=move_id.amount_igtf
        return valor


    @api.onchange('moneda', 'tasa')
    def actualiza_cambio_deuda(self):
        """
        Optimiza el cálculo del monto a pagar basándose en la moneda de la factura
        y la moneda seleccionada en el wizard.
        """
        if not self.move_id or not self.tasa:
            return

        # 1. Obtenemos el saldo pendiente original en la moneda de la factura
        # Re-calculamos el monto base (en la moneda de la factura) para evitar errores de redondeo acumulados
        monto_base_factura = self.move_id.amount_total + self.igtf(self.move_id) - self.abonado(self.move_id)

        # 2. Lógica de conversión
        if self.moneda == self.move_id.currency_id:
            # Si la moneda del wizard es igual a la de la factura, no hay conversión
            self.monta_a_pagar = monto_base_factura
        
        elif self.moneda == self.company_id.currency_id:
            # Caso: Factura en $ (moneda secundaria) -> Pago en Bs (moneda base)
            # Se multiplica por la tasa
            self.monta_a_pagar = monto_base_factura * self.tasa
            
        else:
            # Caso: Factura en Bs (moneda base) -> Pago en $ (moneda secundaria)
            # Se divide por la tasa (evitando división por cero)
            self.monta_a_pagar = monto_base_factura / self.tasa if self.tasa > 0 else 0


            

    def pagar(self):
        active_ids = self._context.get('active_ids') or self._context.get('active_id')
        self.move_id=active_ids[0]
        vals=({
            'move_id':self.move_id.id,
            'account_journal_id':self.account_journal_id.id,
            'moneda':self.moneda.id,
            'monta_a_pagar':self.monta_a_pagar,
            'account_payment_method_id':self.account_payment_method_id.id,
            'tasa':self.tasa,
            'fecha':self.fecha,
            })
        self.env['account.payment.fact'].create(vals)

        