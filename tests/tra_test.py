import sympy.physics.units as units
from bioagents.trips.kqml_list import KQMLList
from bioagents.tra import tra_module
from bioagents.tra.tra import *
from nose.tools import raises

def test_time_interval():
    TimeInterval(2.0, 4.0, 'second')

def test_get_time_interval_full():
    ts = '(:lower-bound 2 :upper-bound 4 :unit "hour")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)
    assert ti.lb == 2*units.hour
    assert ti.ub == 4*units.hour
    assert ti.get_lb_seconds() == 7200
    assert ti.get_ub_seconds() == 14400

def test_get_time_interval_ub():
    ts = '(:upper-bound 4 :unit "hour")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)
    assert ti.lb is None
    assert ti.ub == 4*units.hours
    assert ti.get_ub_seconds() == 14400

def test_get_time_interval_lb():
    ts = '(:lower-bound 4 :unit "hour")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)
    assert ti.lb == 4*units.hours
    assert ti.ub is None
    assert ti.get_lb_seconds() == 14400

@raises(InvalidTimeIntervalError)
def test_get_time_interval_nounit():
    ts = '(:lower-bound 4)'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)

@raises(InvalidTimeIntervalError)
def test_get_time_interval_badunit():
    ts = '(:lower-bound 4 :unit "xyz")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)

def test_get_molecular_entity():
    me = KQMLList.from_string('(:description "%s")' % ekb_complex)
    ent = tra_module.get_molecular_entity(me)

def test_get_molecular_condition():
    lst = KQMLList.from_string('(:type "decrease" :quantity (:type "total" ' +\
                               ':entity (:description "%s")))' % ekb_braf)
    mc = tra_module.get_molecular_condition(lst)

def test_get_temporal_pattern():
    pattern_msg = '(:type "transient" :entities ((:description ' + \
                    '"%s")))' % ekb_complex
    lst = KQMLList.from_string(pattern_msg)
    ent = tra_module.get_temporal_pattern(lst)

def test_decode_model():
    model_str = '"from pysb import *\nModel()\nMonomer(\\"M\\")"'
    model = tra_module.decode_model(model_str)
    assert(model.monomers[0].name == 'M')

ekb_braf = '<ekb><TERM dbid=\\"UP:P15056|HGNC:1097\\" id=\\"V34744\\"><type>ONT::GENE</type><name>BRAF</name><text>BRAF</text></TERM></ekb>'

ekb_complex = '<ekb><TERM id=\\"V34770\\"><type>ONT::MACROMOLECULAR-COMPLEX</type><components><component id=\\"V34744\\"/><component id=\\"V34752\\"/></components><text normalization=\\"\\">The BRAF-KRAS complex</text></TERM> <TERM dbid=\\"UP:P15056|HGNC:1097\\" id=\\"V34744\\"><type>ONT::GENE</type><name>BRAF</name><text>The BRAF-KRAS complex</text></TERM> <TERM dbid=\\"UP:P79800|HGNC:6407|UP:Q5EFX7|UP:O42277|UP:P01116|UP:Q05147|XFAM:PF00071|UP:Q9YH38\\" id=\\"V34752\\"><type>ONT::GENE-PROTEIN</type><name>KRAS</name><text>KRAS</text></TERM></ekb>'
