import datetime as dt
import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (
    create_chart, create_fiscalyear, get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules, set_user


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test_stock_user_intrastat_value_with_landed_cost(self):
        today = dt.date.today()

        config = activate_modules([
            'account_stock_eu_es', 'account_stock_landed_cost'])

        Organization = Model.get('country.organization')
        Country = Model.get('country.country')
        Party = Model.get('party.party')
        User = Model.get('res.user')
        Group = Model.get('res.group')
        Company = Model.get('company.company')
        Employee = Model.get('company.employee')
        ProductCategory = Model.get('product.category')
        ProductTemplate = Model.get('product.template')
        ProductUom = Model.get('product.uom')
        ShipmentIn = Model.get('stock.shipment.in')
        StockLocation = Model.get('stock.location')
        Move = Model.get('stock.move')
        TariffCode = Model.get('customs.tariff.code')

        eur = get_currency('EUR')
        _ = create_company(currency=eur)
        company = get_company()

        europe, = Organization.find([('code', '=', 'EU')])
        belgium = Country(name='Belgium', code='BE')
        belgium.subdivisions.new(
            name='Walloon Region', intrastat_code='2', type='region')
        belgium.save()
        walloon, = belgium.subdivisions
        belgium.subdivisions.new(
            name='Liege', type='province', parent=walloon)
        belgium.save()
        liege, = [s for s in belgium.subdivisions if s.parent == walloon]
        france = Country(name='France', code='FR')
        france.save()
        europe.members.new(country=belgium)
        europe.members.new(country=france)
        europe.save()

        company_address, = company.party.addresses
        company_address.country = belgium
        company_address.subdivision = liege
        company_address.save()

        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        _ = create_chart(company)
        accounts = get_accounts(company)
        expense = accounts['expense']
        revenue = accounts['revenue']

        supplier = Party(name='Supplier')
        address, = supplier.addresses
        address.country = france
        supplier.save()

        account_category = ProductCategory(name='Account Category')
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

        unit, = ProductUom.find([('name', '=', 'Unit')])
        kg, = ProductUom.find([('name', '=', 'Kilogram')])

        tariff_code = TariffCode(code='9403 10 51')
        tariff_code.description = 'Desks'
        tariff_code.intrastat_uom = unit
        tariff_code.save()

        template = ProductTemplate()
        template.name = 'Product'
        template.type = 'goods'
        template.default_uom = unit
        template.account_category = account_category
        template.cost_price = Decimal('80')
        template.weight = 1
        template.weight_uom = kg
        template.tariff_codes.new(tariff_code=tariff_code)
        template.save()
        product, = template.products

        employee_party = Party(name='Stock User')
        employee_party.save()
        employee = Employee()
        employee.party = employee_party
        employee.company = company
        employee.save()

        stock_user = User()
        stock_user.name = 'Stock User'
        stock_user.login = 'stock'
        stock_user.employees.append(employee)
        stock_user.employee = employee
        stock_user.companies.append(Company(company.id))
        stock_user.company = company
        stock_group, = Group.find([('name', '=', 'Stock')])
        stock_user.groups.append(stock_group)
        stock_user.save()

        set_user(stock_user.id)
        config._context = User.get_preferences(True, config.context)

        warehouse, = StockLocation.find([('code', '=', 'WH')])
        shipment = ShipmentIn()
        shipment.planned_date = today
        shipment.warehouse = warehouse
        shipment.supplier = supplier
        shipment.incoming_moves.append(Move())
        move, = shipment.incoming_moves
        move.product = product
        move.quantity = 10
        move.from_location = shipment.supplier_location
        move.to_location = shipment.warehouse_input
        move.unit = unit
        move.unit_price = Decimal('100')
        move.currency = company.currency
        shipment.click('receive')
        shipment.click('do')

        move, = shipment.incoming_moves
        self.assertEqual(move.intrastat_value, Decimal('1000.00'))
