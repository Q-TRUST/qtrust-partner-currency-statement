from io import BytesIO

import xlsxwriter

from odoo import http
from odoo.http import content_disposition, request


class QTrustPartnerCurrencyStatementController(http.Controller):

    @http.route(
        "/qtrust_partner_currency_statement/export_xlsx",
        type="http", auth="user", methods=["GET"], csrf=False,
    )
    def export_xlsx(self, partner_type=None, partner_id=None, company_ids=None,
                    currency_id=None, date_from=None, date_to=None, **kwargs):
        try:
            values = {
                "partner_type": partner_type,
                "partner_id": int(partner_id),
                "company_ids": [int(value) for value in company_ids.split(",") if value],
                "currency_id": int(currency_id),
                "date_from": date_from,
                "date_to": date_to,
            }
        except (AttributeError, TypeError, ValueError):
            return request.not_found()
        if not values["company_ids"] or any(company_id not in request.env.companies.ids for company_id in values["company_ids"]):
            return request.not_found()

        values["company_ids"] = [(6, 0, values["company_ids"])]
        wizard = request.env["qtrust.partner.currency.statement.wizard"].create(values)
        data = wizard._get_statement_data()
        stream = BytesIO()
        workbook = xlsxwriter.Workbook(stream, {"in_memory": True})
        sheet = workbook.add_worksheet("Statement")
        title_fmt = workbook.add_format({"bold": True, "font_size": 14})
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        money_fmt = workbook.add_format({"num_format": "#,##0.00;[Red](#,##0.00)"})
        text_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})

        sheet.merge_range(0, 0, 0, 6, "Foreign Currency Statement", title_fmt)
        sheet.write(1, 0, "Partner")
        sheet.write(1, 1, data["partner"].display_name)
        sheet.write(2, 0, "Company")
        sheet.write(2, 1, ", ".join(data["companies"].mapped("display_name")))
        sheet.write(3, 0, "Currency")
        sheet.write(3, 1, data["currency"].name)
        sheet.write(4, 0, "Period")
        sheet.write(4, 1, "%s - %s" % (data["date_from"], data["date_to"]))

        headers = ["Date", "Entry", "Document", "Description", "Debit", "Credit", "Balance"]
        for col, header in enumerate(headers):
            sheet.write(6, col, header, header_fmt)
        row_idx = 7
        sheet.write(row_idx, 0, "Opening Balance")
        sheet.write_number(row_idx, 6, data["opening_balance"], money_fmt)
        row_idx += 1
        for line in data["rows"]:
            sheet.write(row_idx, 0, str(line["date"]))
            sheet.write(row_idx, 1, line["entry"], text_fmt)
            sheet.write(row_idx, 2, line["document"], text_fmt)
            description = line["label"]
            if line["settlement_note"]:
                description += "\n" + line["settlement_note"]
            sheet.write(row_idx, 3, description, text_fmt)
            sheet.write_number(row_idx, 4, line["debit"], money_fmt)
            sheet.write_number(row_idx, 5, line["credit"], money_fmt)
            sheet.write_number(row_idx, 6, line["balance"], money_fmt)
            row_idx += 1
        sheet.write(row_idx, 3, "Period Totals", header_fmt)
        sheet.write_number(row_idx, 4, data["total_debit"], money_fmt)
        sheet.write_number(row_idx, 5, data["total_credit"], money_fmt)
        sheet.write_number(row_idx, 6, data["closing_balance"], money_fmt)
        sheet.set_column("A:A", 13)
        sheet.set_column("B:C", 20)
        sheet.set_column("D:D", 42)
        sheet.set_column("E:G", 16)
        sheet.freeze_panes(7, 0)
        sheet.autofilter(6, 0, max(row_idx - 1, 6), 6)
        workbook.close()
        stream.seek(0)
        filename = "partner_currency_statement_%s.xlsx" % data["partner"].name.replace("/", "-")
        return request.make_response(
            stream.read(),
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition(filename)),
            ],
        )
