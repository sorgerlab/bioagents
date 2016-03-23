Biological reasoning agents
===========================

A collection of agents for biological reasoning in a communication system. The following agents are currently available: 

- MRA (Mechanistic Reasoning Agent): The MRA uses INDRA to construct mechanistic models of biochemical systems from user input, publications and databases. It can also propose changes to model structure autonomously. 
- MEA (Model Execution Agent): The MEA sets up simulation conditions, simulates models and interprets the output.
- DTDA (Disease, Target and Drug Agent): The DTDA's task is to search for targets known to be implicated in a disease and to look for drugs that are known to affect that target.

We also provide a python implementation of a generic module in the TRIPS dialogue system and a python implementation of a KQML message dispatcher. 

Installing the bioagents
========================
Note that currently the bioagents have limited usage on their own. They are
meant to be launched in the context of a communication system. 

The bioagents depend on the following non-default python packages: objectpath,
rdflib, jnius-indra, functools32, requests, lxml, pandas, suds

The MRA uses [INDRA](https://github.com/sorgerlab/indra) to assemble models
based on a natural language description of mechanisms. Please follow the
more detailed instructions on the [INDRA page](https://github.com/sorgerlab/indra) 
to install it and its dependencies:

`pip install git+https://github.com/sorgerlab/indra.git`

INDRA depends on [PySB](http://pysb.org), which is best installed from Github:

`pip install git+https://github.com/pysb/pysb.git`

PySB depends on [BioNetGen](http://bionetgen.org/index.php/Download). Make sure
that BioNetGen is unzipped into /usr/local/share/BioNetGen, such that BNG2.pl is located at /usr/local/share/BioNetGen/BNG2.pl. Alternatively, set BNGPATH 
to the folder in which BNG2.pl is.
