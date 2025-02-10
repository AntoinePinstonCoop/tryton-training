

import datetime

from sql import Window
from sql.conditionals import Coalesce
from sql.aggregate import Count, Max

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, fields
from trytond.model import Unique
from trytond.pyson import Eval, If, Bool
from trytond.pool import PoolMeta


__all__ = [
    'User',
    'Checkout',
    'Exemplary',
    ]

class User(ModelView, ModelSQL):
    'User'
    __name__ = "library.user"
    
    borrowed_book = checkouts = fields.One2Many('library.user.checkout', 'user', 'Checkouts')
    name = fields.Char('Name', required=True)
    registration_date = fields.Date('Registration Date', help='The date at '
        'which the user registered in the library')
    date_new
    number_of_book
    number_of_book    
        
class Checkout(ModelSQL):
    'Checkout'
    __name__ = 'library.user.checkout'

    user = fields.Many2One('library.user', 'User', required=True,
        ondelete='CASCADE', select=True)
    exemplary = fields.Many2One('library.book.exemplary', 'Exemplary',
        required=True, ondelete='CASCADE', select=True)
    date = fields.Date('Date', required=True)
    return_date = fields.Date('Return Date')
    expected_return

class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'

    checkouts = fields.One2Many('library.user.checkout', 'exemplary',
        'Checkouts')
    is_available = fields.Function()