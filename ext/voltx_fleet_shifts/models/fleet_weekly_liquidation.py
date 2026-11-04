from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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
        currency_field='currency_id'
    )
    amount_total_bs = fields.Monetary(
        string='Pago Bs',
        currency_field='bs_currency_id'
    )

    # Monedas
    currency_id = fields.Many2one(
        'res.currency',
        related='contract_id.secondary_currency_id',
        string='Moneda USD'
    )
    bs_currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_bs_currency',
        string='Moneda Bs'
    )

    fiscal_breakdown = fields.Json(string='Desglose fiscal VoltX', readonly=True, copy=False)
    invoice_id = fields.Many2one('account.move', string='Factura', readonly=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('invoiced', 'Factura'),
        ('paid', 'Pagado')
    ], default='draft', string='Status', compute='_compute_state', store=True)


    def _compute_bs_currency(self):
        bs = self.env.ref('base.VES')
        for liq in self:
            liq.bs_currency_id = bs

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
        if {'fiscal_breakdown', 'amount_total_usd', 'amount_total_bs', 'contract_id', 'invoice_id'} & vals.keys():
            if any(record.invoice_id and (record.fiscal_breakdown or vals.get('fiscal_breakdown')) for record in self):
                raise UserError(_('No se puede modificar una liquidación fiscal ya facturada.'))
        res = super().write(vals)
        # Si se ingresa o actualiza el monto en USD o Bs y no tiene factura, se dispara la creación
        if ('amount_total_usd' in vals or 'amount_total_bs' in vals) and not self.env.context.get('skip_invoice_sync'):
            for record in self:
                if not record.invoice_id and (record.amount_total_usd > 0 or record.amount_total_bs > 0):
                    record._auto_generate_invoice()
        return res

    @api.constrains('fiscal_breakdown', 'amount_total_usd', 'amount_total_bs')
    def _check_fiscal_breakdown(self):
        for record in self:
            if record.fiscal_breakdown:
                record._fiscal_amounts()

    def _fiscal_amounts(self):
        self.ensure_one()
        data = self.fiscal_breakdown
        error = _('ODOO_LIQUIDATION_TAX_MAPPING_REQUIRED: desglose fiscal VES inválido.')
        if not isinstance(data, dict) or set(data) != {'version', 'currency', 'base', 'service', 'vat', 'total'}:
            raise UserError(error)
        if type(data['version']) is not int or data['version'] != 1 or data['currency'] != 'VES':
            raise UserError(error)
        amounts = {}
        for key in ('base', 'service', 'vat', 'total'):
            try:
                if isinstance(data[key], bool) or not isinstance(data[key], (str, int, float)):
                    raise ValueError()
                value = Decimal(str(data[key]))
                if not value.is_finite() or value < 0 or value != value.quantize(Decimal('0.01')):
                    raise ValueError()
                amounts[key] = value
            except (InvalidOperation, ValueError):
                raise UserError(error) from None
        taxable = amounts['base'] + amounts['service']
        if (amounts['base'] <= 0 or amounts['total'] <= 0
                or (taxable * Decimal('0.16')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) != amounts['vat']
                or taxable + amounts['vat'] != amounts['total']
                or self.amount_total_usd != 0 or Decimal(str(self.amount_total_bs)) != amounts['total']):
            raise UserError(error)
        return amounts

    def _fiscal_invoice_lines(self, company, rental, account, description):
        amounts = self._fiscal_amounts()
        service = company.voltx_service_product_id
        if amounts['service'] and not service:
            raise UserError(_('ODOO_LIQUIDATION_SERVICE_MAPPING_REQUIRED: contabilidad debe confirmar el producto de servicio de la compañía.'))
        lines = []
        for product, value, label in ((rental, amounts['base'], description), (service, amounts['service'], _('Servicio — ') + description)):
            if not value:
                continue
            if not product or not product.active or not product.sale_ok or (product.company_id and product.company_id != company):
                raise UserError(_('ODOO_LIQUIDATION_SERVICE_MAPPING_REQUIRED: producto de venta inválido.'))
            taxes = product.taxes_id.filtered(lambda tax: tax.company_id == company)
            if (len(taxes) != 1 or taxes.amount_type != 'percent' or taxes.amount != 16
                    or taxes.price_include or taxes.include_base_amount or taxes.type_tax_use != 'sale'):
                raise UserError(_('ODOO_LIQUIDATION_TAX_MAPPING_REQUIRED: los productos deben tener únicamente IVA de venta 16 % no incluido.'))
            income = product.with_company(company).property_account_income_id or product.categ_id.with_company(company).property_account_income_categ_id
            if product == service and (not income or income.account_type not in ('income', 'income_other')):
                raise UserError(_('ODOO_LIQUIDATION_SERVICE_MAPPING_REQUIRED: confirmar la cuenta de ingresos del producto de servicio.'))
            lines.append(Command.create({
                'product_id': product.id, 'name': label, 'quantity': 1,
                'price_unit': float(value), 'account_id': (income or account).id,
                'tax_ids': [Command.set(taxes.ids)],
            }))
        return lines

    def _auto_generate_invoice(self):
        """Genera la factura borrador manteniendo la estructura contable original."""
        self.ensure_one()
        if self.invoice_id or not self.driver_id:
            return

        amount = self.amount_total_usd if self.amount_total_usd > 0 else self.amount_total_bs
        if amount <= 0:
            return

        company = self.contract_id.company_id or self.env.company
        currency = self.currency_id if self.amount_total_usd > 0 else self.bs_currency_id

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
            'state': 'draft',
            'company_id': company.id,
            'currency_id': currency.id,
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

        if self.fiscal_breakdown:
            invoice_vals['invoice_line_ids'] = self._fiscal_invoice_lines(company, product, account, line_desc)
        # Este contexto también controla los cálculos contables nativos de Odoo.
        move = self.env['account.move'].with_context(skip_invoice_sync=False).create(invoice_vals)
        if self.fiscal_breakdown:
            amounts = self._fiscal_amounts()
            if (currency.compare_amounts(move.amount_total, float(amounts['total']))
                    or currency.compare_amounts(move.amount_tax, float(amounts['vat']))
                    or currency.compare_amounts(move.amount_untaxed, float(amounts['base'] + amounts['service']))):
                raise UserError(_('ODOO_LIQUIDATION_TAX_MAPPING_REQUIRED: los cálculos nativos de Odoo no coinciden con el cobro; no se conserva el borrador.'))
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