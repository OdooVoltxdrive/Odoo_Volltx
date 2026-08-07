# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class AccountMove(models.Model):
    _inherit = 'account.move'

    date_nota_credito = fields.Date()
    date_fact_afectada = fields.Date()



    def action_post(self):
        res = super().action_post()
        self.reajuste_fecha_nc()
        return res




    def reajuste_fecha_nc(self):
        for move in self:
            if move.date_nota_credito:
                # 1. Actualizamos el encabezado (account.move)
                self.env.cr.execute("""
                    UPDATE account_move 
                    SET invoice_date = %s, date = %s 
                    WHERE id = %s
                """, (move.date_nota_credito, move.date_nota_credito, move.id))
                
                # 2. Actualizamos las líneas (account.move.line)
                # En las líneas, el campo relevante es 'date'
                self.env.cr.execute("""
                    UPDATE account_move_line 
                    SET date = %s, invoice_date =%s
                    WHERE move_id = %s
                """, (move.date_nota_credito, move.date_nota_credito,move.id))
                
                # 3. Invalidar caché para que Odoo refresque los datos en UI y lógica
                move.invalidate_recordset(fnames=['invoice_date', 'date'])
                move.line_ids.invalidate_recordset(fnames=['date'])

                # Tu lógica adicional de alícuotas
                for det in move.alicuota_line_ids:
                    det.fecha_fact = move.date_nota_credito