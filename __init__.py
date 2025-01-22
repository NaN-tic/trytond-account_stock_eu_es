# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import (account, account_stock_eu, country, invoice, purchase, sale,
    stock, company)


def register():
    Pool.register(
        country.Country,
        stock.Move,
        stock.ShipmentIn,
        stock.ShipmentOut,
        stock.ShipmentInReturn,
        stock.ShipmentOutReturn,
        stock.ShipmentInternal,
        account_stock_eu.IntrastatUpdateStart,
        account.FiscalYear,
        company.Company,
        module='account_stock_eu_es', type_='model')
    Pool.register(
        account_stock_eu.IntrastatUpdate,
        module='account_stock_eu_es', type_='wizard')
    Pool.register(
        invoice.Configuration,
        invoice.ConfigurationIntrastat,
        invoice.Invoice,
        module='account_stock_eu_es', type_='model',
        depends=['account_invoice_stock'])
    Pool.register(
        purchase.PurchaseLine,
        module='account_stock_eu_es', type_='model', depends=['purchase'])
    Pool.register(
        sale.Sale,
        sale.SaleLine,
        module='account_stock_eu_es', type_='model', depends=['sale'])
