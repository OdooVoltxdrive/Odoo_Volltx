from odoo import models, _, api
from odoo.exceptions import AccessError
import datetime

NUMBER_FIGURE_TYPES = ('float', 'integer', 'monetary', 'percentage')


class AccountReport(models.Model):
    _inherit = 'account.report'

    def _init_options_currencies(self, options, previous_options=None):
        currencies = self.env['res.currency'].search([])
        options['currencies'] = [{'id': c.id, 'name': _(c.name)} for c in currencies]

        selected_currency_id = previous_options.get('selected_currencies_id')
        selected_currency_name = previous_options.get('selected_currencies')

        if selected_currency_id:
            options['selected_currencies'] = self.env['res.currency'].browse(selected_currency_id).name
        else:
            options['selected_currencies'] = selected_currency_name or self.env.company.currency_id.name

    def _build_column_dict(self, col_value, col_data, options=None, currency=False, digits=1,
                           column_expression=None, has_sublines=False, report_line_id=None):
        if col_value is None and col_data is None:
            return {}

        date_obj = datetime.datetime.strptime(options['date']['date_to'], '%Y-%m-%d').date()
        currency_id = self.env.company.currency_id

        to_currency = self.env['res.currency'].search([('name', '=', options['selected_currencies'])], limit=1)
        if isinstance(col_value, (int, float)) and to_currency:
            col_value = currency_id._convert(col_value, to_currency, date=date_obj)
            currency = to_currency

        col_data = col_data or {}
        column_expression = column_expression or self.env['account.report.expression']
        options = options or {}

        figure_type = column_expression.figure_type or col_data.get('figure_type', 'string')
        format_params = {'currency_id': currency.id} if figure_type == 'monetary' and currency else {}
        if figure_type in ('float', 'percentage'):
            format_params['digits'] = digits

        col_group_key = col_data.get('column_group_key')
        return {
            'auditable': col_value is not None and column_expression.auditable
                         and not options['column_groups'][col_group_key]['forced_options'].get('compute_budget'),
            'blank_if_zero': column_expression.blank_if_zero or col_data.get('blank_if_zero', False),
            'column_group_key': col_group_key,
            'currency': currency.id if currency else None,
            'currency_symbol': self.env.company.currency_id.symbol if options.get('multi_currency') else None,
            'digits': digits,
            'expression_label': col_data.get('expression_label'),
            'figure_type': figure_type,
            'green_on_positive': column_expression.green_on_positive,
            'has_sublines': has_sublines,
            'is_zero': col_value is None or (isinstance(col_value, (int, float)) and figure_type in NUMBER_FIGURE_TYPES
                                             and self._is_value_zero(col_value, figure_type, format_params)),
            'no_format': col_value,
            'format_params': format_params,
            'report_line_id': report_line_id,
            'sortable': col_data.get('sortable', False),
            'comparison_mode': col_data.get('comparison_mode'),
        }

    def _init_options_rounding_unit(self, options, previous_options=None):
        options['rounding_unit'] = previous_options.get('rounding_unit', 'decimals') if previous_options else 'decimals'

        currency_name = previous_options.get('selected_currencies') or self.env.company.currency_id.name
        currency_obj = self.env['res.currency'].search([('name', '=', currency_name)],
                                                       limit=1) or self.env.company.currency_id
        options['rounding_unit_names'] = self._get_rounding_unit_names(currency_obj)

    def _get_rounding_unit_names(self, currency_obj):
        currency_symbol = currency_obj.symbol or self.env.company.currency_id.symbol
        return {
            'decimals': f'.{currency_symbol}',
            'units': f'U {currency_symbol}',  # Ensures length >= 2
            'thousands': f'K{currency_symbol}',
            'millions': f'M{currency_symbol}',
        }

