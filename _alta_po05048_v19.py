#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alta de PO05048 en v19, espejo de la de v16.

La PO se crea con las 17 lineas, el proveedor Feronia y el mismo importe.
Se confirma para dejarla en el mismo estado que v16 (state='purchase'), pero
la recepcion NO se valida: el stock es el hilo que se esta rehaciendo (B.19).

Dedupe por clave funcional (numero, partner) antes del create (B.7).

  python3 _alta_po05048_v19.py            # dry-run
  python3 _alta_po05048_v19.py --apply
"""
import sys
sys.path.insert(0, '/home/horacio/proyectos/2026/darakjian')
from _conn19 import o16, d19

APPLY = "--apply" in sys.argv
PO16_ID = 5041
PO_NAME = "PO05048"

c16, c19 = o16(), d19()

head = c16('purchase.order', 'read', [PO16_ID],
           ['name', 'partner_id', 'partner_ref', 'date_order', 'date_planned',
            'state', 'amount_total', 'currency_id'])[0]
lines = c16('purchase.order.line', 'search_read', [['order_id', '=', PO16_ID]],
            ['product_id', 'name', 'product_qty', 'price_unit', 'date_planned'])
codes = {l['product_id'][0]: None for l in lines}
for p in c16('product.product', 'read', list(codes), ['default_code']):
    codes[p['id']] = p['default_code']

# proveedor y productos en destino, por clave funcional
partner = c19('res.partner', 'search', [['name', '=', head['partner_id'][1]]], limit=1)
if not partner:
    sys.exit(f"proveedor {head['partner_id'][1]} no esta en v19")
dest = {p['default_code']: p['id'] for p in
        c19('product.product', 'search_read',
            [['default_code', 'in', list(codes.values())]], ['default_code'])}
falta = [c for c in codes.values() if c not in dest]
if falta:
    sys.exit(f"faltan {len(falta)} SKUs en v19: {falta}")

dup = c19('purchase.order', 'search',
          [['name', '=', PO_NAME], ['partner_id', '=', partner[0]]])
print(f"{PO_NAME} | {head['partner_id'][1]} | v16 state={head['state']} "
      f"| total {head['amount_total']:,.2f} | {len(lines)} lineas")
print(f"proveedor v19 id={partner[0]} | SKUs resueltos {len(dest)}/{len(codes)} | duplicado: {dup}")
if dup:
    sys.exit("ya existe en v19, no se crea nada")

vals = {
    'name': PO_NAME,
    'partner_id': partner[0],
    'partner_ref': head['partner_ref'] or False,
    'date_order': head['date_order'],
    'date_planned': head['date_planned'],
    'order_line': [(0, 0, {
        'product_id': dest[codes[l['product_id'][0]]],
        'name': l['name'],
        'product_qty': l['product_qty'],
        'price_unit': l['price_unit'],
        'date_planned': l['date_planned'],
        'tax_ids': [(6, 0, [])],
    }) for l in lines],
}
if not APPLY:
    print("\nDRY-RUN. Con --apply se crea y se confirma.")
    sys.exit()

oid = c19('purchase.order', 'create', vals)
print(f"creada v19 id={oid}")
c19('purchase.order', 'button_confirm', [oid])
r = c19('purchase.order', 'read', [oid],
        ['name', 'state', 'amount_total', 'picking_ids'])[0]
print("verificacion:", r)
if r['picking_ids']:
    print("recepcion:", c19('stock.picking', 'read', r['picking_ids'],
                            ['name', 'state', 'location_dest_id']))
