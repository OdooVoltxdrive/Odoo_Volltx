from odoo import models
from odoo.addons.account_reports.models import account_report

def patched_set_xlsx_cell_sizes(self, sheet, fonts, x, y, value, style, is_merged=False):
    col = x
    row = y

    # En xlsxwriter, las dimensiones de columnas se guardan internamente en el diccionario `col_sizes`
    # pero bajo un formato específico. Si no existe o no se puede acceder, usamos un fallback seguro.
    col_sizes = getattr(sheet, 'col_sizes', {})
    
    col_width_data = col_sizes.get(col, [8.43])
    col_width = col_width_data if isinstance(col_width_data, float) else col_width_data[0]

    value = str(value) if value is not None else ""
    content_width = len(value) + 2

    if col_width < content_width:
        col_sizes[col] = [content_width]
        # Aplicamos el ancho físicamente en la hoja de cálculo usando la API de xlsxwriter
        sheet.set_column(col, col, content_width)

    # De igual manera, manejamos row_sizes de forma segura usando getattr
    row_sizes = getattr(sheet, 'row_sizes', {})
    if row not in row_sizes:
        row_sizes[row] = 15
        sheet.set_row(row, 15)

# Monkey patch del método original de Odoo
account_report.AccountReport._set_xlsx_cell_sizes = patched_set_xlsx_cell_sizes