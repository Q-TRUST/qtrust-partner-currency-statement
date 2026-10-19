# Q-Trust Partner Currency Statement — Odoo 19

Standalone interactive customer/vendor statement in one selected currency.

- Integrated under **Accounting → Reporting → Foreign Currency Statement**.
- Interactive OWL/JavaScript screen with partner, company, currency, and date filters.
- Search within the displayed transaction rows.
- Summary cards for opening balance, period debit/credit, and closing balance.
- Export to XLSX and print to PDF.
- Does not override standard accounting reports or modify accounting entries.
- Opening balance includes selected-currency movements before the start date.
- Cross-currency settlement display is a first-pass implementation and must be checked against actual reconciliations in staging.

## Staging validation required

This update has not been installed or tested on the target Odoo.sh database. After pushing to `test`, wait for a successful build, upgrade the module, and validate:
- Backend assets load without JavaScript/XML errors.
- Partner/company permissions and multi-company restrictions.
- XLSX download opens correctly in Excel.
- PDF rendering.
- Partial/full reconciliation, credit notes, exchange differences, and payments in another currency.
