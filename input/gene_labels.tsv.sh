#! /usr/bin/env bash

psql -U $DDUSER -p 6432 -d genomics_labels -c "COPY (SELECT * FROM gene_labels) TO STDOUT WITH NULL AS ''"