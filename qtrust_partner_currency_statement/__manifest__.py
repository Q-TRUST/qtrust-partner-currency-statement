{
    "name": "Q-Trust Partner Currency Statement",
    "summary": "Customer and vendor statement in one selected currency",
    "version": "19.0.1.3.13",
    "category": "Accounting/Accounting",
    "author": "Q-Trust",
    "license": "LGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "report/statement_report.xml",
        "views/statement_wizard_views.xml",
    ],
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "qtrust_partner_currency_statement/static/src/js/partner_currency_statement.js",
            "qtrust_partner_currency_statement/static/src/xml/partner_currency_statement.xml",
        ],
    },
    "images": [
        "static/description/icon.png",
    ],
    "application": True,
}