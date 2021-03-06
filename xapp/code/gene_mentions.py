import ddext
from ddext import SD


def init():
  ddext.input('doc_id', 'text')
  ddext.input('sent_id', 'int')
  ddext.input('words', 'text[]')
  ddext.input('lemmas', 'text[]')
  ddext.input('poses', 'text[]')
  ddext.input('ners', 'text[]')

  ddext.returns('doc_id', 'text')
  ddext.returns('sent_id', 'int')
  ddext.returns('wordidxs', 'int[]')
  ddext.returns('mention_id', 'text')
  ddext.returns('type', 'text')
  ddext.returns('entity', 'text')
  ddext.returns('words', 'text[]')
  ddext.returns('is_correct', 'boolean')


def run(doc_id, sent_id, words, lemmas, poses, ners):

  # TODO: currently we match only gene symbols and not phrases; consider matching phrases.

  if 'genes' in SD:
    genes = SD['genes']
  else:
    import os
    APP_HOME = os.environ['GDD_HOME']
    all_names = set()
    dup_names = set()
    all_synonyms = {}
    dup_synonyms = set()
    en_words = set([x.strip().lower() for x in open('%s/onto/dicts/english_words.tsv' % APP_HOME)])
    gene_english = set([x.strip().lower() for x in open('%s/onto/manual/gene_english.tsv' % APP_HOME)])
    gene_bigrams = set([x.strip().lower() for x in open('%s/onto/manual/gene_bigrams.tsv' % APP_HOME)])
    gene_noisy = set([x.strip().lower() for x in open('%s/onto/manual/gene_noisy.tsv' % APP_HOME)])
    gene_exclude = set([x.strip().lower() for x in open('%s/onto/manual/gene_exclude.tsv' % APP_HOME)])
    SD['english'] = en_words
    for line in open('%s/onto/data/genes.tsv' % APP_HOME):
      #plpy.info(line)
      name, synonyms, full_names = line.strip(' \r\n').split('\t')
      synonyms = set(x.strip() for x in synonyms.split('|'))
      synonyms.discard(name)
      synonyms.discard('')
      full_names = set(x.strip() for x in full_names.split('|'))
      if name in all_names:
        dup_names.add(name)
      else:
        all_names.add(name)
      for s in synonyms:
        if s in all_synonyms:
          # we assign the synonym to the first name
          dup_synonyms.add(s)
        else:
          all_synonyms[s] = name
    plpy.info('===== DUPLICATE GENE NAMES')
    plpy.info('\n'.join(sorted(dup_names)))
    plpy.info('===== DUPLICATE GENE SYNONYMS')
    plpy.info(sorted(dup_synonyms))
    all_names -= gene_exclude
    all_synonyms = {s: n for s, n in all_synonyms.iteritems() if s not in all_names and s not in gene_exclude}
    genes = {
      'names': all_names,
      'synonyms': all_synonyms,
      'names_lower': {x.lower(): x for x in all_names},
      'synonyms_lower': {x.lower(): y for x, y in all_synonyms.iteritems()},
      'exact_lower': set(x.lower() for x in gene_english | gene_bigrams | gene_noisy),
    }
    SD['genes'] = genes

  for i in xrange(len(words)):
    word = words[i]

    if len(word) == 1:
      continue

    iword = word.lower()

    match_type = None
    if word in genes['names']:
      match_type = 'NAME'
      entity = word
    elif word in genes['synonyms']:
      match_type = 'SYN'
      entity = genes['synonyms'][word]
    else:
      if iword in genes['exact_lower']:
        continue
      elif iword in genes['names_lower']:
        match_type = 'iNAME'
        entity = genes['names_lower'][iword]
      elif iword in genes['synonyms_lower']:
        match_type = 'iSYN'
        entity = genes['synonyms_lower'][iword]
      else:
        continue

    truth = True

    # a two-letter capital word
    if len(word) == 2 and word.isupper() and word.isalpha():
      has_pub_date = 'DATE' in ners and 'NUMBER' in ners
      # is or right next to a person/organization word
      for j in xrange(max(0, i - 1), min(i + 2, len(words))):
        if has_pub_date and ners[j] in ('PERSON', 'ORGANIZATION'):
          truth = False
          break
      else:
        truth = None

    mid = '%s_%s_%d_1' % (doc_id, sent_id, i)
    yield doc_id, sent_id, [i], mid, match_type, entity, [word], truth
