#!/usr/bin/env python
from pathlib import Path
from time import time
import argparse
import pandas as pd
import networkx as nx
import logging
import os

pipeline_file = '../example_plan.tsv'

def read_pipeline(pipeline_file):
    pipeline = pd.read_csv(pipeline_file, sep='\t', header=None)
    if pipeline.shape[1] == 2:
        pipeline = pipeline.set_axis(['source', 'target'], axis=1)
        pipeline['status'] = 0
    elif pipeline.shape[1] == 3:
        pipeline = pipeline.set_axis(['source', 'target','status'], axis=1)
    return pipeline

def save_pipeline(pipeline):
    pipeline.to_csv(
            f"{os.getpid()}_{os.path.basename(pipeline_file)}.tsv",
            sep='\t',
            index=False)

def first_run(pipeline):
    if pipeline.satus.sum() == 0:
        return True
    return False

def find_first(pipeline):
    #whichever gets to the joined one first removes from tree
    G = nx.from_pandas_edgelist(pipeline, create_using=nx.DiGraph())
    indegree = pd.DataFrame(G.in_degree())
    pipeline.loc[pipeline.source.isin(indegree.loc[indegree[1] == 0, 0]), 'status'] = 'Starting'

def run(pipeline_file):
    pipeline = read_pipeline(pipeline_file)
    if first_run(pipeline):
        processes = find_first(pipeline)
        for process in processes:
            process.status = 'Running'
    status = pipeline.loc[pipeline.status != 0]
    if status.iloc[0].status == 'Starting':
        subprocess.Popen(process, shell=True)
        save_pipeline(processes)
        # LEFT HERE

subprocess.call(process, shell=True)
subprocess.Popen(process, shell=True)

# while jobs_left:
run()

def runner();
    pipeline = read_pipeline(pipeline_file)
    pipeline.loc[pipeline.status == 'Starting']
    if pipeline.status
        pipeline.loc[pipeline.status == 'Starting'].source.unique()
