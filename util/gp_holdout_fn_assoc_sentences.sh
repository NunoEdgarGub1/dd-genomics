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
  l.labeler ASSOCIATION_FALSE_NEGATIVES,
  si.doc_id,
  si.section_id,
  si.sent_id,
  gc.expectation,
  gc.gene_name,
  gc.gene_wordidxs,
  gc.pheno_wordidxs,
  (string_to_array(si.words, '|^|'))[(gc.pheno_wordidxs)[1] + 1] first_pheno,
  array_to_string(string_to_array(si.words, '|^|'), ' ') words,
  array_to_string(string_to_array(si.lemmas, '|^|'), ' ') lemmas
FROM
  genepheno_association_is_correct_inference gc 
  RIGHT JOIN genepheno_association_labels l
    ON (l.relation_id = gc.relation_id)
  JOIN sentences_input si
    ON (si.doc_id = gc.doc_id AND si.section_id = gc.section_id AND si.sent_id = gc.sent_id)
WHERE
  COALESCE(gc.expectation, 0) <= 0.9 
  AND l.is_correct = 't')
TO STDOUT;
EOF
psql -q -X --set ON_ERROR_STOP=1 -d $DB -f ${SQL_COMMAND_FILE} > /dev/stderr
rm -rf ${TMPDIR}

