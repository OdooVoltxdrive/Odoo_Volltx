# -*- coding: utf-8 -*-
# Migración 19.0.1.0: los campos que vivían como manuales de Studio (x_*) pasan
# a ser campos del módulo. Este script copia los datos de las columnas x_* a
# las nuevas. Idempotente: si las columnas/tablas x_* no existen (instalación
# fresca), no hace nada.

MIGRATIONS = [
    # (tabla, {columna_nueva: columna_vieja})
    ("fleet_vehicle_log_contract", {
        "tasa_cambio": "x_tasa_cambio",
        "currency_usd_id": "x_usd_id",
    }),
    ("fleet_vehicle_contract_line", {
        "monto_pagado": "x_monto_pagado",
        "monto_restante": "x_monto_restante",
        "monto_pagado_bs": "x_monto_pagado_bs",
        "monto_restante_bs": "x_monto_restante_bs",
    }),
    ("account_move", {
        "contract_line_id": "x_contract_line_id",
        "monto_bs": "x_monto_bs",
        "servicio_bs": "x_servicio_bs",
        "total_bs": "x_total_bs",
    }),
]

# Many2many: {rel_nueva: (cols, rel_vieja_búsqueda)} — la vieja es la tabla
# auto-generada por Studio para x_facturas_ids
M2M = {
    "fleet_vehicle_log_contract_invoice_rel": ("fleet_vehicle_log_contract", "fleet_vehicle_log_contract_x_facturas_ids_rel"),
    "fleet_vehicle_contract_line_invoice_rel": ("fleet_vehicle_contract_line", "fleet_vehicle_contract_line_x_facturas_ids_rel"),
}


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
        [table, column],
    )
    return bool(cr.fetchone())


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM pg_class WHERE relname=%s AND relkind='r'", [table])
    return bool(cr.fetchone())


def migrate(cr, version):
    for table, mapping in MIGRATIONS:
        if not _column_exists(cr, table, list(mapping.values())[0]):
            continue
        sets = ", ".join(f"{new} = {old}" for new, old in mapping.items())
        cr.execute(f"UPDATE {table} SET {sets}")

    for rel_new, (table, rel_old) in M2M.items():
        if not _table_exists(cr, rel_old) or not _table_exists(cr, rel_new):
            continue
        # descubre los nombres de columna de la tabla vieja (los dos primeros int)
        cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=%s AND data_type='integer' ORDER BY ordinal_position LIMIT 2",
            [rel_old],
        )
        c1, c2 = (r[0] for r in cr.fetchall())
        cr.execute(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name=%s AND data_type='integer' ORDER BY ordinal_position LIMIT 2",
            [rel_new],
        )
        n1, n2 = (r[0] for r in cr.fetchall())
        cr.execute(
            f"INSERT INTO {rel_new} ({n1}, {n2}) "
            f"SELECT DISTINCT {c1}, {c2} FROM {rel_old} "
            f"WHERE NOT EXISTS (SELECT 1 FROM {rel_new} t WHERE t.{n1} = {rel_old}.{c1} AND t.{n2} = {rel_old}.{c2})"
        )
