# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger('__name__')

class AccountMove(models.Model):
    _inherit = 'account.move'    

    vat_ret_id = fields.Many2one('vat.retention', string='Retención IVA', readonly="True", copy=False, help='Voucher Retencion IVA')
    vat_ret_aux_id = fields.Char(copy=False)
    contacto_id = fields.Many2one('res.partner', compute='_compute_contacto',string="Contacto")

    def _compute_contacto(self):
        if self.partner_id:
            self.contacto_id=self.partner_id.id
        else:
            self.contacto_id=False


    def action_post(self):
        result=super().action_post()
        self.valida_vat_retention()
        return result



    def valida_vat_retention(self):
        for selff in self:
            if selff.move_type in ('in_invoice','in_refund','in_receipt'):
                # proveedor
                if selff.company_id.aplicar_ret==True:
                    selff.action_create_vat_retention()
            if selff.move_type in ('out_invoice','out_refund','out_receipt'):
                # cliente
                if selff.partner_id.contribuyente=='si':
                    selff.action_create_vat_retention()


    def action_create_vat_retention(self):
        if self.hay_aliquot()==True:
            factor=1
            if self.currency_id.id!=self.company_id.currency_id.id:
                factor=self.tasa
            objeto=self.env['vat.retention']
            vals=({
                'partner_id':self.partner_id.id,
                'accouting_date':self.date,
                'voucher_delivery_date':self.date,
                'invoice_id':self.id,
                'invoice_number_next':self.invoice_number_next,
                'invoice_number_control':self.invoice_number_control,
                'type':self.move_type,
                'journal_id':self.partner_id.ret_jrl_id.id,
                })
            id_vat=objeto.create(vals)

            if self.vat_ret_aux_id:
                id_vat.name=self.vat_ret_aux_id

            if self.move_type in ('in_invoice','in_refund','in_receipt'):
                # proveedor
                retention_rate=self.partner_id.vat_retention_rate
            if self.move_type in ('out_invoice','out_refund','out_receipt'):
                # cliente
                retention_rate=self.env.company.vat_retention_rate_cli
            #raise UserError(_("retention_rate %s")%retention_rate)

            for line_move in self.invoice_line_ids:
                tax_id=''
                amount_imp=amount_base_impo=0
                amount_base_impo=line_move.price_subtotal
                for det in line_move.tax_ids:
                    tax_id=det.id
                    tax_aliquot=det.aliquot
                    tax_aliquot_value=det.amount
                if tax_aliquot in ('general','reduced','additional'):
                    ban=self.valida_lineas_aliquot_repetidas(tax_id,id_vat)
                    amount_imp=amount_base_impo*tax_aliquot_value/100
                    if ban==False:
                        vals2=({
                            'invoice_number':self.invoice_number_next,
                            'amount_vat_ret':amount_imp*factor,
                            'retention_rate':retention_rate,
                            'retention_id':id_vat.id,
                            'invoice_id':self.id,
                            'tax_id':tax_id if tax_id else '',
                            'base_imponible':amount_base_impo*factor,
                            })
                        id_vat.retention_line_ids.create(vals2)
                    else:
                        objeto_line=self.env['vat.retention.invoice.line'].search([('retention_id','=',id_vat.id),('tax_id','=',tax_id)])
                        objeto_line.write({
                            'amount_vat_ret':objeto_line.amount_vat_ret+amount_imp*factor, #self.amount_imp*factor,
                            'base_imponible':objeto_line.base_imponible+amount_base_impo*factor,
                            })


            # Aqui publica automaticamente el comprobante si la factura es de proveedor
            if self.move_type in ('in_invoice','in_refund','in_receipt'):
                id_vat.action_posted()

            self.vat_ret_id=id_vat.id
            self.vat_ret_aux_id=id_vat.name
            #self.vat_ret_id=id_vat.id

    def button_draft(self):
        super().button_draft()
        self.vat_ret_id.action_draft()
        self.vat_ret_id.with_context(force_delete=True).unlink()

    def hay_aliquot(self):
        ban=False
        for line in self.invoice_line_ids:
            if line.tax_ids.aliquot in ('general','reduced','additional'):
                ban=True
        return ban

    def valida_lineas_aliquot_repetidas(self,tax_id,id_vat):
        busca=self.env['vat.retention.invoice.line'].search([('retention_id','=',id_vat.id),('tax_id','=',tax_id)])  
        if busca:
            result=True
        else:
            result=False
        #raise UserError(_('busca: %s')%busca)
        return result


    