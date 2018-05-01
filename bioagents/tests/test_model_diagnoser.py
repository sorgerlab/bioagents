from indra.statements import *
from bioagents.mra.model_diagnoser import ModelDiagnoser

drug = Agent('PLX4720')
raf = Agent('RAF')
mek = Agent('MEK')
erk = Agent('ERK')

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
