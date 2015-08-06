#!/usr/bin/env python
import collections
import extractor_util as util
import data_util as dutil
import dep_util as deps
import os
import random
import re
import sys
import config


# This defines the Row object that we read in to the extractor
parser = util.RowParser([
          ('doc_id', 'text'),
          ('section_id', 'text'),
          ('sent_id', 'int'),
          ('words', 'text[]'),
          ('lemmas', 'text[]'),
          ('poses', 'text[]'),
          ('dep_paths', 'text[]'),
          ('dep_parents', 'int[]'),
          ('genevar_mention_ids', 'text[]'),
          ('genevar_entities', 'text[]'),
          ('genevar_wordidxs', 'int[][]'),
          ('genevar_is_corrects', 'boolean[]'),
          ('pheno_mention_ids', 'text[]'),
          ('pheno_entities', 'text[]'),
          ('pheno_wordidxs', 'int[][]'),
          ('pheno_is_corrects', 'boolean[]')])


# This defines the output Relation object
Relation = collections.namedtuple('Relation', [
            'dd_id',
            'relation_id',
            'doc_id',
            'section_id',
            'sent_id',
            'genevar_mention_id',
            'genevar_entity',
            'genevar_wordidxs',
            'genevar_is_correct',
            'pheno_mention_id',
            'pheno_entity',
            'pheno_wordidxs',
            'pheno_is_correct'])

### CANDIDATE EXTRACTION ###

def extract_candidate_relations(row):
  """
  Given a row object having a sentence and some associated N gene and M phenotype mention
  candidates, pick a subset of the N*M possible gene-phenotype relations to return as
  candidate relations
  """
  HF = config.GENE_PHENO['HF']

  relations = []

  # Create a dependencies DAG for the sentence
  dep_dag = deps.DepPathDAG(row.dep_parents, row.dep_paths, row.words, max_path_len=HF['max-dep-path-dist'])

  # Create the list of possible G,P pairs with their dependency path distances
  pairs = []
  for i,gid in enumerate(row.gene_mention_ids):
    for j,pid in enumerate(row.pheno_mention_ids):

      # Do not consider overlapping mention pairs
      if len(set(row.gene_wordidxs[i]).intersection(row.pheno_wordidxs[j])) > 0:
        continue

      # Get the min path length between any of the g / p phrase words
      l = dep_dag.path_len_sets(row.gene_wordidxs[i], row.pheno_wordidxs[j])
      pairs.append([l, i, j])

  # Select which of the pairs will be considered
  pairs.sort()
  seen_g = {}
  seen_p = {}
  seen_pairs = {}
  for p in pairs:
    d, i, j = p

    # If the same entity occurs several times in a sentence, only take best one
    if HF.get('take-best-only-dups'):
      e = '%s_%s' % (row.gene_entities[i], row.pheno_entities[j])
      if e in seen_pairs and d > seen_pairs[e]:
        continue
      else:
        seen_pairs[e] = d
    
    # HACK[Alex]: may or may not be hack, needs to be tested- for now be quite restrictive
    # Only take the set of best pairs which still provides coverage of all entities
    if HF.get('take-best-only'):
      if (i in seen_g and seen_g[i] < d) or (j in seen_p and seen_p[j] < d):
        continue

    seen_g[i] = d
    seen_p[j] = d
    r = create_relation(row, i, j, dep_dag)
    relations.append(r)
  return relations


def create_relation(row, i, j, dep_dag=None):
  """
  Given a Row object with a sentence and several genevar and pheno objects, create
  a Relation output object for the ith genevar and jth pheno objects
  """
  return Relation(
    dd_id=None,
    relation_id='%s_%s' % (row.genevar_mention_ids[i], row.pheno_mention_ids[j]),
    doc_id=row.doc_id,
    section_id=row.section_id,
    sent_id=row.sent_id,
    genevar_mention_id=row.genevar_mention_ids[i],
    genevar_entity=row.genevar_entities[i],
    genevar_wordidxs=row.genevar_wordidxs[i],
    genevar_is_correct=row.genevar_is_corrects[i],
    pheno_mention_id=row.pheno_mention_ids[j],
    pheno_entity=row.pheno_entities[j],
    pheno_wordidxs=row.pheno_wordidxs[j],
    pheno_is_correct=row.pheno_is_corrects[j])

def extract_candidate_relations_simple(row):
  relations = []
  for i,gvid in enumerate(row.genevar_mention_ids):
    for j,pid in enumerate(row.pheno_mention_ids):
      if row.genevar_is_corrects[i] != False and row.pheno_is_corrects[j] != False:
        relations.append(create_relation(row, i, j))
  return relations

if __name__ == '__main__':
  for line in sys.stdin:
    row = parser.parse_tsv_row(line)
    
    # find candidate mentions
    #relations = extract_candidate_relations(row)
    relations = extract_candidate_relations_simple(row)

    # print output
    for relation in relations:
      util.print_tsv_output(relation)