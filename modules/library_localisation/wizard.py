import datetime

from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button
from trytond.pyson import Date, Eval, PYSONEncoder
import debugpy

__all__ = [
    'SafeFromQuarantine',
    'SelectSafeQuarantine'
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


# Surcharge du wizard de remise des livres

# Emprunt pour bloquer les livres dans la reserve
# faisable avec domain