#! /bin/bash -e

if [ -z "$DDUSER" ]
then
  echo "set dduser!" > /dev/stderr
  exit 1
fi

psql -U $DDUSER -p 6432 -d genomics_labels -c "COPY (SELECT * FROM gene_labels) TO STDOUT WITH NULL AS ''"
