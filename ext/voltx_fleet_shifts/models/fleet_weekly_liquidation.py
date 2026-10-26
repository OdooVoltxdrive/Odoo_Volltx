from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError


class FleetWeeklyLiquidation(models.Model):
    _name = 'fleet.weekly.liquidation'
    _description = 'Liquidación semanal para conductores de flotas'
    _order = 'name desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    contract_id = fields.Many2one('fleet.vehicle.log.contract', string='Contract', required=True)
    driver_id = fields.Many2one(
        'res.partner',
        string='Driver',
        compute='_compute_driver_id',
        store=True
    )
    week_of_year = fields.Char(string='Semana', required=True)

    #daily_log_ids = fields.One2many('fleet.driver.daily.log', 'liquidation_id', string='Registros diarios')

    #days_worked = fields.Integer(string='Días/Servicios', compute='_compute_totals', store=True)
    #total_hours = fields.Float(string='Horas/Servicios', compute='_compute_totals', store=True)
    """amount_total = fields.Monetary(
        string='Tarifa Total',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )"""

    currency_id = fields.Many2one('res.currency', related='contract_id.company_id.currency_id')
    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('invoiced', 'Factura'),
        ('paid', 'Pago')
    ], default='draft', string='Status', compute='_compute_state', store=True)

    @api.depends('contract_id.purchaser_id')
    def _compute_driver_id(self):
        for liq in self:
            liq.driver_id = liq.contract_id.purchaser_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.weekly.liquidation') or 'New'
        records = super().create(vals_list)
        for record in records:
            record._link_daily_logs()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'week_of_year' in vals or 'contract_id' in vals:
            for record in self:
                record._link_daily_logs()
        return res

    def _link_daily_logs(self):
        for liq in self:
            if liq.contract_id and liq.week_of_year:
                logs = self.env['fleet.driver.daily.log'].search([
                    ('contract_id', '=', liq.contract_id.id),
                    ('week_of_year', '=', liq.week_of_year),
                    ('liquidation_id', '=', False),
                    ('state', '=', 'done')
                ])
                if logs:
                    logs.write({'liquidation_id': liq.id})

    #@api.depends('daily_log_ids.worked', 'daily_log_ids.hours_worked', 'contract_id.cost_generate')
    """def _compute_totals(self):
        for liq in self:
            worked_logs = liq.daily_log_ids.filtered(lambda l: l.worked)
            liq.days_worked = len(worked_logs)
            liq.total_hours = sum(worked_logs.mapped('hours_worked'))

            # Usar cost_generate en lugar del amount nativo como solicitó el usuario
            daily_rate = liq.contract_id.cost_generate if liq.contract_id else 0.0
            liq.amount_total = liq.days_worked * daily_rate"""

    #@api.depends('invoice_id.state', 'invoice_id.payment_state')
    """def _compute_state(self):
        for liq in self:
            if not liq.invoice_id:
                liq.state = 'draft'
            elif liq.invoice_id.payment_state in ('in_payment', 'paid'):
                liq.state = 'paid'
                # Pasa a paid cuando la factura contable se pague realmente
                liq.daily_log_ids.write({'state': 'paid'})
            else:
                liq.state = 'invoiced'"""

    def _auto_generate_or_update_invoice(self):
        """Genera o actualiza la factura automáticamente sumando los días trabajados en lugar de hacerlo manualmente."""
        self.ensure_one()
        if not self.driver_id or self.days_worked <= 0:
            return

        # Si ya existe una factura en borrador, simplemente actualizamos la cantidad
        if self.invoice_id and self.invoice_id.state == 'draft':
            # Solo actualizamos la línea que generamos para esta liquidación
            target_name_prefix = f'Liquidación Semanal {self.week_of_year} - Alquiler/Leasing Vehículo'
            for line in self.invoice_id.invoice_line_ids:
                if line.name and line.name.startswith(target_name_prefix):
                    # Actualizar la cantidad y el nombre de forma segura
                    line.quantity = self.days_worked
                    line.name = f'Liquidación Semanal {self.week_of_year} - Alquiler/Leasing Vehículo ({self.days_worked} días)'
            return

        if self.invoice_id and self.invoice_id.state != 'draft':
            # Si ya hay una factura publicada para esta liquidacion, no la modificamos
            return

        company = self.contract_id.company_id or self.env.company

        # 1. Buscar Diario de Ventas (Factura Cliente)
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id)
        ], limit=1)
        if not journal:
            return

        # 2. Cuenta de Ingresos por defecto
        account = journal.default_account_id or self.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_id', '=', company.id)
        ], limit=1)

        if not account:
            return

        # 3. Crear Factura Cliente ('out_invoice') en estado borrador
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.driver_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': f"{self.name} - {self.week_of_year}",
            'journal_id': journal.id,
            'invoice_line_ids': [
                Command.create({
                    'name': f'Liquidación Semanal {self.week_of_year} - Alquiler/Leasing Vehículo ({self.days_worked} días)',
                    'quantity': self.days_worked,
                    'price_unit': self.contract_id.cost_generate,
                    'account_id': account.id,
                })
            ],
        }

        move = self.env['account.move'].create(invoice_vals)
        self.invoice_id = move.id

    def action_generate_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            raise UserError(_("Ya existe una factura vinculada a esta liquidación."))
        if not self.driver_id:
            raise UserError(_("El contrato no tiene conductor asignado."))
        if self.days_worked <= 0:
            raise UserError(_("No se puede generar factura para una liquidación con 0 días trabajados."))

        company = self.contract_id.company_id or self.env.company

        # 1. Buscar Diario de Ventas (Factura Cliente)
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id)
        ], limit=1)
        if not journal:
            raise UserError(_("Por favor configure un diario de ventas para la compañía '%s'.") % company.name)

        # 2. Cuenta de Ingresos por defecto
        account = journal.default_account_id or self.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_id', '=', company.id)
        ], limit=1)

        if not account:
            raise UserError(_("Configure una cuenta de ingresos en el diario de ventas o en el plan contable."))

        # 3. Crear Factura Cliente ('out_invoice')
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.driver_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': f"{self.name} - {self.week_of_year}",
            'journal_id': journal.id,
            'invoice_line_ids': [
                Command.create({
                    'name': f'Liquidación Semanal {self.week_of_year} - Alquiler/Leasing Vehículo ({self.days_worked} días)',
                    'quantity': self.days_worked,
                    'price_unit': self.contract_id.cost_generate,
                    'account_id': account.id,
                })
            ],
        }

        move = self.env['account.move'].create(invoice_vals)
        self.invoice_id = move.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }