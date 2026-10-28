from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    purchaser_id = fields.Many2one(
        'res.partner',
        string='Driver',
        related=False,
        compute='_compute_purchaser_id',
        inverse='_inverse_purchaser_id',
        store=True,
        readonly=False,
        # La validación ORM permite conservar contratos heredados sin inventar su conductor.
        required=False,
        ondelete='restrict',
        tracking=True,
        help="Conductor titular único asignado a este contrato"
    )

    @api.depends('vehicle_id.driver_id')
    def _compute_purchaser_id(self):
        for contract in self:
            if not contract.purchaser_id:
                contract.purchaser_id = contract.vehicle_id.driver_id

    def _inverse_purchaser_id(self):
        pass

    # Turno configurado como texto libre (ej: '08:00 a 16:00')

    start_time = fields.Char(string='Inicio')
    end_time = fields.Char(string='Fin ')
    shift = fields.Char(string='Zona de retorno ')
    liquidation_ids = fields.One2many('fleet.weekly.liquidation', 'contract_id', string='Weekly Liquidations')
    vehicle_driver_ids = fields.Many2many(related='vehicle_id.driver_ids')

    cost_generate = fields.Monetary(string="Costo paquete", currency_field='secondary_currency_id')

    secondary_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda Secundaria',
        compute='_compute_secondary_currency'
    )

    def _compute_secondary_currency(self):
        for contract in self:
            usd = self.env.ref('base.USD', raise_if_not_found=False)
            contract.secondary_currency_id = usd.id if usd else contract.company_id.currency_id.id

    invoice_count = fields.Integer(compute='_compute_invoice_count', string='Invoice Count')

    @api.depends('liquidation_ids.invoice_id')
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.liquidation_ids.mapped('invoice_id'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super(FleetVehicleLogContract, self).create(vals_list)
        for record, vals in zip(records, vals_list):
            driver_val = vals.get('purchaser_id') or self.env.context.get('default_purchaser_id')
            if driver_val and record.purchaser_id.id != driver_val:
                super(FleetVehicleLogContract, record).write({'purchaser_id': driver_val})
        if records.filtered(lambda contract: not contract.purchaser_id):
            raise ValidationError(_("Debe asignar un conductor al contrato."))
        return records

    def write(self, vals):
        if self.env.context.get('sync_vehicle_turn') and 'purchaser_id' in vals:
            vals = dict(vals)
            del vals['purchaser_id']
            if not vals:
                return True
        if 'purchaser_id' in vals and not vals['purchaser_id'] and self.mapped('purchaser_id'):
            raise ValidationError(_("No puede quitar el conductor de un contrato asignado."))
        return super(FleetVehicleLogContract, self).write(vals)

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        saved_purchaser = self.purchaser_id
        super(FleetVehicleLogContract, self)._onchange_vehicle_id()
        if saved_purchaser:
            self.purchaser_id = saved_purchaser

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.liquidation_ids.mapped('invoice_id')
        return {
            'name': _('Invoices'),
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'domain': [('id', 'in', invoices.ids)],
            'type': 'ir.actions.act_window',
        }