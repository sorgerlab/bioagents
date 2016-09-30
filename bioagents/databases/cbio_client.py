import urllib, urllib2
import pandas
import numpy
import StringIO

cbio_url = 'http://www.cbioportal.org/webservice.do'

def send_request(data, skiprows=None):
    '''
    Sends a web service requrest to the cBio portal with arguments given in
    the dictionary data and returns a Pandas data frame on success.
    '''
    data_str = urllib.urlencode(data)
    req = urllib2.Request(cbio_url, data_str)
    res = urllib2.urlopen(req)
    data_frame = pandas.read_csv(res, sep='\t', skiprows=skiprows)
    return data_frame

def get_mutations(study_id, gene_list_str, mutation_type=None):
    '''
    Get mutations in a given list of genes for a given study filtered
    to a mutation type if needed.
    mutation_type can be: missense, nonsense, frame_shift_ins,
                            frame_shift_del, splice_site
    '''
    genetic_profile = get_genetic_profiles(study_id, 'mutation')[0]

    data = {'cmd': 'getMutationData',
            'case_set_id': study_id,
            'genetic_profile_id': genetic_profile,
            'gene_list': gene_list_str}
    df = send_request(data, skiprows=1)
    res = _filter_data_frame(df, ['gene_symbol', 'amino_acid_change'],
                                   'mutation_type', mutation_type)
    mutations = {'gene_symbol': res['gene_symbol'].values(),
                 'amino_acid_change': res['amino_acid_change'].values()}
    return mutations

def get_num_sequenced(study_id):
    '''
    Get the number of sequenced tumors in a given study. This is useful
    for calculating mutation statistics.
    '''
    data = {'cmd': 'getCaseLists',
            'cancer_study_id': study_id}
    df = send_request(data)
    row_filter = df['case_list_id'].str.contains('sequenced', case=False)
    num_case = len(df[row_filter]['case_ids'].tolist()[0].split(' '))
    return num_case

def get_genetic_profiles(study_id, filter_str=None):
    '''
    Get the list of all genetic profiles for a given study. The genetic
    profiles include mutations, rppa, methylation, etc.
    '''
    data = {'cmd': 'getGeneticProfiles',
            'cancer_study_id': study_id}
    df = send_request(data)
    res = _filter_data_frame(df, ['genetic_profile_id'],
                                  'genetic_alteration_type', filter_str)
    genetic_profiles = res['genetic_profile_id'].values()
    return genetic_profiles

def get_cancer_studies(filter_str=None):
    '''
    Get the list of all cancer studies that have filter_str
    in their id. There are typically multiple studies for
    a given type of cancer.
    '''
    data = {'cmd': 'getCancerStudies'}
    df = send_request(data)
    df.to_csv('cbio_cancer_studies.tsv', sep='\t', index=False)
    res = _filter_data_frame(df, ['cancer_study_id'],
                             'cancer_study_id', filter_str)
    study_ids = res['cancer_study_id'].values()
    return study_ids

def get_cancer_types(filter_str=None):
    '''
    Get the list of all cancer types that have filter_str
    in their name.
    '''
    data = {'cmd': 'getTypesOfCancer'}
    df = send_request(data)
    df.to_csv('cbio_cancer_types.tsv', sep='\t', index=False)
    res = _filter_data_frame(df, ['type_of_cancer_id'], 'name', filter_str)
    type_ids = res['type_of_cancer_id'].values()
    return type_ids

def _filter_data_frame(df, data_col, filter_col, filter_str=None):
    '''
    Filter a column of a data frame for a given string
    and return the corresponding rows of the data column as a dictionary.
    '''
    if filter_str is not None:
        relevant_cols = data_col + [filter_col]
        df.dropna(inplace=True, subset=relevant_cols)
        row_filter = df[filter_col].str.contains(filter_str, case=False)
        data_list = df[row_filter][data_col].to_dict()
    else:
        data_list = df[data_col].to_dict()
    return data_list
