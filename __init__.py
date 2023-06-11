# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import account_stock_eu, country, invoice, purchase, sale, stock


def register():
    Pool.register(
        stock.Move,
        stock.ShipmentIn,
        stock.ShipmentOut,
        stock.ShipmentInReturn,
        stock.ShipmentOutReturn,
        stock.ShipmentInternal,
        purchase.PurchaseLine,
        sale.SaleLine,
        account_stock_eu.IntrastatUpdateStart,
        module='account_stock_eu_es', type_='model')
    Pool.register(
        invoice.Configuration,
        invoice.ConfigurationIntrastat,
        invoice.Invoice,
        module='account_stock_eu_es', type_='model',
        depends=['account_invoice_stock'])
    Pool.register(
        account_stock_eu.IntrastatUpdate,
        module='account_stock_eu_es', type_='wizard')
