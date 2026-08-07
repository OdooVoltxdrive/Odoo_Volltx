/** @odoo-module */

import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { patch } from "@web/core/utils/patch";

patch(AccountReportFilters.prototype,{
    async OnSelectCurrency(currency) {
        currency.selected = !currency.selected;
        if (currency.selected){
            this.controller.options.selected_currencies_id = parseInt(currency.id)
            this.controller.options.selected_currencies = parseInt(currency.name)
        }
        await this.controller.reload('currencies', this.controller.options);
    }

});