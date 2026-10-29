from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMoveMassConfirm(models.TransientModel):
    _name = 'account.move.mass.confirm'
    _description = 'Confirmación Masiva de Facturas'

    date_from = fields.Date(string='Fecha desde')
    date_to = fields.Date(string='Fecha hasta')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)

    def action_confirm_invoices(self):
        self.ensure_one()

        domain = [
            ('state', '=', 'draft'),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('company_id', '=', self.company_id.id)
        ]

        if self.date_from:
            domain.append(('invoice_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('invoice_date', '<=', self.date_to))
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))

        invoices = self.env['account.move'].search(domain)

        if not invoices:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin facturas'),
                    'message': _('No se encontraron facturas en estado borrador para los filtros seleccionados.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        for invoice in invoices:
            invoice.action_post()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': _('Se confirmaron %s facturas correctamente.') % len(invoices),
                'type': 'success',
                'sticky': False,
            }
        }
