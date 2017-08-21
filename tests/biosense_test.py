from kqml import KQMLList
from bioagents.biosense.biosense_module import BioSense_Module

def test_choose_sense():
    bs = BioSense_Module(name='biosense', testing=True)
    msg_content = KQMLList.from_string(test_ekb)
    res = bs.respond_choose_sense(msg_content)
    agents = res.get('agents')
    assert agents and agents.data
    agent = agents[0]
    name = agent.gets('name')
    assert name == 'MAP2K1'
    ont_type = agent.get('ont-type')
    assert ont_type == 'ONT::GENE'



test_ekb = '''(CHOOSE-SENSE :EKB-TERM "<ekb>
  <TERM id=\\"V35275\\" dbid=\\"HGNC:6840|XFAM:PF00069|UP:Q05116|UP:Q02750|NCIT:C17808|NCIT:C105947|UP:Q91447|NCIT:C52823\\">
    <type>ONT::GENE-PROTEIN</type>
    <name>MEK-1</name>
    <drum-terms>
      <drum-term name=\\"MAP2K1\\" matched-name=\\"MEK1\\" dbid=\\"NCIT:C52823\\" match-score=\\"0.82444\\">
        <types>
          <type>ONT::GENE</type>
        </types>
      </drum-term>
      <drum-term dbid=\\"NCIT:C105947\\" match-score=\\"0.82444\\" matched-name=\\"MEK1\\" name=\\"mitogen-activated protein kinase kinase\\">
        <types>
          <type>ONT::PROTEIN-FAMILY</type>
        </types>
      </drum-term>
      <drum-term matched-name=\\"MEK-1\\" dbid=\\"NCIT:C17808\\" match-score=\\"0.82438\\" name=\\"MAP2K1 protein\\">
        <types>
          <type>ONT::PROTEIN</type>
        </types>
      </drum-term>
      <drum-term match-score=\\"0.65301\\" dbid=\\"HGNC:6840\\" matched-name=\\"MEK1\\" name=\\"mitogen-activated protein kinase kinase 1\\">
        <types>
          <type>ONT::GENE</type>
        </types>
        <xrefs>
          <xref dbid=\\"UP:Q02750\\"/>
        </xrefs>
      </drum-term>
      <drum-term match-score=\\"0.65301\\" dbid=\\"UP:Q91447\\" matched-name=\\"MEK1\\" name=\\"Dual specificity mitogen-activated protein kinase kinase 1\\">
        <types>
          <type>ONT::PROTEIN</type>
        </types>
        <xrefs>
          <xref dbid=\\"XFAM:PF00069\\"/>
        </xrefs>
      </drum-term>
      <drum-term matched-name=\\"MEK1\\" dbid=\\"UP:Q05116\\" match-score=\\"0.65301\\" name=\\"Dual specificity mitogen-activated protein kinase kinase 1\\">
        <types>
          <type>ONT::PROTEIN</type>
        </types>
        <xrefs>
          <xref dbid=\\"XFAM:PF00069\\"/>
        </xrefs>
      </drum-term>
    </drum-terms>
  </TERM>
</ekb>")'''.replace('\n','')
