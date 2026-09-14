# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo import Command

class FleetVehicleContractLine(models.Model):
    _name = "fleet.vehicle.contract.line"
    _description = "Líneas de Canones de Contrato"
    _order = "numero_cuota asc"

    contract_id = fields.Many2one("fleet.vehicle.log.contract", string="Contrato", ondelete="cascade")
    numero_cuota = fields.Integer(string="N° Canon", required=True)
    fecha_vencimiento = fields.Date(string="Fecha de Vencimiento", required=True)
    monto = fields.Float(string="Monto a Pagar ($)", required=True)
    
    # Relación con la factura contable real de Odoo
    invoice_id = fields.Many2one("account.move", string="Factura de Cliente", ondelete="set null")

    # Todas las facturas/borradores ligados a este canon (incluye abonos).
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
    ], string="Estado del Canon", default="draft", compute="_compute_state", store=True)

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
        "fleet.vehicle.contract.line", string="Canon del contrato", index=True, ondelete="set null"
    )

    # Bs exactos cobrados según el comprobante (las mismas fórmulas de la app)
    monto_bs = fields.Float(string="Canon exacto (Bs)")
    servicio_bs = fields.Float(string="Cargo por servicios (Bs)")
    total_bs = fields.Float(string="Total cobrado (Bs)")

    def action_post(self):
        """Al confirmar una factura ligada a un canon: la agrega a los chips
        (invoice_ids) de el canon y de su contrato, y marca el canon Facturada
        (state='posted')."""
        res = super().action_post()
        for move in self.filtered(lambda m: m.move_type == 'out_invoice' and m.contract_line_id):
            line = move.contract_line_id
            line.invoice_ids = [(4, move.id)]
            line.contract_id.invoice_ids = [(4, move.id)]
            if line.state in ('draft', 'overdue'):
                line.state = 'posted'
        return res

    def action_transformar_moneda(self):
        """Convierte el borrador de una factura del leasing entre Bs y USD
        (misma factura, misma línea: los importes se reescriben con la tasa
        del comprobante).

        - Bs -> USD: reconstruye canon + servicio SIN IVA ni IGTF; si el
          contexto trae 'efectivo' agrega una línea IGTF 3% del total.
        - USD -> Bs: reconstruye canon + servicio con el IVA 16% y actualiza
          el bloque de Bs exactos.
        """
        self.ensure_one()
        if self.state != 'draft' or self.move_type != 'out_invoice' or not self.contract_line_id:
            raise UserError('Solo facturas borrador de cliente ligadas a un canon del leasing.')

        compania = self.company_id.currency_id
        es_bs = self.currency_id == compania
        tasa = self.tasa or self.invoice_currency_rate
        if not tasa or tasa <= 0:
            raise UserError('Sin tasa del comprobante: no se puede convertir la factura.')

        canon = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and 'Canon' in (l.name or ''))
        servicio = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and 'servicios' in (l.name or '').lower())
        if not canon or not servicio:
            raise UserError('La factura no tiene las líneas de Canon y Cargo por servicios.')
        canon, servicio = canon[0], servicio[0]

        if es_bs:
            # Bs -> USD: sin IVA ni IGTF (opción Efectivo agrega IGTF 3%).
            # Las líneas llevan el impuesto EXENTO (0%): el desglose venezolano
            # del footer las clasifica como exentas y el Sub-Total sale bien.
            tax_exento = self.env['account.tax'].search(
                [('type_tax_use', '=', 'sale'), ('amount', '=', 0)], limit=1)
            canon_usd = round(canon.price_unit / tasa, 2)
            servicio_usd = round(servicio.price_unit / tasa, 2)
            lineas = [
                Command.create({
                    'name': 'Canon de arrendamiento operativo de vehículo',
                    'product_id': canon.product_id.id, 'account_id': canon.account_id.id,
                    'quantity': 1, 'price_unit': canon_usd,
                    'tax_ids': [(6, 0, tax_exento.ids)] if tax_exento else [],
                }),
                Command.create({
                    'name': 'Cargo por servicios',
                    'quantity': 1, 'price_unit': servicio_usd,
                    'tax_ids': [(6, 0, tax_exento.ids)] if tax_exento else [],
                }),
            ]
            if self.env.context.get('efectivo'):
                igtf = round((canon_usd + servicio_usd) * 0.03, 2)
                lineas.append(Command.create({
                    'name': 'IGTF 3% (pago en efectivo)',
                    'quantity': 1, 'price_unit': igtf, 'tax_ids': [],
                }))
            self.write({'currency_id': self.env.ref('base.USD').id, 'invoice_line_ids': [Command.clear()] + lineas})
        else:
            # USD -> Bs: canon + servicio con IVA 16%; el bloque de Bs se reescribe
            canon_bs = round(canon.price_unit * tasa, 2)
            servicio_bs = round(servicio.price_unit * tasa, 2)
            tax16 = self.env['account.tax'].search(
                [('type_tax_use', '=', 'sale'), ('amount', '=', 16)], limit=1)
            lineas = [
                Command.create({
                    'name': 'Canon de arrendamiento operativo de vehículo',
                    'product_id': canon.product_id.id, 'account_id': canon.account_id.id,
                    'quantity': 1, 'price_unit': canon_bs,
                    'tax_ids': [(6, 0, tax16.ids)] if tax16 else [],
                }),
                Command.create({
                    'name': 'Cargo por servicios',
                    'quantity': 1, 'price_unit': servicio_bs,
                    'tax_ids': [(6, 0, tax16.ids)] if tax16 else [],
                }),
            ]
            self.write({'currency_id': compania.id, 'invoice_line_ids': [Command.clear()] + lineas})
            self.write({
                'monto_bs': canon_bs,
                'servicio_bs': servicio_bs,
                'total_bs': round((canon_bs + servicio_bs) * 1.16, 2),
            })
        return True