# PrestaShop integration (sketch)

The portal is a PrestaShop site with custom B2B modules. Medina plugs in as a thin module;
nothing in the existing catalog, cart or order-upload code changes.

## What the module does

1. Registers the `displayBeforeBodyClosingTag` hook.
2. For a logged-in customer, looks up the ERP customer number the portal already keeps for the account,
   and the current delivery address (delivery point).
3. Signs `{customer, delivery point, expiry}` with an HMAC secret shared with the Medina backend.
4. Renders one script tag: `<script src=".../medina.js" data-api="..." data-token="..." data-lang="ru|kk">`.

The widget lives in a Shadow DOM, so portal CSS (Bootstrap/jQuery themes) and widget CSS do not interfere.

## Backend side (production)

- Verify the token and take the customer id from it. The demo's `customer_id` form field is for the
  synthetic demo only.
- Data access adapter: implement `data_access.base.DataSource` over the data the portal already receives
  from the ERP batch export (product cards, batches with expiry and stock per branch, customer prices,
  customers with delivery points, credit and overdue debt, order history). Either read the portal
  database tables that the import fills, or the intermediate export tables directly. Read-only.
- The generated `.xls` uses exactly the portal's order-upload format (`Штрихкод | Код товара | Количество`,
  text cells), so the existing upload flow and its business rules stay the single path to place an order.

## Files

- `medina/medina.php` — module class (install, hook, token signing).
- `medina/views/templates/hook/widget.tpl` — the script tag.
