import datetime as dt
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import (create_chart, create_fiscalyear,
                                                 create_tax, get_accounts)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules
from trytond.modules.account_invoice.tests.tools import set_fiscalyear_invoice_sequences


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Imports
        today = dt.date.today()

        # Activate modules
        activate_modules(['account_stock_eu_es', 'sale'])
        Country = Model.get('country.country')
        Incoterm = Model.get('incoterm.incoterm')
        Organization = Model.get('country.organization')
        Party = Model.get('party.party')
        Period = Model.get('account.period')
        ProductTemplate = Model.get('product.template')
        ProductUom = Model.get('product.uom')
        TariffCode = Model.get('customs.tariff.code')
        StockLocation = Model.get('stock.location')

        # Create countries
        europe, = Organization.find([('code', '=', 'EU')])
        belgium = Country(name="Belgium", code='BE')
        belgium.subdivisions.new(name="Flemish Region",
                                               intrastat_code='1',
                                               type='region')
        belgium.subdivisions.new(name="Walloon Region",
                                               intrastat_code='2',
                                               type='region')
        belgium.save()
        flemish, walloon = belgium.subdivisions
        belgium.subdivisions.new(name="Liège",
                                               type='province',
                                               parent=walloon)
        belgium.save()
        liege, = [s for s in belgium.subdivisions if s.parent == walloon]
        france = Country(name="France", code='FR')
        france.save()
        china = Country(name="China", code='CN')
        china.save()
        europe.members.new(country=belgium)
        europe.members.new(country=france)
        europe.save()

        # Create currency
        eur = get_currency('EUR')

        # Create company in Belgium
        _ = create_company(currency=eur)
        company = get_company()
        self.assertEqual(company.intrastat, True)
        company_address, = company.party.addresses
        company_address.country = belgium
        company_address.subdivision = liege
        company.incoterms.extend(Incoterm.find([
             ('code', 'in', ['FCA', 'CIP', 'CFR', 'CIF']),
             ('version', '=', '2020')
             ]))
        company_address.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create taxes
        Tax = Model.get('account.tax')
        tax_intrastat = create_tax(Decimal('.04'))
        tax_intrastat.save()
        tax10 = create_tax(Decimal('.10'))
        tax10.save()
        tax21 = create_tax(Decimal('.21'))
        tax21.save()

        # Configure taxes as to be intrastat exempt
        StockConfig = Model.get('stock.configuration')
        stock_config = StockConfig(1)
        stock_config.intrastat_exempt_taxes.extend([tax10, tax21])
        stock_config.save()

        # Get stock locations
        warehouse_loc, = StockLocation.find([('code', '=', 'WH')])
        warehouse_loc.address = company_address
        warehouse_loc.save()

        # Create customer
        customer_fr = Party(name="Customer FR")
        identifier = customer_fr.identifiers.new(type='eu_vat')
        identifier.code = "FR40303265045"
        address_fr, = customer_fr.addresses
        address_fr.country = france
        sale_incoterm = customer_fr.sale_incoterms.new()
        sale_incoterm.type = 'sale'
        sale_incoterm.incoterm, = Incoterm.find([
                ('code', '=', 'DAP'), ('version', '=', '2020')])
        sale_incoterm.incoterm_location = warehouse_loc
        customer_fr.save()
        address_fr.save()

        # Create account categories
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(Tax(tax21.id))
        account_category.save()

        category_intrastat = ProductCategory(name="Account Category Intrastat")
        category_intrastat.accounting = True
        category_intrastat.account_expense = expense
        category_intrastat.account_revenue = revenue
        category_intrastat.customer_taxes.append(Tax(tax_intrastat.id))
        category_intrastat.save()

        # Create products
        unit, = ProductUom.find([('name', '=', "Unit")])
        kg, = ProductUom.find([('name', '=', "Kilogram")])
        tariff_code = TariffCode(code="9403 10 51")
        tariff_code.description = "Desks"
        tariff_code.intrastat_uom = unit
        tariff_code.save()
        template = ProductTemplate(name="Desk")
        template.default_uom = unit
        template.type = 'goods'
        template.account_category = account_category
        template.salable = True
        template.cost_price = Decimal('100.0000')
        _ = template.tariff_codes.new(tariff_code=tariff_code)
        template.weight = 3
        template.weight_uom = kg
        template.country_of_origin = china
        template.save()
        product, = template.products

        intrastat_template = ProductTemplate(name="Lamp")
        intrastat_template.default_uom = unit
        intrastat_template.type = 'goods'
        intrastat_template.account_category = category_intrastat
        intrastat_template.salable = True
        intrastat_template.cost_price = Decimal('100.0000')
        _ = intrastat_template.tariff_codes.new(tariff_code=tariff_code)
        intrastat_template.weight = 1
        intrastat_template.weight_uom = kg
        intrastat_template.country_of_origin = china
        intrastat_template.save()
        product_intrastat, = intrastat_template.products

        # Create international sale (to france), with intrastat exempt and intrastat bound items
        Sale = Model.get('sale.sale')
        sale = Sale()
        sale.party = customer_fr
        sale.invoice_method = 'order'
        sale_line = sale.lines.new()
        sale_line.product = product
        sale_line.quantity = 10
        sale_line.unit_price = Decimal(40)
        intrastat_line = sale.lines.new()
        intrastat_line.product = product_intrastat
        intrastat_line.quantity = 5
        intrastat_line.unit_price = Decimal(60)
        sale.save()
        sale.click('quote')
        sale.click('confirm')
        sale.click('process')

        # Send sale shipment
        shipment, = sale.shipments
        shipment.click('wait')
        shipment.click('pick')
        shipment.click('pack')
        shipment.click('do')
        self.assertEqual(shipment.state, 'done')

        # Check that, despite being an international shipment,
        # the intrastat exempt move has no intrastat info
        move, intrastat_move = shipment.outgoing_moves
        self.assertEqual(move.intrastat_type, None)
        self.assertEqual(move.intrastat_warehouse_country, None)
        self.assertEqual(move.intrastat_country, None)
        self.assertEqual(move.intrastat_subdivision, None)
        self.assertEqual(move.intrastat_tariff_code, None)
        self.assertEqual(move.intrastat_value, Decimal('400.00'))
        self.assertEqual(move.intrastat_transaction, None)
        self.assertEqual(move.intrastat_additional_unit, None)
        self.assertEqual(move.intrastat_country_of_origin, None)
        self.assertEqual(move.intrastat_vat, None)
        self.assertEqual(move.intrastat_declaration, None)

        # Meanwhile the intrastat bound move has all intrastat info set
        self.assertEqual(intrastat_move.intrastat_type, 'dispatch')
        self.assertEqual(intrastat_move.intrastat_warehouse_country.code, 'BE')
        self.assertEqual(intrastat_move.intrastat_country.code, 'FR')
        self.assertEqual(intrastat_move.intrastat_subdivision.intrastat_code, '2')
        self.assertEqual(intrastat_move.intrastat_tariff_code.code, '9403 10 51')
        self.assertEqual(intrastat_move.intrastat_value, Decimal('300.00'))
        self.assertEqual(intrastat_move.intrastat_transaction.code, '11')
        self.assertEqual(intrastat_move.intrastat_additional_unit, 5.0)
        self.assertEqual(intrastat_move.intrastat_country_of_origin.code, 'CN')

        # Update intrastat
        update = Wizard('account.stock.eu.intrastat.update')
        update.form.period, = Period.find([('start_date', '<=', today),
                                             ('end_date', '>=', today)])
        update.execute('update')


        # Confirm that both moves stayed the same after intrastat update
        move, intrastat_move = shipment.outgoing_moves
        self.assertEqual(move.intrastat_type, None)
        self.assertEqual(move.intrastat_warehouse_country, None)
        self.assertEqual(move.intrastat_country, None)
        self.assertEqual(move.intrastat_subdivision, None)
        self.assertEqual(move.intrastat_tariff_code, None)
        self.assertEqual(move.intrastat_value, Decimal('400.00'))
        self.assertEqual(move.intrastat_transaction, None)
        self.assertEqual(move.intrastat_additional_unit, None)
        self.assertEqual(move.intrastat_country_of_origin, None)
        self.assertEqual(move.intrastat_vat, None)
        self.assertEqual(move.intrastat_declaration, None)

        self.assertEqual(intrastat_move.intrastat_type, 'dispatch')
        self.assertEqual(intrastat_move.intrastat_warehouse_country.code, 'BE')
        self.assertEqual(intrastat_move.intrastat_country.code, 'FR')
        self.assertEqual(intrastat_move.intrastat_subdivision.intrastat_code, '2')
        self.assertEqual(intrastat_move.intrastat_tariff_code.code, '9403 10 51')
        self.assertEqual(intrastat_move.intrastat_value, Decimal('300.00'))
        self.assertEqual(intrastat_move.intrastat_transaction.code, '11')
        self.assertEqual(intrastat_move.intrastat_additional_unit, 5.0)
        self.assertEqual(intrastat_move.intrastat_country_of_origin.code, 'CN')
