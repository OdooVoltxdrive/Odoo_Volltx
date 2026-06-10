# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class FleetVehicleContractLine(models.Model):
    _name = "fleet.vehicle.contract.line"
    _description = "Líneas de Cuotas de Contrato"
    _order = "numero_cuota asc"

    contract_id = fields.Many2one("fleet.vehicle.log.contract", string="Contrato", ondelete="cascade")
    numero_cuota = fields.Integer(string="N° Cuota", required=True)
    fecha_vencimiento = fields.Date(string="Fecha de Vencimiento", required=True)
    monto = fields.Float(string="Monto a Pagar ($)", required=True)
    
    # Relación con la factura contable real de Odoo
    invoice_id = fields.Many2one("account.move", string="Factura de Cliente", ondelete="set null")
    
    # Estado calculado o definido según la factura
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('posted', 'Facturado / Esperando Pago'),
        ('paid', 'Pagada 100%'),
        ('overdue', 'En Mora ⚠️')
    ], string="Estado de la Cuota", default="draft", compute="_compute_state", store=True)

    @api.depends('invoice_id', 'invoice_id.payment_state', 'fecha_vencimiento')
    def _compute_state(self):
        hoy = fields.Date.today()
        for line in self:
            if not line.invoice_id:
                # Si no hay factura y ya pasó la fecha, está en mora, si no, pendiente
                line.state = 'overdue' if line.fecha_vencimiento < hoy else 'draft'
            else:
                # Evaluamos el estado nativo de la factura de Odoo
                if line.invoice_id.payment_state == 'paid':
                    line.state = 'paid'
                elif line.invoice_id.payment_state in ['not_paid', 'partial'] and line.fecha_vencimiento < hoy:
                    line.state = 'overdue'
                else:
                    line.state = 'posted'