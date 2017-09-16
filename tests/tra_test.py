import json
from xml.etree import ElementTree
from nose.tools import raises
import sympy.physics.units as units
from bioagents.tra import tra_module
from bioagents.tra.tra import *
from indra.sources import trips
from pysb import Model, Rule, Monomer, Parameter, Initial, SelfExporter
from indra.statements import stmts_to_json, Agent, Phosphorylation,\
    Dephosphorylation
from kqml import KQMLPerformative, KQMLString, KQMLList
from tests.util import *
from tests.integration import _StringCompareTest

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

def test_molecular_quantity_conc1():
    s = '(:type "concentration" :value 2 :unit "uM")'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)
    assert mq.quant_type == 'concentration'
    assert mq.value == 2 * units.micro * units.mol / units.liter

def test_molecular_quantity_conc2():
    s = '(:type "concentration" :value 200 :unit "nM")'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)
    assert mq.quant_type == 'concentration'
    assert mq.value == 200 * units.nano * units.mol / units.liter

@raises(InvalidMolecularQuantityError)
def test_molecular_quantity_conc_badval():
    s = '(:type "concentration" :value "xyz" :unit "nM")'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)

@raises(InvalidMolecularQuantityError)
def test_molecular_quantity_conc_badunit():
    s = '(:type "concentration" :value 200 :unit "meter")'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)

def test_molecular_quantity_num():
    s = '(:type "number" :value 20000)'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)
    assert mq.quant_type == 'number'
    assert mq.value == 20000

@raises(InvalidMolecularQuantityError)
def test_molecular_quantity_num_badval():
    s = '(:type "number" :value -1)'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)

def test_molecular_quantity_qual():
    s = '(:type "qualitative" :value "high")'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)
    assert mq.quant_type == 'qualitative'
    assert mq.value == 'high'

@raises(InvalidMolecularQuantityError)
def test_molecular_quantity_qual_badval():
    s = '(:type "qualitative" :value 123)'
    lst = KQMLList.from_string(s)
    mq = tra_module.get_molecular_quantity(lst)

def test_molecular_quantity_ref():
    s = '(:type "total" :entity (:description "%s"))' % ekb_complex
    lst = KQMLList.from_string(s)
    mqr = tra_module.get_molecular_quantity_ref(lst)
    assert mqr.quant_type == 'total'
    assert len(mqr.entity.bound_conditions) == 1

def test_molecular_quantity_ref2():
    s = '(:type "initial" :entity (:description "%s"))' % ekb_complex
    lst = KQMLList.from_string(s)
    mqr = tra_module.get_molecular_quantity_ref(lst)
    assert mqr.quant_type == 'initial'
    assert len(mqr.entity.bound_conditions) == 1

@raises(InvalidMolecularQuantityRefError)
def test_molecular_quantity_badtype():
    s = '(:type "xyz" :entity (:description "%s"))' % ekb_complex
    lst = KQMLList.from_string(s)
    mqr = tra_module.get_molecular_quantity_ref(lst)

@raises(InvalidMolecularQuantityRefError)
def test_molecular_quantity_badentity():
    s = '(:type "xyz" :entity (:description "xyz"))'
    lst = KQMLList.from_string(s)
    mqr = tra_module.get_molecular_quantity_ref(lst)

def test_get_molecular_condition_dec():
    lst = KQMLList.from_string('(:type "decrease" :quantity (:type "total" ' +\
                               ':entity (:description "%s")))' % ekb_braf)
    mc = tra_module.get_molecular_condition(lst)
    assert mc.condition_type == 'decrease'
    assert mc.quantity.quant_type == 'total'
    assert mc.quantity.entity.name == 'BRAF'

def test_get_molecular_condition_exact():
    lst = KQMLList.from_string('(:type "exact" :value (:value 0 :type "number") ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_braf)
    mc = tra_module.get_molecular_condition(lst)
    assert mc.condition_type == 'exact'
    assert mc.value.quant_type == 'number'
    assert mc.quantity.quant_type == 'total'
    assert mc.quantity.entity.name == 'BRAF'

def test_get_molecular_condition_multiple():
    lst = KQMLList.from_string('(:type "multiple" :value 2 ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_braf)
    mc = tra_module.get_molecular_condition(lst)
    assert mc.condition_type == 'multiple'
    assert mc.value == 2.0
    assert mc.quantity.quant_type == 'total'
    assert mc.quantity.entity.name == 'BRAF'

@raises(InvalidMolecularConditionError)
def test_get_molecular_condition_badtype():
    lst = KQMLList.from_string('(:type "xyz" :value 2 ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_braf)
    mc = tra_module.get_molecular_condition(lst)

@raises(InvalidMolecularConditionError)
def test_get_molecular_condition_badvalue():
    lst = KQMLList.from_string('(:type "multiple" :value "xyz" ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_braf)
    mc = tra_module.get_molecular_condition(lst)

@raises(InvalidMolecularConditionError)
def test_get_molecular_condition_badvalue2():
    lst = KQMLList.from_string('(:type "exact" :value 2 ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_braf)
    mc = tra_module.get_molecular_condition(lst)

@raises(InvalidMolecularConditionError)
def test_get_molecular_condition_badentity():
    lst = KQMLList.from_string('(:type "exact" :value 2 ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "xyz")))')
    mc = tra_module.get_molecular_condition(lst)

def test_apply_condition_exact():
    model = _get_gk_model()
    lst = KQMLList.from_string('(:type "exact" :value (:value 0 :type "number") ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_map2k1)
    mc = tra_module.get_molecular_condition(lst)
    apply_condition(model, mc)
    assert model.parameters['MAP2K1_0'].value == 0
    mc.value.value = 2000
    apply_condition(model, mc)
    assert model.parameters['MAP2K1_0'].value == 2000

def test_apply_condition_multiple():
    model = _get_gk_model()
    lst = KQMLList.from_string('(:type "multiple" :value 2.5 ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_map2k1)
    mc = tra_module.get_molecular_condition(lst)
    apply_condition(model, mc)
    assert model.parameters['MAP2K1_0'].value == 250

def test_apply_condition_decrease():
    model = _get_gk_model()
    lst = KQMLList.from_string('(:type "decrease" ' +
                               ':quantity (:type "total" ' +
                               ':entity (:description "%s")))' % ekb_map2k1)
    mc = tra_module.get_molecular_condition(lst)
    pold = model.parameters['MAP2K1_0'].value
    apply_condition(model, mc)
    assert model.parameters['MAP2K1_0'].value < pold

def test_get_molecular_entity():
    me = KQMLList.from_string('(:description "%s")' % ekb_complex)
    ent = tra_module.get_molecular_entity(me)
    assert len(ent.bound_conditions) == 1

def test_get_temporal_pattern():
    pattern_msg = '(:type "transient" :entities ((:description ' + \
                    '"%s")))' % ekb_complex
    lst = KQMLList.from_string(pattern_msg)
    pattern = tra_module.get_temporal_pattern(lst)
    assert pattern.pattern_type == 'transient'

def test_get_temporal_pattern_always():
    pattern_msg = '(:type "always_value" :entities ((:description ' + \
                    '"%s")) :value (:type "qualitative" :value "low"))' % \
                    ekb_complex
    lst = KQMLList.from_string(pattern_msg)
    pattern = tra_module.get_temporal_pattern(lst)
    assert pattern.pattern_type == 'always_value'
    assert pattern.value is not None
    assert pattern.value.quant_type == 'qualitative'
    assert pattern.value.value == 'low'

def test_get_temporal_pattern_sometime():
    pattern_msg = '(:type "sometime_value" :entities ((:description ' + \
                    '"%s")) :value (:type "qualitative" :value "high"))' % \
                    ekb_complex
    lst = KQMLList.from_string(pattern_msg)
    pattern = tra_module.get_temporal_pattern(lst)
    assert pattern.pattern_type == 'sometime_value'
    assert pattern.value is not None
    assert pattern.value.quant_type == 'qualitative'
    assert pattern.value.value == 'high'

def test_get_temporal_pattern_eventual():
    pattern_msg = '(:type "eventual_value" :entities ((:description ' + \
                    '"%s")) :value (:type "qualitative" :value "high"))' % \
                    ekb_complex
    lst = KQMLList.from_string(pattern_msg)
    pattern = tra_module.get_temporal_pattern(lst)
    assert pattern.pattern_type == 'eventual_value'
    assert pattern.value is not None
    assert pattern.value.quant_type == 'qualitative'
    assert pattern.value.value == 'high'

def test_get_all_patterns():
    patterns = get_all_patterns('MAPK1')
    print(patterns)

def test_module():
    tra = tra_module.TRA_Module(testing=True)
    content = KQMLList()
    pattern_msg = '(:type "sometime_value" :entities ((:description ' + \
                    '"%s")) :value (:type "qualitative" :value "high"))' % \
                    ekb_complex
    pattern = KQMLList.from_string(pattern_msg)
    content.set('pattern', pattern)
    model_json = _get_gk_model_indra()
    content.sets('model', model_json)
    res = tra.respond_satisfies_pattern(content)
    assert res[2] is not None


class TestModel(_StringCompareTest):
    """Test that TRA can correctly run a model."""
    def __init__(self, *args):
        super(TestModel, self).__init__(tra_module.TRA_Module)
        self.expected = '(SUCCESS :content (:satisfies-rate 1.0 ' + \
            ':num-sim 10 :suggestion (:type "always_value" ' + \
            ':value (:type "qualitative" :value "low"))))'
        self.entity_str = 'MAPK1-MAP2K1 complex'
        self.model_str = 'MAP2K1 binds MAPK1'
        return

    def get_message(self):
        model = stmts_kstring_from_text(self.model_str)
        entity = ekb_kstring_from_text(self.entity_str)
        condition_entity = ekb_kstring_from_text('MAP2K1')

        entities = KQMLList([KQMLList([':description', entity])])
        pattern = KQMLList()
        pattern.set('entities', entities)

        content = KQMLList('SATISFIES-PATTERN')
        content.set('pattern', pattern)
        content.set('model', model)

        conditions = KQMLList()
        condition = KQMLList()
        condition.sets('type', 'multiple')
        condition.set('value', '10.0')
        quantity = KQMLList()
        quantity.sets('type', 'total')
        entity = KQMLList()
        entity.set('description', condition_entity)
        quantity.set('entity', entity)
        condition.set('quantity', quantity)
        conditions.append(condition)
        content.set('conditions', conditions)
        msg = KQMLPerformative('REQUEST')
        msg.set('content', content)
        msg.set('reply-with', 'IO-1')
        return (msg, content)

ekb_map2k1 = '<ekb><TERM dbid=\\"UP:Q02750|HGNC:6840\\" end=\\"6\\" id=\\"V2700141\\"><type>ONT::GENE</type><name>MAP-2-K-1</name><text>MAP2K1</text></TERM></ekb>'

ekb_braf = '<ekb><TERM dbid=\\"UP:P15056|HGNC:1097\\" id=\\"V34744\\"><type>ONT::GENE</type><name>BRAF</name><text>BRAF</text></TERM></ekb>'

ekb_complex = '<ekb><TERM id=\\"V34770\\"><type>ONT::MACROMOLECULAR-COMPLEX</type><components><component id=\\"V34744\\"/><component id=\\"V34752\\"/></components><text normalization=\\"\\">The BRAF-KRAS complex</text></TERM> <TERM dbid=\\"UP:P15056|HGNC:1097\\" id=\\"V34744\\"><type>ONT::GENE</type><name>BRAF</name><text>The BRAF-KRAS complex</text></TERM> <TERM dbid=\\"UP:P79800|HGNC:6407|UP:Q5EFX7|UP:O42277|UP:P01116|UP:Q05147|XFAM:PF00071|UP:Q9YH38\\" id=\\"V34752\\"><type>ONT::GENE-PROTEIN</type><name>KRAS</name><text>KRAS</text></TERM></ekb>'

def _get_gk_model():
    SelfExporter.do_export = True
    Model()
    Monomer('DUSP6', ['mapk1'])
    Monomer('MAP2K1', ['mapk1'])
    Monomer('MAPK1', ['phospho', 'map2k1', 'dusp6'], {'phospho': ['u', 'p']})

    Parameter('kf_mm_bind_1', 1e-06)
    Parameter('kr_mm_bind_1', 0.001)
    Parameter('kc_mm_phos_1', 0.001)
    Parameter('kf_dm_bind_1', 1e-06)
    Parameter('kr_dm_bind_1', 0.001)
    Parameter('kc_dm_dephos_1', 0.001)
    Parameter('DUSP6_0', 100.0)
    Parameter('MAP2K1_0', 100.0)
    Parameter('MAPK1_0', 100.0)

    Rule('MAP2K1_phospho_bind_MAPK1_phospho_1', MAP2K1(mapk1=None) + \
         MAPK1(phospho='u', map2k1=None) >>
         MAP2K1(mapk1=1) % MAPK1(phospho='u', map2k1=1), kf_mm_bind_1)
    Rule('MAP2K1_phospho_MAPK1_phospho_1', MAP2K1(mapk1=1) % \
         MAPK1(phospho='u', map2k1=1) >>
        MAP2K1(mapk1=None) + MAPK1(phospho='p', map2k1=None), kc_mm_phos_1)
    Rule('MAP2K1_dissoc_MAPK1', MAP2K1(mapk1=1) % MAPK1(map2k1=1) >> 
         MAP2K1(mapk1=None) + MAPK1(map2k1=None), kr_mm_bind_1)
    Rule('DUSP6_dephos_bind_MAPK1_phospho_1', DUSP6(mapk1=None) + 
         MAPK1(phospho='p', dusp6=None) >>
         DUSP6(mapk1=1) % MAPK1(phospho='p', dusp6=1), kf_dm_bind_1)
    Rule('DUSP6_dephos_MAPK1_phospho_1', DUSP6(mapk1=1) % 
         MAPK1(phospho='p', dusp6=1) >>
         DUSP6(mapk1=None) + MAPK1(phospho='u', dusp6=None), kc_dm_dephos_1)
    Rule('DUSP6_dissoc_MAPK1', DUSP6(mapk1=1) % MAPK1(dusp6=1) >> 
         DUSP6(mapk1=None) + MAPK1(dusp6=None), kr_dm_bind_1)

    Initial(DUSP6(mapk1=None), DUSP6_0)
    Initial(MAP2K1(mapk1=None), MAP2K1_0)
    Initial(MAPK1(phospho='u', map2k1=None, dusp6=None), MAPK1_0)
    SelfExporter.do_export = False
    return model

def _get_gk_model_indra():
    kras = Agent('KRAS', db_refs={'HGNC': '6407', 'UP': 'P01116'})
    braf = Agent('BRAF', db_refs={'HGNC': '1097', 'UP': 'P15056'})
    pp2a = Agent('PPP2CA')
    st1 = Phosphorylation(kras, braf)
    st2 = Dephosphorylation(pp2a, braf)
    stmts = [st1, st2]
    stmts_json = json.dumps(stmts_to_json(stmts))
    return stmts_json
