from ez_setup import use_setuptools
use_setuptools()
from setuptools import setup

def main():
    setup(name='bioagents',
          version='0.0.1',
          description='Biological Reasoning Agents',
          long_description='Biological Reasoning Agents',
          author='Benjamin Gyori',
          author_email='benjamin_gyori@hms.harvard.edu',
          url='http://github.com/sorgerlab/bioagents',
          packages=['bioagents', 'bioagents.KQML', 'bioagents.TripsModule'],
          install_requires=['pysb', 'objectpath', 'rdflib', 'jnius-indra', 
                            'functools32', 'requests', 'lxml', 'suds'],
          include_package_data=True,
          keywords=['systems', 'biology', 'model', 'pathway', 'assembler', 'nlp', 
                    'mechanism', 'biochemistry'],
          classifiers=[
            'Development Status :: 4 - Beta',
            'Environment :: Console',
            'Intended Audience :: Science/Research',
            'License :: OSI Approved :: BSD License',
            'Operating System :: OS Independent',
            'Programming Language :: Python :: 2',
            'Topic :: Scientific/Engineering :: Bio-Informatics',
            'Topic :: Scientific/Engineering :: Chemistry',
            'Topic :: Scientific/Engineering :: Mathematics',
            ],
          )
if __name__ == '__main__':
    main()
