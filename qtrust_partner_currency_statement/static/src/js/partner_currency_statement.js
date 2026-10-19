/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class QTrustPartnerCurrencyStatement extends Component {
    static template = "qtrust_partner_currency_statement.PartnerCurrencyStatement";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            partnerType: "customer", partnerId: "", partnerSearch: "", partnerOptions: [], partnerDropdownOpen: false, partnerOffset: 0, partnerHasMore: false, partnerLoading: false,
            companyIds: [], companyDropdownOpen: false, currencyId: "", dateFrom: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10),
            dateTo: new Date().toISOString().slice(0, 10), companies: [], currencies: [],
            rows: [], openingBalance: 0, totalDebit: 0, totalCredit: 0, closingBalance: 0,
            partnerName: "", currencyName: "", searchText: "", datePreset: "this_month", datePickerOpen: false, datePeriodType: "month", datePeriodYear: new Date().getFullYear(), datePeriodMonth: new Date().getMonth(), datePeriodQuarter: Math.floor(new Date().getMonth() / 3), loading: false, hasRun: false,
        });
        onWillStart(async () => {
            try {
                this.state.companies = await this.orm.call(
                    "qtrust.partner.currency.statement.wizard", "get_allowed_companies", []
                );
                this.state.currencies = await this.orm.searchRead(
                    "res.currency", [["active", "=", true]], ["name", "symbol"], { order: "name" }
                );
                // Client actions do not guarantee a registered "user" service.
                // Use the action context when available and safely fall back to an accessible company.
                this.state.companyIds = this.state.companies.map((company) => company.id);
                const company = this.state.companies[0];
                this.state.currencyId = String(company?.currency_id?.[0] || this.state.currencies[0]?.id || "");
            } catch (error) {
                console.error("Q-Trust Partner Currency Statement initialization failed:", error);
                this.notification.add(
                    "The statement screen could not load its company/currency filters. Check access rights and the browser console.",
                    { type: "danger" }
                );
            }
        });
    }

    async onPartnerSearch(ev) {
        this.state.partnerSearch = ev.target.value;
        this.state.partnerId = "";
        this.state.partnerName = "";
        this.state.partnerDropdownOpen = true;
        await this.searchPartners(true);
    }

    async searchPartners(reset = false) {
        if (this.state.partnerLoading) {
            return;
        }
        const rank = this.state.partnerType === "customer" ? "customer_rank" : "supplier_rank";
        const term = this.state.partnerSearch.trim();
        const domain = [[rank, ">", 0]];
        if (term) {
            domain.push(["name", "ilike", term]);
        }
        const offset = reset ? 0 : this.state.partnerOffset;
        this.state.partnerLoading = true;
        try {
            const partners = await this.orm.searchRead(
                "res.partner",
                domain,
                ["display_name"],
                { limit: 40, offset, order: "name" }
            );
            this.state.partnerOptions = reset ? partners : [...this.state.partnerOptions, ...partners];
            this.state.partnerOffset = offset + partners.length;
            this.state.partnerHasMore = partners.length === 40;
        } catch (error) {
            this.notification.add(error.message || "Could not load customers/vendors.", { type: "danger" });
        } finally {
            this.state.partnerLoading = false;
        }
    }

    async loadMorePartners() {
        if (this.state.partnerHasMore && !this.state.partnerLoading) {
            await this.searchPartners(false);
        }
    }

    selectPartner(partner) {
        this.state.partnerId = String(partner.id);
        this.state.partnerName = partner.display_name;
        this.state.partnerSearch = partner.display_name;
        this.state.partnerDropdownOpen = false;
    }

    async onPartnerInputFocus() {
        this.state.partnerDropdownOpen = true;
        if (!this.state.partnerOptions.length && !this.state.partnerLoading) {
            await this.searchPartners(true);
        }
    }

    onPartnerTypeChange(ev) {
        this.state.partnerType = ev.target.value;
        this.state.partnerId = "";
        this.state.partnerSearch = "";
        this.state.partnerName = "";
        this.state.partnerOptions = [];
        this.state.partnerDropdownOpen = false;
        this.state.partnerOffset = 0;
        this.state.partnerHasMore = false;
        this.state.hasRun = false;
        this.state.rows = [];
    }

    get datePeriodLabel() {
        if (this.state.datePreset === "custom") return "Custom Dates";
        if (this.state.datePeriodType === "year") return String(this.state.datePeriodYear);
        if (this.state.datePeriodType === "month") {
            return new Date(this.state.datePeriodYear, this.state.datePeriodMonth, 1)
                .toLocaleDateString(undefined, { month: "long", year: "numeric" });
        }
        const firstMonth = this.state.datePeriodQuarter * 3;
        const start = new Date(this.state.datePeriodYear, firstMonth, 1);
        const end = new Date(this.state.datePeriodYear, firstMonth + 2, 1);
        return `${start.toLocaleDateString(undefined, { month: "short" })} - ${end.toLocaleDateString(undefined, { month: "short" })} ${this.state.datePeriodYear}`;
    }

    toggleDatePicker() {
        this.state.datePickerOpen = !this.state.datePickerOpen;
    }

    applyDatePeriod() {
        const year = this.state.datePeriodYear;
        let start, end;
        if (this.state.datePeriodType === "year") {
            start = new Date(year, 0, 1); end = new Date(year, 11, 31);
        } else if (this.state.datePeriodType === "quarter") {
            const month = this.state.datePeriodQuarter * 3;
            start = new Date(year, month, 1); end = new Date(year, month + 3, 0);
        } else {
            start = new Date(year, this.state.datePeriodMonth, 1);
            end = new Date(year, this.state.datePeriodMonth + 1, 0);
        }
        const iso = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
        this.state.dateFrom = iso(start);
        this.state.dateTo = iso(end);
        this.state.datePreset = this.state.datePeriodType === "year" ? "this_year" :
            this.state.datePeriodType === "quarter" ? "this_quarter" : "this_month";
        this.state.datePickerOpen = false;
    }

    changeDatePeriod(direction) {
        if (this.state.datePeriodType === "year") this.state.datePeriodYear += direction;
        else if (this.state.datePeriodType === "month") {
            const d = new Date(this.state.datePeriodYear, this.state.datePeriodMonth + direction, 1);
            this.state.datePeriodYear = d.getFullYear(); this.state.datePeriodMonth = d.getMonth();
        } else {
            const q = this.state.datePeriodQuarter + direction;
            if (q < 0) { this.state.datePeriodYear--; this.state.datePeriodQuarter = 3; }
            else if (q > 3) { this.state.datePeriodYear++; this.state.datePeriodQuarter = 0; }
            else this.state.datePeriodQuarter = q;
        }
        this.applyDatePeriod();
        this.state.datePickerOpen = true;
    }

    selectDatePeriodType(type) {
        this.state.datePeriodType = type;
        this.applyDatePeriod();
        this.state.datePickerOpen = true;
    }

    onDateRangeManualChange() {
        this.state.datePreset = "custom";
        this.state.datePeriodType = "custom";
        this.state.datePickerOpen = false;
    }

    useCustomDates() {
        this.state.datePreset = "custom";
        this.state.datePeriodType = "custom";
        this.state.datePickerOpen = false;
    }

    async toggleCompanyDropdown() {
        try {
            this.state.companies = await this.orm.call(
                "qtrust.partner.currency.statement.wizard", "get_allowed_companies", []
            );
            const activeIds = this.state.companies.map((company) => company.id);
            this.state.companyIds = this.state.companyIds.filter((id) => activeIds.includes(id));
            if (!this.state.companyIds.length) {
                this.state.companyIds = activeIds;
            }
        } catch (error) {
            this.notification.add(error.message || "Could not refresh active companies.", { type: "danger" });
            return;
        }
        this.state.companyDropdownOpen = !this.state.companyDropdownOpen;
    }

    onSelectAllCompanies() {
        this.state.companyIds = this.state.companies.map((company) => company.id);
        this.state.hasRun = false;
        this.state.rows = [];
    }

    onCompanyToggle(companyId, checked) {
        const id = Number(companyId);
        this.state.companyIds = checked
            ? [...new Set([...this.state.companyIds, id])]
            : this.state.companyIds.filter((value) => value !== id);
        this.state.hasRun = false;
        this.state.rows = [];
    }

    get selectedCompanyLabel() {
        const names = this.state.companies.filter((company) => this.state.companyIds.includes(company.id)).map((company) => company.name);
        if (!names.length) return "Select companies";
        if (names.length === this.state.companies.length) return "All active companies";
        return names.length <= 2 ? names.join(", ") : names.length + " companies selected";
    }

    onCurrencyChange(ev) {
        this.state.currencyId = ev.target.value;
    }

    get filteredRows() {
        const query = this.state.searchText.trim().toLowerCase();
        return query ? this.state.rows.filter((row) =>
            [row.entry, row.document, row.label, row.settlement_note].some((v) => String(v || "").toLowerCase().includes(query))
        ) : this.state.rows;
    }

    get positiveOpening() { return Math.max(this.state.openingBalance, 0); }
    get negativeOpening() { return Math.max(-this.state.openingBalance, 0); }

    get currencySymbol() {
        return this.state.currencies.find((c) => String(c.id) === this.state.currencyId)?.symbol || "";
    }

    formatMoney(value) {
        const formatted = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0));
        return this.currencySymbol ? formatted + " " + this.currencySymbol : formatted;
    }

    async loadReport() {
        if (!this.state.partnerId || !this.state.companyIds.length || !this.state.currencyId || !this.state.dateFrom || !this.state.dateTo) {
            this.notification.add("Select a partner, at least one active company, currency and date range first.", { type: "warning" });
            return;
        }
        this.state.datePickerOpen = false;
        this.state.companyDropdownOpen = false;
        this.state.partnerDropdownOpen = false;
        this.state.loading = true;
        try {
            const result = await this.orm.call("qtrust.partner.currency.statement.wizard", "get_interactive_data", [{
                partner_type: this.state.partnerType, partner_id: Number(this.state.partnerId),
                company_ids: this.state.companyIds, currency_id: Number(this.state.currencyId),
                date_from: this.state.dateFrom, date_to: this.state.dateTo,
            }]);
            Object.assign(this.state, {
                rows: result.rows, openingBalance: result.opening_balance, totalDebit: result.total_debit,
                totalCredit: result.total_credit, closingBalance: result.closing_balance,
                partnerName: result.partner_name, currencyName: result.currency_name, hasRun: true,
            });
        } catch (error) {
            this.notification.add(error.message || "Could not load the statement.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get exportUrl() {
        const params = new URLSearchParams({
            partner_type: this.state.partnerType, partner_id: this.state.partnerId,
            company_ids: this.state.companyIds.join(","), currency_id: this.state.currencyId,
            date_from: this.state.dateFrom, date_to: this.state.dateTo,
        });
        return "/qtrust_partner_currency_statement/export_xlsx?" + params.toString();
    }

    exportXlsx() {
        if (!this.state.hasRun) {
            this.notification.add("Load the statement before exporting it.", { type: "warning" });
            return;
        }
        window.location.href = this.exportUrl;
    }

    async printPdf() {
        if (!this.state.partnerId || !this.state.companyIds.length || !this.state.currencyId || !this.state.dateFrom || !this.state.dateTo) {
            this.notification.add("Select a partner, at least one active company, currency and date range first.", { type: "warning" });
            return;
        }
        const ids = await this.orm.create("qtrust.partner.currency.statement.wizard", [{
            partner_type: this.state.partnerType, partner_id: Number(this.state.partnerId),
            company_ids: [[6, 0, this.state.companyIds]], currency_id: Number(this.state.currencyId),
            date_from: this.state.dateFrom, date_to: this.state.dateTo,
        }]);
        const action = await this.orm.call("qtrust.partner.currency.statement.wizard", "action_print_pdf", [ids]);
        await this.action.doAction(action);
    }
}

registry.category("actions").add("qtrust_partner_currency_statement.interactive", QTrustPartnerCurrencyStatement);
