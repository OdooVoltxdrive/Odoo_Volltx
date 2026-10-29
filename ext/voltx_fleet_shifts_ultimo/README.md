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

## Compatibilidad con contratos heredados: 19.0.0.2.0

La actualización anterior encontró contratos existentes sin `purchaser_id`, sin asignación de conductor ni historial que permita recuperarlo. El `NOT NULL` global impedía validar el esquema. No se rellena ese dato con el administrador, un contacto ficticio o el conductor actual de otro contrato.

- La columna admite los nulos heredados; no se borran contratos ni se cambian sus estados, importes o asignaciones.
- Las altas de contratos siguen exigiendo conductor mediante validación ORM, incluidos los lotes. No se permite quitar un conductor ya asignado ni eliminar el contacto referenciado (`ondelete='restrict'`).
- El formulario mantiene el conductor obligatorio. Se elimina el `related` heredado de `vehicle_id.driver_id` para que se ejecuten el cálculo y la inversa propios ya definidos por el módulo: el titular del contrato no sustituye al conductor actual del vehículo ni se pierde al cambiar el turno. Los contratos heredados pueden conservarse y recibir una asignación real cuando esté confirmada.
- Se conserva la protección existente: una liquidación sin conductor no genera factura.
- Actualizar `voltx_fleet_shifts` para aplicar la compatibilidad de esquema. Los contratos heredados sin conductor siguen pendientes de revisión manual; este parche no afirma haber reconstruido esa información.

`tests/test_contract_purchaser.py` cubre el esquema compatible, contratos heredados, altas válidas/inválidas, lotes atómicos, valores por contexto/vehículo, borrado del contacto, independencia entre titular y conductor actual del vehículo, conservación del titular al sincronizar turnos, bloqueo de facturación sin conductor y ausencia de duplicados al asignar conductores.

## Limpieza de avisos: 19.0.0.3.0

Se eliminan `tracking=True` de los dos importes de liquidación: el modelo no hereda `mail.thread`, por lo que Odoo no admitía ese parámetro. No se añade chatter ni se cambian cálculos, impuestos o generación de facturas.

Se revirtieron íntegramente los cambios de metadatos que se habían aplicado a `Localizacion_contable/iva_retention` e `isrl_retention`. Los ocho archivos vuelven al contenido previo al commit `4eb2a1c`. Los módulos de Darrell Sojo no forman parte del alcance autorizado: no deben modificarse para limpiar sus avisos. Esos warnings pueden reaparecer y no se deben silenciar ni corregir desde este trabajo.

Desde la raíz del repositorio, `python3 -m unittest discover -s tests -p test_warning_metadata.py -v` comprueba únicamente la declaración de los importes del addon propio. Se retiraron las cuatro comprobaciones nuevas que exigían cambios en los módulos de terceros. Las pruebas ORM del addon propio no cambian; sus resultados anteriores no sustituyen una prueba con todos los módulos Enterprise de calidad.

La deprecación de XML-RPC en Odoo 19 (retirada prevista para Odoo 22), los adjuntos ausentes del filestore y los permisos de catálogo PostgreSQL de Odoo.sh son asuntos separados. No se ocultan avisos ni se amplían permisos para eliminarlos.

## Mapeo fiscal VES: 19.0.0.4.0

El campo opcional `fiscal_breakdown` recibe el desglose guardado del pago: `{"version":1,"currency":"VES","base":"3900.00","service":"487.50","vat":"702.00","total":"5089.50"}`. Los importes son decimales de hasta dos posiciones. Solo admite VES, sin importe USD simultáneo, base positiva, servicio no negativo e IVA exacto del 16 % sobre base + servicio. El total debe coincidir con `amount_total_bs`. Se conserva el comportamiento histórico de las liquidaciones sin este campo; no se migran documentos anteriores.

**Configuración pendiente de contabilidad:** en Ajustes → Compañías → compañía → «Facturación VoltX», seleccionar la variante de producto de servicio en `voltx_service_product_id`, con cuenta de ingresos de producto/categoría confirmada. Queda vacío por defecto; no se infiere del nombre de un producto ni se modifica calidad automáticamente. El arrendamiento sigue usando la plantilla 27. Ambos productos deben tener solo IVA de venta 16 % no incluido, de la compañía correcta.

Sin configuración válida, `create` devuelve `ODOO_LIQUIDATION_SERVICE_MAPPING_REQUIRED` o `ODOO_LIQUIDATION_TAX_MAPPING_REQUIRED` y la transacción RPC no conserva la liquidación ni la factura. Con configuración válida, Odoo genera líneas de arrendamiento y servicio netas, aplica sus impuestos nativos y verifica base, impuesto y total. Una discrepancia de redondeo tampoco se corrige inventando ajustes: se rechaza. La factura queda `draft`, `auto_post=no`, sin pago ni conciliación. Los datos financieros de una liquidación fiscal facturada no pueden cambiarse ni desvincular su factura.

Desplegar y actualizar el addon antes del backend que envía el protocolo fiscal. El backend detecta addons antiguos y conserva el bloqueo. USD/IGTF, pagos multisemana y el reparto de impuestos en reembolsos de facturas multilínea siguen pendientes. No habilitar colas generales ni reutilizar pagos QA ya consumidos.

La suite nativa incluye 10 regresiones fiscales además de las 26 anteriores. `scripts/seed_fiscal_local.py`, ejecutado por `odoo shell` exclusivamente en una base desechable llamada `voltx_fiscal_test` y con `FISCAL_QA_PASSWORD` local, prepara la comprobación visual/RPC. Incluye asserts de importes, borrador y rechazo sin configuración. Reproduce la plantilla 27 solo en esa base vacía, preservando el avance previo de su secuencia; nunca usar ese script en calidad. Escribe `/tmp/fiscal-ui-fixture.json`, que debe copiarse al host para las pruebas Chromium del frontend.

## Reversión USD/IGTF y alícuotas: 19.0.0.7.0

Por solicitud expresa del usuario se revierten los cambios del addon de `1cb9c50` (USD v2/IGTF nativo) y `0608571` (compatibilidad de alícuotas/totales y guardas de publicación/envío). Los modelos, vistas e imports quedan como en `d0e2cc5` / funcionalidad 19.0.0.4.0; el número 19.0.0.7.0 solo permite desplegar la reversión mediante actualización del módulo. No se modifica la localización de terceros, el backend ni su cálculo de cobro.

Se retiran junto con la funcionalidad sus casos de prueba nuevos de USD v2/localización, restaurando **exactamente** las pruebas existentes antes de T-7, sin rebajar ninguna expectativa VES/legacy. El historial y la evidencia roja quedan conservados. No se presenta esta retirada como arreglo ni como aprobación de la suite Enterprise.

La reversión no borra facturas, liquidaciones, impuestos QA ni snapshots financieros ya guardados. Las asignaciones temporales de compañía estaban vacías antes del despliegue. Los documentos antiguos con dos impuestos pueden volver a mostrar el error heredado de singleton; no se reescriben para ocultarlo. El backend conserva la negociación de capacidad y debe bloquear nuevos envíos USD v2 al addon revertido. El recorrido nuevo se detiene en el primer fallo real, sin forzar la factura ni corregir el error todavía.

**Comprobación real tras desplegar la reversión:** `28656eb` instalado como 19.0.0.7.0; `fields_get` ya no declara capacidad v2 ni impuestos de compañía añadidos. Fixture nueva **RZC37**, contacto/vehículo/contrato **79/44/87**, pago local `369ef66f-e712-4161-88bb-e738cad3de61`: candidato y altas por HTTP, login y pago de una cuota por navegador TesterArmy con Stripe falso, base 92,50 y cobro 110,52 USD. El primer intento de publicación falla en el backend intacto con `ODOO_LIQUIDATION_TAX_MAPPING_REQUIRED: upgrade the liquidation addon before sending fiscal data`. **Cero liquidaciones/facturas nuevas** y ninguna escritura de impuestos/compañía. El flujo global termina bloqueado (exit 1), no aprobado; no se llega a comprobar el IGTF heredado y no se corrige todavía. Los impuestos/documentos históricos quedan conservados, sin reintento ni limpieza.

## Histórico retirado — USD con IVA e IGTF: 19.0.0.5.0

`fiscal_breakdown` v2 usa `{version:2,currency:'USD',base,vat,igtf,total}`, con los cuatro importes como texto de dos decimales. IVA 16 % sobre base e IGTF SENIAT 3 % sobre base + IVA, redondeo decimal de cada impuesto; total igual a `amount_total_usd`, sin Bs simultáneos. La capacidad readonly `fiscal_breakdown_version`, consultable por `default_get`, vale 2. VES v1 y liquidaciones heredadas sin desglose se conservan.

La compañía configura **impuestos separados**, sin alterar IVA ni producto compartidos: `voltx_usd_vat_tax_id` (IVA 16 % no incluido, primero, amplía la base siguiente) y `voltx_igtf_tax_id` (IGTF 3 % no incluido, afectado por la base anterior, sin ampliarla, con cuenta de pasivo propia distinta del IVA). El ORM verifica individualmente los impuestos, base y total de la factura nativa antes de enlazarla. Las liquidaciones fiscales facturadas no admiten cambios financieros.

**Verificación funcional real, 2026-10-28:** el usuario autorizó subir `1cb9c50` a `calidad`; se confirmó instalada 19.0.0.5.0 y se creó una fixture nueva desde candidato/conductor/vehículo/contrato hasta pago USD por navegador con pasarela falsa. Liquidación **4**, factura **482**: base **92,50**, IVA **14,80**, IGTF **3,22**, total **110,52 USD**, `draft/not_paid`, `auto_post=no`. Reentregar la publicación no duplica. Solo se usaron impuestos QA 18/19, cuenta IGTF **453 / 2175021**, **a revisar por un contador**, no aprobada para producción. Compañía restaurada `(false,false) → (18,19) → (false,false)`; IVA 10 y producto 26 intactos. No se publica, paga ni concilia el borrador.

**Límite:** la suite ORM completa de `tests/test_liquidation_fiscal.py` no se ejecutó: Community local no carga la cadena Unidigital/Enterprise y no se obtuvieron logs de tests Odoo.sh. La verificación real acredita el recorrido feliz e idempotente, no todos los rechazos/rollback de esa suite ni bancos reales. Producción necesita configuración aprobada por contabilidad. Las notas de crédito con IGTF o varias líneas permanecen bloqueadas en el backend.

## Pruebas nativas

Ejecutar solo en una base Odoo/PostgreSQL aislada, con los addons oficiales y este módulo disponibles en `addons_path`:

```bash
odoo server -d voltx_currency_patch_test -i voltx_fleet_shifts \
  --test-tags=/voltx_fleet_shifts --stop-after-init --no-http --max-cron-threads=0
```

Usar `-u voltx_fleet_shifts` en lugar de `-i` si ya está instalado. Añadir los parámetros de conexión de la base de pruebas; no reutilizar una base de desarrollo o calidad con datos conservados.

`tests/test_liquidation_currency.py` comprueba monedas distintas, contextos de moneda contradictorios, compañía USD, cálculos nativos con contexto heredado, importes exactos, borradores sin publicación programada ni pago, alta/escritura/botón manual, ausencia de duplicados, importes cero e impuestos del producto. Solo se sustituye la búsqueda del producto fijo 27 por un producto de prueba; las facturas y sus cálculos usan el ORM contable real de Odoo.
