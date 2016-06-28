from bioagents.trips.kqml_list import KQMLList
from bioagents.tra import tra_module

def test_get_time_interval_full():
    ts = '(:lower-bound 2 :upper-bound 4 :unit "hour")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)

def test_get_time_interval_ub():
    ts = '(:upper-bound 4 :unit "hour")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)

def test_get_time_interval_lb():
    ts = '(:lower-bound 4 :unit "hour")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)

def test_get_time_interval_nounit():
    ts = '(:lower-bound 4)'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)

def test_get_time_interval_badunit():
    ts = '(:lower-bound 4 :unit "xyz")'
    lst = KQMLList.from_string(ts)
    ti = tra_module.get_time_interval(lst)

def test_get_molecular_entity():
    me = KQMLList.from_string('(:description "%s")' % ekb_complex)
    print me
    ent = tra_module.get_molecular_entity(me)

def test_get_temporal_pattern():
    pattern_msg = '(:type "transient" :entities ((:description ' + \
                    '"%s")))' % ekb_complex
    lst = KQMLList.from_string(pattern_msg)
    ent = tra_module.get_temporal_pattern(lst)

ekb_complex = '<ekb><TERM id=\\"V34770\\"><type>ONT::MACROMOLECULAR-COMPLEX</type><components><component id=\\"V34744\\"/><component id=\\"V34752\\"/></components><text normalization=\\"\\">The BRAF-KRAS complex</text></TERM> <TERM dbid=\\"UP:P15056|HGNC:1097\\" id=\\"V34744\\"><type>ONT::GENE</type><name>BRAF</name><text>The BRAF-KRAS complex</text></TERM> <TERM dbid=\\"UP:P79800|HGNC:6407|UP:Q5EFX7|UP:O42277|UP:P01116|UP:Q05147|XFAM:PF00071|UP:Q9YH38\\" id=\\"V34752\\"><type>ONT::GENE-PROTEIN</type><name>KRAS</name><text>KRAS</text></TERM></ekb>'
