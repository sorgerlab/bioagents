class TRA(object):
    pass

class MolecularQuantity(object):
    def __init__(self, quant_type, value, unit=None):
        if quant_type == 'concentration':
            unit = lst.get_keyword_arg(':unit')
            try:
                value_num = float(falue)
            except ValueError:
                msg = 'Invalid quantity type %s' % quant_type
                raise InvalidMolecularQuantityError(msg)
            pass
        elif quant_type == 'number':
            pass
        elif quant_type == 'qualitative':
            if value == 'high':
                pass
            elif value == 'low':
                pass
            else:
                msg = 'Invalid qualitative quantity value %s' % value
                raise InvalidMolecularQuantityError(msg)
            pass
        else:
            raise InvalidMolecularQuantityError('Invalid quantity type %s' %
                                                quant_type)
        self.quant_type = quant_type
        self.value = value
        self.unit = unit

class MolecularQuantityReference(object):
    def __init__(self, quant_type, entity):
        self.quant_type = quant_type
        self.entity = entity

class TimeInterval(object):
    def __init__(self, lb, ub, unit):
        self.lb = lb
        self.ub = ub
        self.unit = unit

class TemporalPattern(object):
    def __init__(self, pattern_type, entities, time_limit, *args, **kwargs):
        if pattern_type == 'transient':
            get_transient_pattern(lst)
        elif pattern_type == 'sustained':
            get_transient_pattern(lst)
        else:
            raise InvalidTemporalPatternError
        self.pattern_type = pattern_type
        self.entities = entities
        self.time_limit = time_limit

def MolecularCondition(object):
    def __init__(self, condition_type, quantity, value):
        self.condition_type = condition_type
        self.quantity = quantity
        self.value = value

class InvalidMolecularQuantityError(Exception):
    pass

class InvalidMolecularEntityError(Exception):
    pass

class InvalidTemporalPatternError(Exception):
    pass

