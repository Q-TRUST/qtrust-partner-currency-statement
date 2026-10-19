from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class QTrustPartnerCurrencyStatementWizard(models.TransientModel):
    _name = "qtrust.partner.currency.statement.wizard"
    _description = "Q-Trust Partner Currency Statement"

    partner_type = fields.Selection(
        [("customer", "Customer"), ("supplier", "Vendor")],
        required=True, default="customer", string="Partner Type"
    )
    partner_id = fields.Many2one("res.partner", required=True, string="Customer / Vendor")
    company_ids = fields.Many2many(
        "res.company", string="Companies", required=True,
        default=lambda self: self.env.companies,
    )
    currency_id = fields.Many2one(
        "res.currency", required=True, string="Statement Currency",
        default=lambda self: self.env.company.currency_id
    )
    date_from = fields.Date(required=True, string="Start Date",
                            default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(required=True, string="End Date", default=fields.Date.context_today)

    def _validate_filters(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_("The start date must be on or before the end date."))
        partner = self.partner_id.commercial_partner_id
        if self.partner_type == "customer" and partner.customer_rank <= 0:
            raise ValidationError(_("The selected partner is not configured as a customer."))
        if self.partner_type == "supplier" and partner.supplier_rank <= 0:
            raise ValidationError(_("The selected partner is not configured as a vendor."))

    def _get_statement_data(self):
        self.ensure_one()
        self._validate_filters()
        partner = self.partner_id.commercial_partner_id
        account_type = "asset_receivable" if self.partner_type == "customer" else "liability_payable"
        domain = [
            ("company_id", "in", self.company_ids.ids),
            ("partner_id", "child_of", partner.id),
            ("account_id.account_type", "=", account_type),
            ("parent_state", "=", "posted"),
            ("date", "<=", self.date_to),
        ]
        # Explicitly use every company selected in the statement. The active company's
        # default context can otherwise make multi-company reporting appear limited
        # to the primary company in some Odoo contexts.
        lines = self.env["account.move.line"].with_context(
            allowed_company_ids=self.company_ids.ids
        ).search(domain, order="date, move_id, id")
        currency = self.currency_id
        opening = 0.0
        period_rows = []
        total_debit = 0.0
        total_credit = 0.0

        for line in lines:
            amount = 0.0
            settlement_note = ""
            if line.currency_id == currency:
                amount = line.amount_currency
            else:
                amount, settlement_note = self._cross_currency_amount(line, currency)
            if not amount:
                continue
            if line.date < self.date_from:
                opening += amount
                continue
            debit, credit = max(amount, 0.0), max(-amount, 0.0)
            total_debit += debit
            total_credit += credit
            period_rows.append({
                "date": line.date,
                "entry": line.move_id.name or line.move_id.ref or "",
                "document": line.move_id.ref or "",
                "label": line.name or "",
                "debit": debit,
                "credit": credit,
                "amount": amount,
                "settlement_note": settlement_note,
            })

        balance = opening
        for row in period_rows:
            balance += row["amount"]
            row["balance"] = balance

        return {
            "wizard": self, "partner": partner, "companies": self.company_ids, "company": self.env.company,
            "currency": currency, "date_from": self.date_from, "date_to": self.date_to,
            "opening_balance": opening, "total_debit": total_debit,
            "total_credit": total_credit, "closing_balance": balance, "rows": period_rows,
        }

    def _cross_currency_amount(self, line, currency):
        """Represent cross-currency settlements in the selected currency only
        when reconciliation links the line to a receivable/payable line in that currency.
        """
        partials = line.matched_debit_ids | line.matched_credit_ids
        amount = 0.0
        references = []
        for partial in partials:
            other = partial.debit_move_id if partial.credit_move_id == line else partial.credit_move_id
            if other.currency_id != currency:
                continue
            # Partial reconciliation stores amounts in both sides' currencies.
            if partial.debit_move_id == other:
                matched_amount = partial.debit_amount_currency
            else:
                matched_amount = partial.credit_amount_currency
            amount += abs(matched_amount)
            references.append(other.move_id.name or other.move_id.ref or "")
        if not amount:
            return 0.0, ""
        # Receivable/payable balances are signed by debit/credit. A settlement
        # on the opposite side reduces the invoice balance.
        sign = -1.0 if line.credit > line.debit else 1.0
        return sign * amount, _("Settlement against: %s") % ", ".join(filter(None, references))

    @api.model
    def get_allowed_companies(self):
        """Return only companies enabled in the current Odoo company switcher."""
        return self.env.companies.read(["name", "currency_id"])

    @api.model
    def get_interactive_data(self, filters):
        required = ("partner_type", "partner_id", "company_ids", "currency_id", "date_from", "date_to")
        if not isinstance(filters, dict) or any(not filters.get(key) for key in required):
            raise ValidationError(_("Partner, company, currency and date range are required."))
        raw_company_ids = filters["company_ids"]
        if isinstance(raw_company_ids, str):
            raw_company_ids = [value for value in raw_company_ids.split(",") if value]
        try:
            company_ids = list(dict.fromkeys(int(value) for value in raw_company_ids))
        except (TypeError, ValueError):
            raise ValidationError(_("Invalid company selection."))
        allowed_company_ids = set(self.env.companies.ids)
        if not company_ids or not set(company_ids).issubset(allowed_company_ids):
            raise ValidationError(_("You can only report on companies currently enabled in the Odoo company switcher."))
        wizard = self.create({
            "partner_type": filters["partner_type"],
            "partner_id": int(filters["partner_id"]),
            "company_ids": [(6, 0, company_ids)],
            "currency_id": int(filters["currency_id"]),
            "date_from": filters["date_from"],
            "date_to": filters["date_to"],
        })
        data = wizard._get_statement_data()
        rows = []
        for row in data["rows"]:
            values = dict(row)
            values["date"] = row["date"].isoformat()
            rows.append(values)
        return {
            "partner_name": data["partner"].display_name,
            "currency_name": data["currency"].name,
            "opening_balance": data["opening_balance"],
            "total_debit": data["total_debit"],
            "total_credit": data["total_credit"],
            "closing_balance": data["closing_balance"],
            "rows": rows,
        }

    def action_print_pdf(self):
        self.ensure_one()
        self._validate_filters()
        return self.env.ref(
            "qtrust_partner_currency_statement.action_report_partner_currency_statement"
        ).report_action(self)


class QTrustPartnerCurrencyStatementReport(models.AbstractModel):
    _name = "report.qtrust_partner_currency_statement.statement_report"
    _description = "Q-Trust Partner Currency Statement PDF"

    def _get_report_values(self, docids, data=None):
        wizard = self.env["qtrust.partner.currency.statement.wizard"].browse(docids).exists()
        if not wizard:
            raise ValidationError(_("The statement wizard no longer exists."))
        report_data = wizard._get_statement_data()
        currency = report_data["currency"]

        # Prepare display strings in Python. QWeb report templates do not expose
        # formatLang as a global in this Odoo version.
        def format_currency_amount(amount):
            rounded = currency.round(amount)
            number = format(rounded, f",.{currency.decimal_places}f")
            symbol = currency.symbol or currency.name
            return f"{number} {symbol}"

        report_data["opening_debit_display"] = format_currency_amount(
            max(report_data["opening_balance"], 0.0)
        )
        report_data["opening_credit_display"] = format_currency_amount(
            max(-report_data["opening_balance"], 0.0)
        )
        report_data["opening_balance_display"] = format_currency_amount(
            report_data["opening_balance"]
        )
        report_data["total_debit_display"] = format_currency_amount(report_data["total_debit"])
        report_data["total_credit_display"] = format_currency_amount(report_data["total_credit"])
        report_data["closing_balance_display"] = format_currency_amount(report_data["closing_balance"])
        for row in report_data["rows"]:
            row["debit_display"] = format_currency_amount(row["debit"])
            row["credit_display"] = format_currency_amount(row["credit"])
            row["balance_display"] = format_currency_amount(row["balance"])

        return {"doc_ids": wizard.ids, "doc_model": wizard._name, "docs": wizard,
                **report_data}
