# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class Productos(models.Model):
    _inherit = 'product.template'


    habilita_precio_div = fields.Boolean(default=False)
    list_price2 = fields.Float(string="Precio de Venta en USD", default=1,digits=(12, 4))
    standard_price_usd = fields.Float(digits=(12, 4))
    tasa_dia=fields.Float(digits=(12, 4),compute='_compute_tasa')

    def _log_and_raise_fiscal_error(self, message, event_type='cancel_attempt'):
        """Registra el evento en l10n.ve.fiscal.log y lanza un error de validación."""
        
        # Si el registro no tiene un ID real (NewId en creación), evitamos crear el log
        #if isinstance(self.id, models.NewId) or not self.id:
            #raise ValidationError(message)

        try:
            # Intentamos crear el log de auditoría fiscal
            self.env['l10n.ve.fiscal.log'].create({
                'model_name': 'product.template',
                'res_id': self.id,
                'event_type': event_type,
                'description': message,
                'document_ref': f"product.template,{self.id}",  # Volvemos al formato original seguro bajo try/except
            })
            self.env.cr.commit()
        except Exception:
            # Si el módulo de auditoría falla por el tipo de campo, dejamos pasar el log 
            # pero el ValidationError de abajo igual detendrá la operación del usuario.
            pass
        
        raise ValidationError(message)

    

    @api.constrains('taxes_id')
    def _check_single_tax(self):
        """ Valida que solo haya un impuesto en la lista al guardar. """
        # Odoo salta la validación si se está instalando/configurando la contabilidad o módulos en segundo plano
        """if self.env.context.get('install_mode') or self.env.context.get('skip_check_tax'):
            return"""

        for record in self:
            # len(record.taxes_id) cuenta el número de registros en el Many2many
            if len(record.taxes_id) > 1:
                # ❌ Lanza un error de validación, que automáticamente revierte (rollback)
                #    cualquier cambio y previene el commit de datos incorrectos.
                """raise ValidationError(
                    _('Error de Validación: Solo se puede asignar una alícuota de ventas a este producto. Deje uno y guarde'))"""
                self._log_and_raise_fiscal_error("🛑 Error de Validación: Solo se puede asignar una alícuota de ventas a este producto. Deje uno y guarde")

    @api.constrains('supplier_taxes_id')
    def _check_single_tax_compras(self):
        """ Valida que solo haya un impuesto en la lista al guardar. """
        # Odoo salta la validación si se está instalando/configurando la contabilidad o módulos en segundo plano
        #if self.env.context.get('install_mode') or self.env.context.get('skip_check_tax'):
            #return

        for record in self:
            # len(record.taxes_id) cuenta el número de registros en el Many2many
            if len(record.supplier_taxes_id) > 1:
                # ❌ Lanza un error de validación, que automáticamente revierte (rollback)
                #    cualquier cambio y previene el commit de datos incorrectos.
                """raise ValidationError(
                    _('Error de Validación: Solo se puede asignar una alícuota de compras a este producto. Deje uno y guarde'))"""
                record._log_and_raise_fiscal_error("🛑 Error de Validación: Solo se puede asignar una alícuota de compras a este producto. Deje uno y guarde")



    def _compute_tasa(self):
        lista=self.env['res.currency.rate'].search([('currency_id','=',self.env.company.currency_sec_id.id)],limit=1,order='name desc')
        if lista:
            for det in lista:
                self.tasa_dia=det.inverse_company_rate


    @api.onchange('standard_price')
    def actualiza_coste(self):
        for selff in self:
            var_tasa=selff.tasa_dia
            if var_tasa==0:
                var_tasa=1
            if selff.standard_price!=0:
                selff.standard_price_usd=selff.standard_price/var_tasa


    @api.onchange('list_price2')
    def actualiza_precio_venta_bs(self):
        for selff in self:
            if selff.list_price2!=0 and selff.habilita_precio_div==True:
                selff.list_price=selff.list_price2*selff.tasa_dia


    def write(self,vals):
        # Agregamos 'skip_check_tax' al contexto interno al hacer write masivos de Odoo para evitar bloqueos del sistema
        if not self.env.context.get('skip_check_tax'):
            self = self.with_context(skip_check_tax=True)
            
        super().write(vals)
        for selff in self:
            busca=selff.env['product.product'].search([('product_tmpl_id','=',selff.id)])
            if busca:
                for det in busca:
                    det.habilita_precio_divv=selff.habilita_precio_div
                    det.lst_price2=selff.list_price2

    #def actualiza_coste(self):



class ProductProduct(models.Model):
    _inherit = 'product.product'

    habilita_precio_divv = fields.Boolean(default=False)
    lst_price2 = fields.Float(string="Precio de Venta en USD", default=1,digits=(12, 4))
    standard_price_usd = fields.Float(digits=(12, 4))
    tasa_dia=fields.Float(digits=(12, 4),compute='_compute_tasa')

    def _compute_tasa(self):
        lista=self.env['res.currency.rate'].search([('currency_id','=',self.env.company.currency_sec_id.id)],limit=1,order='name desc')
        if lista:
            for det in lista:
                self.tasa_dia=det.inverse_company_rate

    @api.onchange('standard_price_usd')
    def actualiza_coste(self):
        for selff in self:
            var_tasa=selff.tasa_dia
            if var_tasa==0:
                var_tasa=1
            if selff.standard_price!=0:
                selff.standard_price_usd=selff.standard_price/var_tasa
                selff.product_tmpl_id.standard_price_usd=selff.standard_price_usd

    @api.onchange('lst_price2')
    def actualiza_precio_venta_bs(self):
        for selff in self:
            if selff.lst_price2!=0 and selff.habilita_precio_divv==True:
                selff.lst_price=selff.lst_price2*selff.tasa_dia