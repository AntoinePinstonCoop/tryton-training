

import datetime

from sql import Window, Null
from sql.conditionals import Coalesce
from sql.aggregate import Count, Max, Min
import sqlparse
# TODO imports
import debugpy

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, fields
from trytond.model import Unique
from trytond.pyson import Eval, If, Bool, Or
from trytond.pool import PoolMeta
from trytond.model.fields import SQL_OPERATORS

__all__ = [
    'User',
    'Checkout',
    'Exemplary',
    ]

# TODO out 
# debugpy.listen(("localhost", 5678))

class User(ModelView, ModelSQL):
    'User'
    __name__ = "library.user"
    
    name = fields.Char('Name', required=True)
    registration_date = fields.Date('Registration Date', help='The date at '
        'which the user registered in the library', 
        domain=[("registration_date", "<=", datetime.date.today())]) 
    borrowed_book = checkouts = fields.One2Many('library.user.checkout', 'user', 'Checkouts')
    checkedout_books = fields.Function(
        fields.Integer('Checked-out books', help='The number of books a user '
            'has currently checked out', readonly=True),
    'getter_checkedout_books')
    late_checkedout_books = fields.Function(
        fields.Integer('Late checked-out books', help='The number of books a '
            'user is late returning', readonly=True),
        'getter_checkedout_books')
    expected_return_date = fields.Function(
        fields.Date('Expected return date', help='The date at which the user '
            'is (or was) expected to return his books', readonly=True),
        'getter_checkedout_books', searcher='search_expected_return_date')
    
    
    @classmethod
    def getter_checkedout_books(cls, users, name):
        if name in ("checkedout_books", "late_checkedout_books"):
            result = {x.id: 0 for x in users}
        else:
            result = {x.id: None for x in users}
            
        Checkout = Pool().get('library.user.checkout')
        checkout = Checkout.__table__()
        cursor = Transaction().connection.cursor()
        column, cond = None, None
        
        if name == "checkedout_books":
            column = Count(checkout.exemplary)
            cond = checkout.user.in_([x.id for x in users]) & \
                (checkout.return_date==Null)
        elif name == "late_checkedout_books":
            column = Count(checkout.exemplary)
            cond = checkout.user.in_([x.id for x in users]) & \
                (checkout.return_date==Null) & \
                ((checkout.date + datetime.timedelta(days=20))<(datetime.date.today()))
        elif name == "expected_return_date":
            column = Min(checkout.date)
            cond = checkout.user.in_([x.id for x in users]) & (checkout.return_date==Null)            
            
        cursor.execute(*checkout.select(checkout.user, column,
                    where=(cond),
                    group_by=[checkout.user]))
        
        for user_id, fetched_value in cursor.fetchall():
            result[user_id] = fetched_value
            if name == "expected_return_date":
                result[user_id] = fetched_value + datetime.timedelta(days=20)
        return result
    
    @classmethod
    def search_expected_return_date(cls, name, clause):
        user = cls.__table__()
        checkout = Pool().get('library.user.checkout').__table__()
        _, operator, value = clause
        if isinstance(value, datetime.date):
            value = value + datetime.timedelta(days=-20)
        if isinstance(value, (list, tuple)):
            value = [(x + datetime.timedelta(days=-20) if x else x)
                for x in value]
        Operator = SQL_OPERATORS[operator]

        query_table = user.join(checkout, 'LEFT OUTER',
            condition=checkout.user == user.id)

        query = query_table.select(user.id,
            where=(checkout.return_date == Null) |
            (checkout.id == Null),
            group_by=user.id,
            having=Operator(Min(checkout.date), value))
        return [('id', 'in', query)]
    
        
class Checkout(ModelSQL, ModelView):
    'Checkout'
    __name__ = 'library.user.checkout'

    user = fields.Many2One('library.user', 'User', required=True,
        ondelete='CASCADE', select=True)
    exemplary = fields.Many2One('library.book.exemplary', 'Exemplary',
        required=True, ondelete='CASCADE', select=True)
    date = fields.Date('Date', required=True, 
        domain=[("date", "<=", datetime.date.today())])
    return_date = fields.Date('Return Date', 
        domain=['OR',
            [("return_date", "=", None)],
            [("return_date", "<=", datetime.date.today()),
                ("return_date", ">=", Eval("date", datetime.date.today()))],])   
    expected_return_date = fields.Function(
        fields.Date('Expected return date', help='The date at which the '
            'exemplary is supposed to be returned', readonly=True),
        'getter_expected_return_date', searcher="search_expected_return_date")
    
    def getter_expected_return_date(self, name):
        return self.date + datetime.timedelta(days=20)
    
    @classmethod
    def search_expected_return_date(cls, name, clause):
        value = clause[2] + datetime.timedelta(-20)
        return [('date', clause[1], value),]
    
    
class Book(metaclass=PoolMeta):
    __name__ = 'library.book'

    is_available = fields.Function(
        fields.Boolean('Is available', help='If True, at least an exemplary '
            'of this book is currently available for borrowing', readonly=True),
        'getter_is_available', searcher='search_is_available')
    
    @classmethod
    def getter_is_available(cls, books, name):
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()
        book =  pool.get('library.book').__table__()
        
        result = {x.id: False for x in books}
        
        cursor = Transaction().connection.cursor()
        cursor.execute(*book.join(exemplary, condition=(exemplary.book == book.id)
            ).join(checkout, 'LEFT OUTER', condition=(exemplary.id == checkout.exemplary)
            ).select(book.id, where=((checkout.return_date != Null) | (checkout.id == Null)),
                group_by=[book.id]))
        
        for book_id, in cursor.fetchall():
            result[book_id] = True
        return result

    @classmethod
    def search_is_available(cls, name, clause):
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()
        book = cls.__table__()
        _, operator, value = clause
        assert value in (True, False)

        query_table = book.join(exemplary, condition=(exemplary.book == book.id)
            ).join(checkout, 'LEFT OUTER', condition=(exemplary.id == checkout.exemplary))
            
        query = query_table.select(book.id,
            where=((checkout.return_date != Null) | (checkout.id == Null)),
            group_by=book.id)
        operator = 'in' if value else 'not in'
        return [('id', operator, query)]
    

class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'

    checkouts = fields.One2Many('library.user.checkout', 'exemplary',
        'Checkouts')
    is_available = fields.Function(
        fields.Boolean('Is available', help='If True, the exemplary is '
            'currently available for borrowing', readonly=True),
    'getter_is_available', searcher='search_is_available')
    
    @classmethod
    def getter_is_available(cls, exemplaries, name):
        # Default case is True, if we find exemplaries in checking without return_date we set it at False
        result = {x.id: True for x in exemplaries} 
        
        Checkout = Pool().get('library.user.checkout')
        checkout = Checkout.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*checkout.select(checkout.exemplary,
                where=(checkout.exemplary.in_([x.id for x in exemplaries]) & (checkout.return_date==Null))))
        
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = False
        return result
    
    
    @classmethod
    def search_is_available(cls, name, clause):
        return []
    
    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            ('identifier', clause[1], clause[2]),
            ('book.title', clause[1], clause[2]),
            ]
        