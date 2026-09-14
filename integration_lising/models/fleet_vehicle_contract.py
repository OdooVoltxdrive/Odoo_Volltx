# See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class FleetVehicleLogContract(models.Model):
    _inherit = "fleet.vehicle.log.contract"

    # 1. Asegúrate de que los campos estén declarados exactamente con estos nombres
    total_cuotas = fields.Integer(string="Total de Cuotas")
    precio_cuota = fields.Float(string="Precio de cada Cuota ($)")
    
    monto_total_contrato = fields.Float(
        string="Monto Total ($)", 
        compute="_compute_monto_total", 
        store=True
    )

    # Nueva pestaña de trazabilidad
    contract_line_ids = fields.One2many(
        "fleet.vehicle.contract.line", "contract_id", string="Plan de Cuotas"
    )

    # Chips de facturas del contrato (borradores y confirmadas, incluidos abonos).
    # Los borradores los enlaza el backend; las confirmadas las agrega
    # account.move.action_post() vía contract_line_id.
    invoice_ids = fields.Many2many(
        "account.move", relation="fleet_vehicle_log_contract_invoice_rel",
        column1="contract_id", column2="move_id", string="Facturas"
    )

    # Tasa Bs/$ usada para las columnas en Bs del plan (la escribe el backend
    # con la tasa real del pago).
    tasa_cambio = fields.Float(string="Tasa de Cambio (Bs por $)")

    # Moneda de visualización ($) del formulario: solo cambia el símbolo
    # mostrado en los widgets monetary; la moneda contable queda intacta.
    currency_usd_id = fields.Many2one("res.currency", string="Moneda de visualización ($)")

    @api.depends("total_cuotas", "precio_cuota","contract_line_ids.monto")
    def _compute_monto_total(self):
        """Calcula el valor total: Tarifa Diaria x 30 días x N° de Meses"""
        for contract in self:
            # Multiplicamos el valor diario por 30 para sacar el mes comercial, y luego por los meses totales
            contract.monto_total_contrato = (
                contract.precio_cuota * contract.total_cuotas
            )


    def action_generar_plan_cuotas(self):
        """Este método es el que ejecuta el botón manual e inyecta las líneas en contract_line_ids"""
        self.ensure_one()
        # Limpiamos el One2many por si ejecutan el botón más de una vez
        self.contract_line_ids.unlink()

        lineas = []
        # CORRECCIÓN AQUÍ: Se cambió 'date_start' por 'start_date' nativo de Odoo 19
        fecha_inicial = self.start_date or fields.Date.today()
        
        # El monto de la factura mensual basado en tus campos (Tarifa diaria x 30)
        monto_mensual_fijo = self.precio_cuota 

        for i in range(1, self.total_cuotas + 1):
            # Calcula el vencimiento mes a mes a partir de la fecha de inicio del contrato
            fecha_vencimiento = fecha_inicial + relativedelta(months=i)

            lineas.append((0, 0, {
                'numero_cuota': i,
                'fecha_vencimiento': fecha_vencimiento,
                'monto': monto_mensual_fijo,
                'state': 'draft'
            }))
            
        # Inyectamos de golpe todas las líneas generadas en tu campo contract_line_ids
        self.write({'contract_line_ids': lineas})
        
        return True

    def action_ver_facturas(self):
        """Abre las facturas (borradores y confirmadas) ligadas a este contrato."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facturas del contrato',
            'res_model': 'account.move',
            'domain': [('contract_line_id.contract_id', '=', self.id)],
            'context': {'default_move_type': 'out_invoice'},
            'views': [(False, 'list'), (False, 'form')],
            'target': 'current',
        }