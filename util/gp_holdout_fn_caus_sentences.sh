#!/bin/bash -e
set -beEu -o pipefail

if [ $# -ne 1 ]; then
	echo "$0: ERROR: wrong number of arguments" >&2
	echo "$0: USAGE: $0 DB" >&2
	exit 1
fi

DB=$1

TMPDIR=$(mktemp -d /tmp/dft.XXXXXX)
SQL_COMMAND_FILE=${TMPDIR}/dft.sql
cat <<EOF >> ${SQL_COMMAND_FILE}
COPY (
SELECT DISTINCT
  l.labeler CAUSATION_FALSE_NEGATIVES,
  s.doc_id,
  s.section_id,
  s.sent_id,
  gc.expectation,
  gc.gene_name,
  gc.gene_wordidxs,
  gc.pheno_wordidxs,
  (string_to_array(si.words, '|^|'))[(gc.pheno_wordidxs)[1] + 1] first_pheno,
  array_to_string(string_to_array(si.words, '|^|'), ' ') words,
  array_to_string(string_to_array(si.lemmas, '|^|'), ' ') lemmas
FROM
  genepheno_causation_is_correct_inference gc 
  RIGHT JOIN genepheno_holdout_labels_caus l
    ON (l.doc_id = gc.doc_id AND l.section_id = gc.section_id AND l.sent_id = gc.sent_id AND gc.gene_wordidxs = l.gene_wordidxs AND gc.pheno_wordidxs = l.pheno_wordidxs) 
  JOIN sentences_input si
    ON (si.doc_id = l.doc_id AND si.section_id = l.section_id AND si.sent_id = l.sent_id)
WHERE
  COALESCE(gc.expectation, 0) <= 0.9 
  AND l.is_correct = 't')
TO STDOUT;
EOF
psql -q -X --set ON_ERROR_STOP=1 -d $DB -f ${SQL_COMMAND_FILE} > /dev/stderr
rm -rf ${TMPDIR}

