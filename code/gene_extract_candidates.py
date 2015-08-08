#!/usr/bin/env python
import collections
import extractor_util as util
import data_util as dutil
import random
import re
import os
import sys
import string
import config
import dep_util as deps

CACHE = dict()  # Cache results of disk I/O


# This defines the Row object that we read in to the extractor
parser = util.RowParser([
          ('doc_id', 'text'),
          ('section_id', 'text'),
          ('sent_id', 'int'),
          ('words', 'text[]'),
          ('dep_paths', 'text[]'),
          ('dep_parents', 'int[]'),
          ('lemmas', 'text[]'),
          ('poses', 'text[]'),
          ('ners', 'text[]')])


# This defines the output Mention object
Mention = collections.namedtuple('Mention', [
            'dd_id',
            'doc_id',
            'section_id',
            'sent_id',
            'wordidxs',
            'mention_id',
            'mention_supertype',
            'mention_subtype',
            'entity',
            'words',
            'is_correct'])

### CANDIDATE EXTRACTION ###
HF = config.GENE['HF']
SR = config.GENE['SR']

def read_phrase_to_genes():
  """Read in phrase to gene mappings. The format is TSV: <EnsemblGeneId> <Phrase> <MappingType>"""
  with open('%s/onto/data/ensembl_genes.tsv' % util.APP_HOME) as f:
    phrase_to_genes = collections.defaultdict(set)
    lower_phrase_to_genes = collections.defaultdict(set)
    for line in f:
      ensembl_id,phrase,mapping_type = line.rstrip('\n').split('\t')
      if mapping_type in HF['ensembl-mapping-types']:
        phrase_to_genes[phrase].add((ensembl_id,mapping_type))
        lower_phrase_to_genes[phrase.lower()].add((ensembl_id,mapping_type))
  return phrase_to_genes, lower_phrase_to_genes


def read_pubmed_to_genes():
  """NCBI provides a list of articles (PMIDs) that discuss a particular gene (Entrez IDs).
  These provide a nice positive distant supervision set, as mentions of a gene name in
  an article about that gene are likely to be true mentions.
  
  This returns a dictionary that maps from Pubmed ID to a set of ENSEMBL genes mentioned
  in that article.
  """
  pubmed_to_genes = collections.defaultdict(set)
  with open('%s/onto/data/pmid_to_ensembl.tsv' % util.APP_HOME) as f:
    for line in f:
      pubmed,gene = line.rstrip('\n').split('\t')
      pubmed_to_genes[pubmed].add(gene)
  return pubmed_to_genes


def extract_candidate_mentions(row):
  phrase_to_genes = CACHE['phrase_to_genes']
  lower_phrase_to_genes = CACHE['lower_phrase_to_genes']
  mentions = []
  for i, word in enumerate(row.words):
    # Treat lowercase mappings the same as exact case ones for now.
    if (word in phrase_to_genes or word.lower() in lower_phrase_to_genes) and (len(word) >= HF['min-word-len']):
      exact_case_matches = phrase_to_genes[word]
      lowercase_matches = phrase_to_genes[word.lower()]
      for eid, mapping_type in exact_case_matches.union(lowercase_matches):
        m = create_supervised_mention(row, i, eid, mapping_type)
        if m:
          mentions.append(m)
  return mentions


### DISTANT SUPERVISION ###
VALS = config.GENE['vals']
def create_supervised_mention(row, i, entity=None, mention_supertype=None, mention_subtype=None):
  """Given a Row object consisting of a sentence, create & supervise a Mention output object"""
  word = row.words[i]
  word_lower = word.lower()
  mid = '%s_%s_%s_%s_%s_%s' % (row.doc_id, row.section_id, row.sent_id, i, entity, mention_supertype)
  m = Mention(None, row.doc_id, row.section_id, row.sent_id, [i], mid, mention_supertype, mention_subtype, entity, [word], None)
  dep_dag = deps.DepPathDAG(row.dep_parents, row.dep_paths, row.words)

  if SR.get('post-match'):
    opts = SR['post-match']
    phrase_post = " ".join(row.words[i+1:])
    for name,val in VALS:
      if len(opts[name]) + len(opts['%s-rgx' % name]) > 0:
        match = util.rgx_mult_search(phrase_post, opts[name], opts['%s-rgx' % name], flags=re.I)
        if match:
          return m._replace(is_correct=val, mention_supertype='POST_MATCH_%s_%s' % (name, val), mention_subtype=match)

  if SR.get('pre-neighbor-match') and i > 0:
    opts = SR['pre-neighbor-match']
    pre_neighbor = row.words[i-1]
    for name,val in VALS:
      if len(opts[name]) + len(opts['%s-rgx' % name]) > 0:
        match = util.rgx_mult_search(pre_neighbor, opts[name], opts['%s-rgx' % name], flags=re.I)
        if match:
          return m._replace(is_correct=val, mention_supertype='PRE_NEIGHBOR_MATCH_%s_%s' % (name, val), mention_subtype=match)

  ## DS RULE: matches from papers that NCBI annotates as being about the mentioned gene are likely true.
  if SR['pubmed-paper-genes-true']:
    pubmed_to_genes = CACHE['pubmed_to_genes']
    pmid = dutil.get_pubmed_id_for_doc(row.doc_id)
    if pmid and entity:
      mention_ensembl_id = entity.split(":")[0]
      if mention_ensembl_id in pubmed_to_genes.get(pmid, {}):
        return m._replace(is_correct=True, mention_supertype='%s_NCBI_ANNOTATION_TRUE' % mention_supertype, mention_subtype=mention_ensembl_id)

  if SR['all-canonical-true']:
    if m.mention_supertype in ('CANONICAL_SYMBOL','NONCANONICAL_SYMBOL'):
      return m._replace(is_correct=True, mention_supertype='CANONICAL_TRUE')

  ## DS RULE: Genes on the gene list with complicated names are probably good for exact matches.
  if SR['complicated-gene-names-true']:
    if m.mention_supertype in ('CANONICAL_SYMBOL','NONCANONICAL_SYMBOL'):
      if re.match(r'[a-zA-Z]{3}[a-zA-Z]*\d+\w*', word):
        return m._replace(is_correct=True, mention_supertype='COMPLICATED_GENE_NAME')

  if SR.get('neighbor-match'):
    opts = SR['neighbor-match']
    for name,val in VALS:
      if len(opts[name]) + len(opts['%s-rgx' % name]) > 0:
        for neighbor_idx in dep_dag.neighbors(i):
          neighbor = row.words[neighbor_idx]
          match = util.rgx_mult_search(neighbor, opts[name],  opts['%s-rgx' % name], flags=re.I)
          if match:
            return m._replace(is_correct=val, mention_supertype='NEIGHBOR_MATCH_%s_%s' % (name, val), mention_subtype='Neighbor: ' + neighbor + ', match: ' + match)

  return m

def get_negative_mentions(row, mentions, d, per_row_max=2):
  """Generate random / pseudo-random negative examples, trying to keep set approx. balanced"""
  negs = []
  if d < 0:
    return negs
  existing_mention_idxs = [m.wordidxs[0] for m in mentions]
  for i, word in enumerate(row.words):
    if len(negs) > d or len(negs) > per_row_max:
      return negs

    # skip if an existing mention
    if i in existing_mention_idxs:
      continue
    
    # Make a template mention object- will have mention_id opt with entity (ensemble_id) appended
    mid = '%s_%s_%s_%s' % (row.doc_id, row.section_id, row.sent_id, i)
    m = Mention(dd_id=None, doc_id=row.doc_id, section_id=row.section_id, sent_id=row.sent_id, wordidxs=[i], mention_id=mid, mention_supertype="RANDOM_NEGATIVE",mention_subtype=None, entity=None, words=[word], is_correct=None)

    # Non-match all uppercase negative supervision
    if word==word.upper() and len(word)>2 and word.isalnum() and not unicode(word).isnumeric():
      if random.random() < 0.01*d:
        negs.append(m._replace(mention_supertype='ALL_UPPER_NOT_GENE_SYMBOL', is_correct=False))

    # Random negative supervision
    elif random.random() < 0.005*d:
      negs.append(m._replace(mention_supertype='RAND_WORD_NOT_GENE_SYMBOL', is_correct=False))
  return negs


if __name__ == '__main__':
  # load static data
  CACHE['phrase_to_genes'],CACHE['lower_phrase_to_genes'] = read_phrase_to_genes()
  CACHE['pubmed_to_genes'] = read_pubmed_to_genes()
  # unnecessary currently b/c our doc id is the pmid, thankfully
  # CACHE['doi_to_pmid'] = dutil.read_doi_to_pmid()
  
  # generate the mentions, while trying to keep the supervision approx. balanced
  # print out right away so we don't bloat memory...
  pos_count = 0
  neg_count = 0
  for line in sys.stdin:
    row = parser.parse_tsv_row(line)

    # Skip row if sentence doesn't contain a verb, contains URL, etc.
    if util.skip_row(row):
      continue

    # Find candidate mentions & supervise
    try:
      mentions = extract_candidate_mentions(row)
    except IndexError:
      util.print_error("Error with row: %s" % (row,))
      continue

    pos_count += len([m for m in mentions if m.is_correct])
    neg_count += len([m for m in mentions if m.is_correct is False])

    # add negative supervision
    if pos_count > neg_count and SR['rand-negs']:
      negs = get_negative_mentions(row, mentions, pos_count - neg_count)
      neg_count += len(negs)
      mentions += negs

    # print output
    for mention in mentions:
      util.print_tsv_output(mention)
