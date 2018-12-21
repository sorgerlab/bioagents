from indra.statements import *
from bioagents.mra.model_diagnoser import ModelDiagnoser
from indra.assemblers.pysb import PysbAssembler
from nose.plugins.attrib import attr


drug = Agent('PLX4720')
raf = Agent('RAF', db_refs={'FPLX': 'RAF'})
mek = Agent('MEK', db_refs={'FPLX': 'MEK'})
erk = Agent('ERK', db_refs={'FPLX': 'ERK'})


def test_missing_activity1():
    stmts = [Activation(raf, mek), Phosphorylation(mek, erk)]
    md = ModelDiagnoser(stmts)
    suggs = md.get_missing_activities()
    assert len(suggs) == 1
    assert suggs[0].enz.name == 'MEK'
    assert suggs[0].enz.activity
    assert suggs[0].enz.activity.activity_type == 'activity'


def test_missing_activity2():
    stmts = [Inhibition(drug, raf), Activation(raf, mek)]
    md = ModelDiagnoser(stmts)
    suggs = md.get_missing_activities()
    assert len(suggs) == 1
    assert suggs[0].subj.name == 'RAF'
    assert suggs[0].subj.activity
    assert suggs[0].subj.activity.activity_type == 'activity'


def test_missing_activity3():
    stmts = [Activation(raf, mek), Activation(raf, erk)]
    md = ModelDiagnoser(stmts)
    suggs = md.get_missing_activities()
    assert len(suggs) == 0


def test_check_model():
    explain = Activation(raf, erk)
    mek_active = Agent('MEK', db_refs={'FPLX': 'MEK'},
                       activity=ActivityCondition('activity', True))
    model_stmts = [Activation(raf, mek), Activation(mek_active, erk)]
    # Build the pysb model
    pa = PysbAssembler()
    pa.add_statements(model_stmts)
    pa.make_model(policies='one_step')
    md = ModelDiagnoser(model_stmts, pa.model, explain)
    result = md.check_explanation()
    assert result['has_explanation'] is True
    path = result['explanation_path']
    assert len(path) == 2
    assert path[0] == model_stmts[0]
    assert path[1] == model_stmts[1]


@attr('nonpublic')
def test_propose_statement():
    jun = Agent('JUN', db_refs={'HGNC':'6204', 'UP': 'P05412'})
    explain = Activation(raf, jun)
    erk_active = Agent('ERK', db_refs={'FPLX': 'ERK'},
                       activity=ActivityCondition('activity', True))
    # Leave out MEK activates ERK
    model_stmts = [Activation(raf, mek), Activation(erk_active, jun)]
    # Build the pysb model
    pa = PysbAssembler()
    pa.add_statements(model_stmts)
    pa.make_model(policies='one_step')
    md = ModelDiagnoser(model_stmts, pa.model, explain)
    result = md.check_explanation()
    assert result['has_explanation'] is False
    assert result.get('explanation_path') is None
    inf_prop = result.get('connect_rules')
    assert inf_prop == ('RAF_activates_MEK_activity',
                        'ERK_act_activates_JUN_activity'), inf_prop
    stmt_prop = result.get('connect_stmts')
    assert stmt_prop == (model_stmts[0], model_stmts[1])
    stmt_suggestions = md.suggest_statements(*stmt_prop)
