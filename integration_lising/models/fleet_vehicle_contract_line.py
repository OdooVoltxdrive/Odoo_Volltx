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

    # Todas las facturas/borradores ligados a esta cuota (incluye abonos).
    # Los crea el backend; action_post() agrega las confirmadas.
    invoice_ids = fields.Many2many(
        "account.move", relation="fleet_vehicle_contract_line_invoice_rel",
        column1="line_id", column2="move_id", string="Facturas"
    )

    # Montos cobrados (los escribe el backend con la tasa real del pago)
    monto_pagado = fields.Float(string="Monto Pagado ($)")
    monto_restante = fields.Float(string="Monto Restante ($)")
    monto_pagado_bs = fields.Float(string="Pagado (Bs)")
    monto_restante_bs = fields.Float(string="Restante (Bs)")
    
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


class AccountMove(models.Model):
    _inherit = "account.move"

    # Cuota del contrato de leasing que origina esta factura (trazabilidad:
    # lo escribe el backend al crear el borrador)
    contract_line_id = fields.Many2one(
        "fleet.vehicle.contract.line", string="Cuota del contrato", index=True, ondelete="set null"
    )

    # Bs exactos cobrados según el comprobante (las mismas fórmulas de la app)
    monto_bs = fields.Float(string="Canon exacto (Bs)")
    servicio_bs = fields.Float(string="Cargo por servicios (Bs)")
    total_bs = fields.Float(string="Total cobrado (Bs)")

    def action_post(self):
        """Al confirmar una factura ligada a una cuota: la agrega a los chips
        (invoice_ids) de la cuota y de su contrato, y marca la cuota Facturada
        (state='posted')."""
        res = super().action_post()
        for move in self.filtered(lambda m: m.move_type == 'out_invoice' and m.contract_line_id):
            line = move.contract_line_id
            line.invoice_ids = [(4, move.id)]
            line.contract_id.invoice_ids = [(4, move.id)]
            if line.state in ('draft', 'overdue'):
                line.state = 'posted'
        return res