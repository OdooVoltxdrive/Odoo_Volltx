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
    observation = fields.Text(string='Observación de Pago / Semana')

    # Campos de pago en moneda extranjera y local
    amount_total_usd = fields.Monetary(
        string='Pago $',
        currency_field='currency_id',
        tracking=True
    )
    amount_total_bs = fields.Monetary(
        string='Pago Bs',
        tracking=True
    )

    # Monedas
    currency_id = fields.Many2one(
        'res.currency',
        related='contract_id.secondary_currency_id',
        string='Moneda USD'
    )


    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('invoiced', 'Factura'),
        ('paid', 'Pagado')
    ], default='draft', string='Status', compute='_compute_state', store=True)


    @api.depends('contract_id.purchaser_id')
    def _compute_driver_id(self):
        for liq in self:
            liq.driver_id = liq.contract_id.purchaser_id

    @api.depends('invoice_id.state', 'invoice_id.payment_state')
    def _compute_state(self):
        for liq in self:
            if not liq.invoice_id:
                liq.state = 'draft'
            elif liq.invoice_id.payment_state in ('in_payment', 'paid'):
                liq.state = 'paid'
            else:
                liq.state = 'invoiced'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.weekly.liquidation') or 'New'
        records = super().create(vals_list)
        # Si al crear el registro ya se incluye un importe en USD o Bs, se crea la factura
        for record in records:
            if (record.amount_total_usd > 0 or record.amount_total_bs > 0) and not record.invoice_id:
                record._auto_generate_invoice()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Si se ingresa o actualiza el monto en USD o Bs y no tiene factura, se dispara la creación
        if ('amount_total_usd' in vals or 'amount_total_bs' in vals) and not self.env.context.get('skip_invoice_sync'):
            for record in self:
                if not record.invoice_id and (record.amount_total_usd > 0 or record.amount_total_bs > 0):
                    record._auto_generate_invoice()
        return res

    def _auto_generate_invoice(self):
        """Genera la factura borrador manteniendo la estructura contable original."""
        self.ensure_one()
        if self.invoice_id or not self.driver_id:
            return

        amount = self.amount_total_usd if self.amount_total_usd > 0 else self.amount_total_bs
        if amount <= 0:
            return

        company = self.contract_id.company_id or self.env.company

        # 1. Diario de Ventas
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id)
        ], limit=1)
        if not journal:
            return

        # 2. Cuenta de Ingresos
        account = journal.default_account_id or self.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_id', '=', company.id)
        ], limit=1)
        if not account:
            return

        # 3. Producto de la plantilla (ID 27)
        product = self.env['product.template'].browse(27).product_variant_id

        # 4. Descripción de la línea
        vehicle_name = self.contract_id.vehicle_id.name or ''
        line_desc = f"Liquidación Semanal {self.week_of_year} - Alquiler/Leasing Vehículo {vehicle_name}".strip()
        if self.observation:
            line_desc += f" ({self.observation})"

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.driver_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': f"{self.name} - {self.week_of_year}",
            'journal_id': journal.id,
            'invoice_line_ids': [
                Command.create({
                    'product_id': product.id if product else False,
                    'name': line_desc,
                    'quantity': 1.0,
                    'price_unit': amount,
                    'account_id': account.id,
                })
            ],
        }

        move = self.env['account.move'].with_context(skip_invoice_sync=True).create(invoice_vals)
        self.with_context(skip_invoice_sync=True).write({'invoice_id': move.id})

    def action_generate_invoice(self):
        """Acción de botón manual para generar la factura."""
        self.ensure_one()
        if self.invoice_id:
            raise UserError(_("Ya existe una factura vinculada a esta liquidación."))
        if not self.driver_id:
            raise UserError(_("El contrato no tiene conductor asignado."))
        if self.amount_total_usd <= 0 and self.amount_total_bs <= 0:
            raise UserError(_("Debe registrar un monto en USD o en Bs para generar la factura."))

        self._auto_generate_invoice()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }