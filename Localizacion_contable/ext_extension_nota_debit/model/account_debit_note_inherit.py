# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'


    @api.model
    def default_get(self, fields):
        """
        Sobrescribe default_get para establecer el diario por defecto
        basándose en si la nota de débito es para clientes o proveedores.
        """
        # 1. Obtener los valores por defecto de la implementación base
        #raise UserError(_("valor"))
        res = super().default_get(fields)

        # 2. Solo proceder si se necesita el campo 'journal_id'
        if 'journal_id' in fields and not res.get('journal_id'):
            # Obtener la compañía actual
            company_id = self.env.company.id
            
            # Obtener los IDs de las facturas activas (si existen)
            active_ids = self.env.context.get('active_ids')
            
            # Inicializar los criterios de búsqueda por defecto (para clientes)
            tipo_doc_code = 'nb'  # 'nb' para Nota de Débito de Cliente (según tu código)
            journal_type = 'sale' # Diario de ventas
            
            # Determinar el tipo de movimiento de la factura original
            if active_ids:
                move = self.env['account.move'].browse(active_ids)
                # La Nota de Débito de Cliente se aplica a 'out_invoice'
                if move and move.move_type in ('out_invoice', 'out_receipt'):
                    tipo_doc_code = 'nb'
                    journal_type = 'sale'
                # La Nota de Débito de Proveedor se aplica a 'in_invoice'
                elif move and move.move_type in ('in_invoice', 'in_receipt'):
                    tipo_doc_code = 'nb'  # 'nd' para Nota de Débito de Proveedor (según tu requerimiento)
                    journal_type = 'purchase' # Diario de compras
            
            # 3. Buscar el diario con los criterios específicos:
            journal = self.env['account.journal'].search([
                ('company_id', '=', company_id),
                ('type', '=', journal_type),  # 'sale' o 'purchase'
                ('tipo_doc', '=', tipo_doc_code), # 'nb' o 'nd'
            ], limit=1)
            #raise UserError(_("diario=%s")%journal.name)
            # 4. Asignar el ID del diario si se encuentra
            if journal:
                res['journal_id'] = journal.id

        return res


    def _prepare_default_values(self, move):
        #raise UserError(_('move tipo=%s')%move.type)
        if move.move_type in ('in_refund', 'out_refund'):
            type = 'in_invoice' if move.move_type == 'in_refund' else 'out_invoice'
        else:
            type = move.move_type
        if move.move_type=='in_invoice':
            type='in_receipt'
        if move.move_type=='out_invoice':
            type='out_receipt'
        #raise UserError(_('move tipo2=%s')%type)
        default_values = {
                'ref': '%s, %s' % (move.name, self.reason) if self.reason else move.name,
                'date': self.date or move.date,
                'invoice_date': move.is_invoice(include_receipts=True) and (self.date or move.date) or False,
                'journal_id': self.journal_id and self.journal_id.id or move.journal_id.id,
                'invoice_payment_term_id': None,
                'debit_origin_id': move.id,
                'move_type': type,
                'fact_afect':move.invoice_number_next,
                'tasa': self.tasa(self.date,move),
            }
        if not self.copy_lines or move.move_type in [('in_refund', 'out_refund')]:
            default_values['line_ids'] = [(5, 0, 0)]
        return default_values

    def tasa(self,date,move):
        #raise UserError(_("xxxx"))
        result=1
        for selff in self:
            lista=selff.env['res.currency.rate'].search([('currency_id','=',move.company_id.currency_sec_id.id),('name','<=',date)],order='name desc',limit=1)
            #raise UserError(_("xx %s")%lista.inverse_company_rate)
            if lista:
                result=lista.inverse_company_rate
                #raise UserError(_("%s")%result)
            return result

    def create_debit(self):
        res=super().create_debit()
        active_ids = self.env.context.get('active_ids')
        move = self.env['account.move'].browse(active_ids)
        if move.move_type in ('out_refund','out_receipt'):
            raise UserError(_("No puedes crear una Nota de débito a partir de una nota de credito"))
            #move._log_and_raise_fiscal_error("No puedes crear una Nota de débito a partir de una nota de credito")
        return res


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'
    _check_company_auto = True

    date_nota = fields.Date(default=fields.Date.context_today)

    @api.model
    def default_get(self, fields_list):
        """
        Sobrescribe default_get para establecer el diario por defecto
        basándose en si la reversión es para facturas de clientes o proveedores.
        """
        # 1. Obtener los valores por defecto de la implementación base (Odoo)
        res = super().default_get(fields_list)

        # 2. Solo proceder si se necesita el campo 'journal_id'
        if 'journal_id' in fields_list and not res.get('journal_id'):
            company_id = self.env.company.id
            active_ids = self.env.context.get('active_ids')
            
            # Inicializar variables para la búsqueda del diario
            tipo_doc_code = False
            journal_type = False
            date = False
            
            # 3. Determinar el tipo de movimiento de la factura original
            if active_ids:
                # Buscamos la factura original sobre la que se hace la reversión
                move = self.env['account.move'].browse(active_ids)
                if move:
                    if move.invoice_date:
                        res['date'] = move.invoice_date # Colocamos por defecto la fecha de la factura afectada
                
                if move and move.move_type in ('out_invoice', 'out_receipt'):
                    # Caso 1: Reversión de Factura de Cliente (Nota de Crédito de Cliente)
                    tipo_doc_code = 'nc'    # El código que usas para NC de Cliente
                    journal_type = 'sale'   # Diario de ventas
                    
                    
                elif move and move.move_type in ('in_invoice', 'in_receipt'):
                    # Caso 2: Reversión de Factura de Proveedor (Nota de Crédito de Proveedor)
                    # Usaremos 'ndp' (Nota de Crédito de Proveedor) como ejemplo para diferenciar,
                    # o el código que uses para este tipo de diario.
                    tipo_doc_code = 'nc' # <-- Ajusta este código si es diferente
                    journal_type = 'purchase' # Diario de compras
                    

            # 4. Buscar el diario con los criterios específicos si se determinó el tipo
            if tipo_doc_code and journal_type:
                journal = self.env['account.journal'].search([
                    ('company_id', '=', company_id),
                    ('type', '=', journal_type),     # 'sale' o 'purchase'
                    ('tipo_doc', '=', tipo_doc_code), # 'nc' o 'ndp'
                ], limit=1)

                # 5. Asignar el ID del diario si se encuentra
                if journal:
                    res['journal_id'] = journal.id

        return res

    

    def _prepare_default_reversal(self, move):
        reverse_date = self.date
        mixed_payment_term = move.invoice_payment_term_id.id if move.invoice_payment_term_id.early_pay_discount_computation == 'mixed' else None
        #raise UserError(_('move tipo2=%s')%move.invoice_number_next)
        return {
            'ref': _('Reversal of: %(move_name)s, %(reason)s', move_name=move.name, reason=self.reason)
                   if self.reason
                   else _('Reversal of: %s', move.name),
            'date': reverse_date,
            'invoice_date_due': reverse_date,
            'invoice_date': move.is_invoice(include_receipts=True) and (self.date or move.date) or False,
            'journal_id': self.journal_id.id,
            'invoice_payment_term_id': mixed_payment_term,
            'invoice_user_id': move.invoice_user_id.id,
            'auto_post': 'at_date' if reverse_date > fields.Date.context_today(self) else 'no',
            'fact_afect':move.invoice_number_next,
            'tasa':self.tasa(reverse_date,move),
            'date_nota_credito':self.date_nota,
            'date_fact_afectada':reverse_date,
        }


    def tasa(self,date,move):
        #raise UserError(_("xxxx"))
        result=1
        for selff in self:
            lista=selff.env['res.currency.rate'].search([('currency_id','=',move.company_id.currency_sec_id.id),('name','<=',date)],order='name desc',limit=1)
            #raise UserError(_("xx %s")%lista.inverse_company_rate)
            if lista:
                result=lista.inverse_company_rate
                #raise UserError(_("%s")%result)
            return result

    

    

    def refund_moves(self):
        # 1. Obtener los registros de la factura original
        active_ids = self.env.context.get('active_ids')
        original_moves = self.env['account.move'].browse(active_ids)
        
        # --- NUEVA VALIDACIÓN: PREVENCIÓN DE SOBRE-REVERSIÓN ---
        for original_move in original_moves:
            # Buscamos todas las notas de crédito vinculadas a esta factura
            notas_credito_existentes = self.env['account.move'].search([
                ('reversed_entry_id', '=', original_move.id),
                ('state', '!=', 'cancel')
            ])
            
            # Sumamos los totales de las NC previas
            total_nc_acumulado = sum(notas_credito_existentes.mapped('amount_total'))
            
            # Si el acumulado ya es igual o mayor al total original, bloqueamos
            if total_nc_acumulado >= original_move.amount_total:
                original_move._log_and_raise_fiscal_error("No se puede crear una Nota de Crédito. La factura %s ya ha sido totalmente reversada por otras notas de crédito acumuladas." % original_move.name)
                #raise UserError(_("No se puede crear una Nota de Crédito. La factura %s ya ha sido totalmente reversada por otras notas de crédito acumuladas.") % original_move.name)

        # 2. Ejecutar la creación estándar de la Nota de Crédito
        res = super().refund_moves()
        
        # 3. Obtener los IDs de las Notas de Crédito recién creadas
        new_move_id = res.get('res_id')
        new_move_ids = [new_move_id] if new_move_id else []
        
        if not new_move_id and res.get('domain'):
            for domain_part in res.get('domain'):
                if isinstance(domain_part, (list, tuple)) and domain_part[0] == 'id':
                    new_move_ids = domain_part[2]
                    break

        # 4. Procesar las nuevas Notas de Crédito (Preservando tu lógica original)
        if new_move_ids:
            new_moves = self.env['account.move'].browse(new_move_ids)
            
            for i, move in enumerate(new_moves):
                orig_move = original_moves[i] if len(original_moves) > i else original_moves[0]

                # --- TU LÓGICA DE IGTF ---
                if orig_move.igtf_ids:
                    for line in orig_move.igtf_ids:
                        line.copy({
                            'move_id': move.id,
                            'asiento_igtf': False, 
                            'payment_id': False,
                        })

                # --- TU LÓGICA DE LÍNEAS EXENTAS ---
                lines_to_delete = move.invoice_line_ids.filtered(lambda l: l.linea_exenta)
                if lines_to_delete:
                    move.write({
                        'invoice_line_ids': [(2, line.id) for line in lines_to_delete]
                    })
            
        return res