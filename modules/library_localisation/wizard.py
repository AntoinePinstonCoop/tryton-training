import datetime

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button
from trytond.pyson import Date, Eval, PYSONEncoder
import debugpy

__all__ = [
    'SafeFromQuarantine',
    'SelectSafeQuarantine',
    'Return',
    'CreateExemplaries',
    'CreateExemplariesParameters',
    ]


class SafeFromQuarantine(Wizard):
    'Safe from quarantine'
    __name__ = 'library.localisation.quarantine.safe'

    start_state = 'select_safe_quarantine'
    select_safe_quarantine = StateView(
        'library.localisation.quarantine.safe.choose_quarantine',
        'library_localisation.safe_quarantine_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Remove from quarantine', 'delete_quarantine', 'tryton-go-next', default=True)])
    delete_quarantine = StateTransition()
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
                'early_out_quarantine': 'At least one exemplary didnt make a '
                'week in quarantine',
                })
    
    def default_select_safe_quarantine(self, name):
        Quarantine = Pool().get('library.localisation.quarantine')

        quarantine = Quarantine.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*quarantine.select(quarantine.id,
                where=(quarantine.date + datetime.timedelta(days=7)) 
                    <= datetime.date.today()))
        
        safe_quarantine_id = [x[0] for x in cursor.fetchall()]

        return {
            'quarantines': safe_quarantine_id,
            }   
 
    def transition_delete_quarantine(self):
        Quarantine = Pool().get('library.localisation.quarantine')
        quarantine_to_end = self.select_safe_quarantine.quarantines
        
        for quarantine in quarantine_to_end:
            if quarantine.date + datetime.timedelta(days=7) > datetime.date.today():
                self.raise_user_error("early_out_quarantine")
        
        Quarantine.delete(quarantine_to_end)
        return 'end'

    def end(self):
        return 'reload'

class SelectSafeQuarantine(ModelView):
    'SelectSafeQuarantine'
    __name__ = 'library.localisation.quarantine.safe.choose_quarantine'

    quarantines = fields.One2Many("library.localisation.quarantine", "choose_quarantine", "Quarantine to end")


class Return(metaclass=PoolMeta):
    __name__ = 'library.user.return'

    def transition_return_(self):
        Checkout = Pool().get('library.user.checkout')
        Quarantine = Pool().get('library.localisation.quarantine')
        
        Checkout.write(list(self.select_checkouts.checkouts), {
                'return_date': self.select_checkouts.date})
        
        # Add the returned exemplary to the quarantine aera
        to_create = []
        for checkout in self.select_checkouts.checkouts:
            quarantine = Quarantine()
            quarantine.date = datetime.date.today()
            quarantine.exemplary = checkout.exemplary
            to_create.append(quarantine)
        Quarantine.save(to_create)
        
        return 'end'


class CreateExemplaries(metaclass=PoolMeta):
    __name__ = 'library.book.create_exemplaries'

    def default_parameters(self, name):
        if Transaction().context.get('active_model', '') != 'library.book':
            self.raise_user_error('invalid_model')
        return {
            'acquisition_date': datetime.date.today(),
            'book': Transaction().context.get('active_id'),
            'acquisition_price': 0,
            'number_in_store': 0,
            }

    def transition_create_exemplaries(self):
        if (self.parameters.acquisition_date and
                self.parameters.acquisition_date > datetime.date.today()):
            self.raise_user_error('invalid_date')
        cursor = Transaction().connection.cursor()
        
        Exemplary = Pool().get('library.book.exemplary')
        shelf = Pool().get('library.localisation.room.shelf').__table__()
        
        cursor.execute(*shelf.select(shelf.id,
                where=shelf.is_store==True))
        store_id = cursor.fetchone()[0]
        
        to_create = []
        while len(to_create) < self.parameters.number_of_exemplaries:
            exemplary = Exemplary()
            exemplary.book = self.parameters.book
            exemplary.acquisition_date = self.parameters.acquisition_date
            exemplary.acquisition_price = self.parameters.acquisition_price
            exemplary.identifier = self.parameters.identifier_start + str(
                len(to_create) + 1)
            if len(to_create) < self.parameters.number_in_store:
                exemplary.shelf = store_id
            else:
                exemplary.shelf = self.parameters.shelf
            to_create.append(exemplary)
        Exemplary.save(to_create)
        self.parameters.exemplaries = to_create
        return 'open_exemplaries'


class CreateExemplariesParameters(metaclass=PoolMeta):
    __name__ = 'library.book.create_exemplaries.parameters'

    shelf = fields.Many2One('library.localisation.room.shelf', 
        "Shelf to put the exemplaries", "shelf", required=True)
    number_in_store = fields.Integer("Number of exemplaries in the store", 
        "The rest of the exemplaries will be put on the shelf you defined")
