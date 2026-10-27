# Voltx Fleet Shifts: monedas de las liquidaciones

## Alcance del parche 19.0.0.1.0

- `amount_total_usd` conserva la moneda USD del contrato (`currency_id`).
- `amount_total_bs` usa VES (`base.VES`) mediante `bs_currency_id`, independientemente de la moneda de la compañía.
- La lista, el formulario y las liquidaciones del contrato muestran la moneda de cada importe.
- La factura declara expresamente su compañía, moneda y estado `draft`. No se valida ni se registra/concilia un pago automáticamente.
- Se conserva la prioridad existente: si ambos importes son positivos, se factura el importe USD; no se suman ni se convierten entre sí.
- La creación de `account.move` mantiene activos sus cálculos nativos (`skip_invoice_sync=False`). El valor `True` omite sincronizaciones contables de Odoo y podía dejar el borrador con total cero. La escritura del enlace en la liquidación conserva su protección contra recursión.

No se cambian productos, diarios, cuentas, tipos de impuesto ni reglas de cobro de la app. No se suprimen los impuestos configurados en el producto. Se mantiene la generación automática por `create`/`write` y el botón manual; una liquidación ya facturada no genera otra factura.

## Actualización y límites

Desplegar el código y **actualizar el módulo `voltx_fleet_shifts`** en la base de calidad antes de comprobar sus metadatos desde la app. Este cambio no se despliega por guardar los archivos locales.

La actualización no convierte importes ni corrige facturas anteriores. Cualquier documento previo con moneda o total incorrecto debe revisarse con contabilidad, no modificarse masivamente.

El backend conserva `ODOO_LIQUIDATION_TAX_MAPPING_REQUIRED`: separar monedas no acuerda cómo representar base, servicio, IVA e IGTF. Tampoco resuelve pagos que abarcan varias semanas. No quitar estas protecciones ni reintentar todos los eventos pendientes para comprobar el parche.

## Pruebas nativas

Ejecutar solo en una base Odoo/PostgreSQL aislada, con los addons oficiales y este módulo disponibles en `addons_path`:

```bash
odoo server -d voltx_currency_patch_test -i voltx_fleet_shifts \
  --test-tags=/voltx_fleet_shifts --stop-after-init --no-http --max-cron-threads=0
```

Usar `-u voltx_fleet_shifts` en lugar de `-i` si ya está instalado. Añadir los parámetros de conexión de la base de pruebas; no reutilizar una base de desarrollo o calidad con datos conservados.

`tests/test_liquidation_currency.py` comprueba monedas distintas, contextos de moneda contradictorios, compañía USD, cálculos nativos con contexto heredado, importes exactos, borradores sin publicación programada ni pago, alta/escritura/botón manual, ausencia de duplicados, importes cero e impuestos del producto. Solo se sustituye la búsqueda del producto fijo 27 por un producto de prueba; las facturas y sus cálculos usan el ORM contable real de Odoo.
