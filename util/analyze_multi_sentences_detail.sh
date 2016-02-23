#!/bin/bash -e
set -beEu -o pipefail

echo "CREATE HOLDOUT PATCH!"


GP_CUTOFF=`cat ../results_log/gp_cutoff`

cd ..
source env_local.sh

deepdive sql """
COPY (
SELECT DISTINCT
  gc.relation_id
FROM
  genepheno_causation_is_correct_inference gc 
WHERE
  gc.expectation > $GP_CUTOFF
ORDER BY random()
LIMIT 50
) TO STDOUT;
""" | while read rid
do
echo "RELATION ID"
echo $rid
echo "BASE INFO"
deepdive sql """
COPY (
SELECT DISTINCT
  s.labeler CAUSATION_FALSE_POSITIVES,
  si.doc_id,
  si.section_id,
  si.sent_id,
  gc.gene_name,
  gc.gene_wordidxs,
  gc.pheno_wordidxs,
  (string_to_array(si.words, '|^|'))[(gc.pheno_wordidxs)[1] + 1] first_pheno,
  array_to_string(string_to_array(si.words, '|^|'), ' ') words,
FROM
  genepheno_causation_is_correct_inference gc
  JOIN sentences_input si
    ON (si.doc_id = gc.doc_id AND si.section_id = gc.section_id AND si.sent_id = gc.sent_id)
WHERE
  gc.relation_id = '$rid') TO STDOUT;
""" | sed 's/-LRB- /(/g' | sed 's/ -RRB-/)/g'
echo "DISTANT SUPERVISION"
deepdive sql """
COPY (
SELECT DISTINCT
  gc.supertype, gc.subtype
FROM
  genepheno_causation gc
WHERE
  gc.relation_id = '$rid') TO STDOUT
""" 
echo """sentence NER:"""
cat <(deepdive sql """
COPY (
  SELECT ARRAY_TO_STRING(STRING_TO_ARRAY(words, '|^|'), ' ') FROM sentences_input_ner si join genepheno_causation gc on (si.doc_id = gc.doc_id and si.section_id = gc.section_id and si.sent_id = gc.sent_id) WHERE relation_id = '$rid'
) TO STDOUT
""") \
  <(deepdive sql """
COPY (
  SELECT ARRAY_TO_STRING(STRING_TO_ARRAY(ners, '|^|'), ' ') FROM sentences_input_ner si join genepheno_causation gc on (si.doc_id = gc.doc_id and si.section_id = gc.section_id and si.sent_id = gc.sent_id) WHERE relation_id = '$rid'
) TO STDOUT
""") | column -t
echo "IDENTIFIED GENES IN SENTENCE:"
deepdive sql """
COPY (
  SELECT DISTINCT
    gp2.gene_name, gp2.gene_wordidxs[1]
  FROM
    genepheno_causation gp1
    JOIN genepheno_causation gp2
      on (gp1.doc_id = gp2.doc_id and gp1.section_id = gp2.section_id and gp1.sent_id = gp2.sent_id)
  WHERE
    gp1.relation_id = '$rid'
  ORDER BY gp2.gene_wordidxs[1]
) TO STDOUT
"""
echo "IDENTIFIED PHENOS IN SENTENCE:"
deepdive sql """
COPY (
  SELECT DISTINCT
    gp2.pheno_entity, (STRING_TO_ARRAY(si.words, '|^|'))[gp2.pheno_wordidxs[1]+1], gp2.pheno_wordidxs, (STRING_TO_ARRAY(n.names, '|^|'))[1]
  FROM
    genepheno_causation gp1
    JOIN genepheno_causation gp2
      on (gp1.doc_id = gp2.doc_id and gp1.section_id = gp2.section_id and gp1.sent_id = gp2.sent_id)
    JOIN sentences_input si
      on (gp1.doc_id = si.doc_id and gp1.section_id = si.section_id and gp1.sent_id = si.sent_id)
    JOIN pheno_names n
      on (n.id = gp2.pheno_entity)
  WHERE
    gp1.relation_id = '$rid'
  ORDER BY gp2.pheno_wordidxs[1]
) TO STDOUT
"""
echo """OTHER GENEPHENOS IN SENTENCE:"""
deepdive sql """
COPY (
SELECT DISTINCT
  gp2.gene_wordidxs[1],
  (STRING_TO_ARRAY(si.words, '|^|'))[gp2.gene_wordidxs[1]+1],
  gp2.pheno_wordidxs[1],
  (STRING_TO_ARRAY(si.words, '|^|'))[gp2.pheno_wordidxs[1]+1],
  (STRING_TO_ARRAY(n.names, '|^|'))[1],
  expectation
FROM
  genepheno_causation gp1
  JOIN genepheno_causation gp2
    on (gp1.doc_id = gp2.doc_id and gp1.section_id = gp2.section_id and gp1.sent_id = gp2.sent_id)
  JOIN pheno_names n
    on (gp2.pheno_entity = n.id)
  JOIN sentences_input si
    on (si.doc_id = gp1.doc_id and si.section_id = gp1.section_id and si.sent_id = gp1.sent_id)
  JOIN genepheno_causation_inference_label_inference i
    on (gp2.relation_id = i.relation_id)
WHERE
  gp1.relation_id = '$rid'
  AND expectation > $GP_CUTOFF
ORDER BY
  gp2.gene_wordidxs[1],
  gp2.pheno_wordidxs[1]
) TO STDOUT
"""
echo "FEATURES"
deepdive sql """
select distinct
  feature,
  w.weight
from 
  genepheno_relations r 
  join genepheno_features f 
    on (f.relation_id = r.relation_id) 
  join dd_inference_result_weights_mapping w 
    on (w.description = ('inf_istrue_genepheno_causation_inference--' || f.feature)) 
where 
  r.relation_id = '$rid'
order by abs(weight) desc
LIMIT 22;
"""
echo

done
