# yaguven_darakjian_etiquetas

Odoo 19 module — **jewelry tag printing on Zebra printers**, straight from the browser.

## What it does

Adds a **Print Tag** button to the product form. The button builds the ZPL for the piece
and posts it to the local print bridge, which forwards it to the Zebra over the store
network.

The tag is built from the product's own attributes, not from free text, so a tag never
drifts from what the catalog says.

## Why a local bridge and not a direct call

Odoo runs on **https**; the Zebra speaks **raw socket over http**. The browser blocks any
direct request as mixed content. The single exception browsers make is
`http://127.0.0.1`, so a small process has to run **on the machine that has the browser
open**. That process is `zebra_bridge/zebra_bridge.py`, shared with the POS receipt
printer — see its own README.

## How the tag is composed

* **Stone family priority** (`STONE_FAMILIES`): a piece can carry several stone families
  (Center Diamond, Side Diamond, Accent Stone…). The first family in the list with a
  *Carat Weight* filled in is the one printed — the highest one wins, not all of them.
  Added on 2026-07-29 after finding 10 pieces in the catalog that carry **only** the
  lower families and were coming out with no stone at all on the tag.
* **Attribute name overrides** (`CARAT_ATTR_OVERRIDE`, `QUANTITY_ATTR_OVERRIDE`): most
  families follow the pattern `<family> Carat Weight` / `<family> Quantity`. Marquis and
  Round Diamond do not, and their exceptions are declared rather than guessed.
* **The wordmark** (`logo_zpl.LOGO_ZPL`) was pulled from the layout at the store's request
  on 2026-07-29 to free up room. The code is kept in place in case it goes back in.

## What it depends on

Stock Odoo only: `product` and `stock`. No OCA, no third-party modules — see
`../GLOSSARY.md` for the reasoning.

## Checking it works

1. Open any product with attributes and press **Print Tag**.
2. If nothing comes out, open `http://127.0.0.1:9199/status` on that same machine: it
   says whether the bridge is running and whether the Zebra is on the network.
3. The bridge writes every print to `/Users/Shared/zebra_bridge.log`, one line per job,
   with the SKU it printed.

Yagüven C.G.
