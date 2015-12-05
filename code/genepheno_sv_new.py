#! /usr/bin/env python

import collections
from util import extractor_util as eutil
from util import data_util as dutil
import re
import sys
from util import latticelib
import config

# This defines the Row object that we read in to the extractor
parser = eutil.RowParser([
            ('relation_id', 'text'),
            ('doc_id', 'text'),
            ('section_id', 'text'),
            ('sent_id', 'int'),
            ('gene_mention_id', 'text'),
            ('gene_name', 'text'),
            ('gene_wordidxs', 'int[]'),
            ('gene_is_correct', 'boolean'),
            ('pheno_mention_id', 'text'),
            ('pheno_entity', 'text'),
            ('pheno_wordidxs', 'int[]'),
            ('pheno_is_correct', 'boolean'),
            ('words', 'text[]'),
            ('lemmas', 'text[]'),
            ('poses', 'text[]'),
            ('dep_paths', 'text[]'),
            ('dep_parents', 'int[]'),
            ('ners', 'text')])

# This defines the output Relation object
Relation = collections.namedtuple('Relation', [
            'dd_id',
            'relation_id',
            'doc_id',
            'section_id',
            'sent_id',
            'gene_mention_id',
            'gene_name',
            'gene_wordidxs',
            'pheno_mention_id',
            'pheno_entity',
            'pheno_wordidxs',
            'is_correct',
            'relation_supertype',
            'relation_subtype'])

HPO_DAG = dutil.read_hpo_dag()

def replace_opts(opts, replaceList):
  ret = {}
  for name in opts:
    strings = opts[name]
    for (pattern, subst) in replaceList:
      if name.endswith('rgx'):
        subst = re.escape(subst)
      strings = [s.replace(pattern, subst) for s in strings]
    ret[name] = strings
  return ret

def read_supervision():
  """Reads genepheno supervision data (from charite)."""
  supervision_pairs = set()
  with open('%s/onto/data/canon_phenotype_to_gene.map' % eutil.APP_HOME) as f:
    for line in f:
      hpo_id, gene_name = line.strip().split('\t')
      hpo_ids = [hpo_id] + [parent for parent in HPO_DAG.edges[hpo_id]]
      for h in hpo_ids:
        supervision_pairs.add((h, gene_name))
  return supervision_pairs

# count_g_or_p_false_none = 0
# count_adjacent_false_none = 0

non_alnum = re.compile('[\W_]+')

def supervise(supervision_rules, hard_filters):
  # generate the mentions, while trying to keep the supervision approx. balanced
  # print out right away so we don't bloat memory...
  pos_count = 0
  neg_count = 0
  # load in static data
  CHARITE_PAIRS = read_supervision()
  for line in sys.stdin:
    row = parser.parse_tsv_row(line)

    relation = create_supervised_relation(row, superv_diff=pos_count - neg_count, SR=supervision_rules, HF=hard_filters, charite_pairs=CHARITE_PAIRS)

    if relation:
      if relation.is_correct == True:
        pos_count += 1
      elif relation.is_correct == False:
        neg_count += 1
      eutil.print_tsv_output(relation)
  # sys.stderr.write('count_g_or_p_false_none: %s\n' % count_g_or_p_false_none)
  # sys.stderr.write('count_adjacent_false_none: %s\n' % count_adjacent_false_none)

genepheno_dicts = {
    'mutation' : ['mutation', 'allele', 'variant'],
    'serum' : ['serum', 'level', 'elevated', 'plasma'],
}

pos_patterns = {
    '[rel[1]] -nsubjpass-> cause -nmod-> mutation -nmod-> [rel[0]]',
}

neg_patterns = {
    'possible _ association',
}

strong_pos_patterns = {
    '[rel[1]] -nsubjpass-> cause -nmod-> mutation -nmod-> [rel[0]]',
}

strong_neg_patterns = {
    'possible _ association',
}

def read_candidate(sentence_index, sentence, row, config):
  gene_mention_id = row.gene_mention_id
  gene_name = row.gene_name
  gene_wordidxs = row.gene_wordidxs
  pheno_mention_id = row.pheno_mention_id
  pheno_entity = row.pheno_entity
  pheno_wordidxs = row.pheno_wordidxs

  relation_id = '%s_%s' % (gene_mention_id, pheno_mention_id)
  r = Relation(None, relation_id, row.doc_id, row.section_id, row.sent_id, gene_mention_id, gene_name, \
               gene_wordidxs, pheno_mention_id, pheno_entity, pheno_wordidxs, None, None, None)
  return r

if __name__ == '__main__':
  supervision_rules = config.GENE_PHENO_ASSOCIATION['SR']
  hard_filters = config.GENE_PHENO_ASSOCIATION['HF']

  # Configure the extractor
  config = latticelib.Config()

  config.add_dicts(genepheno_dicts)
  config.set_pos_patterns(pos_patterns)
  config.set_neg_patterns(neg_patterns)
  config.set_strong_pos_patterns(strong_pos_patterns)
  config.set_strong_neg_patterns(strong_neg_patterns)
  config.set_candidate_generator(read_candidate)
  config.set_pos_supervision_phrases([])
  config.set_neg_supervision_phrases([])
  # config.set_feature_patterns(feature_patterns)
  # config.add_featurizer(ddlib_featurizer)
  config.NGRAM_WILDCARD = False
  config.PRINT_SUPV_RULE = True

  config.run(parser, [7,10])
