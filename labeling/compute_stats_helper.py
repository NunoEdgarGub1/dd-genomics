#! /usr/bin/env python

import sys

if len(sys.argv) != 4:
    print 'Wrong number of arguments'
    print 'USAGE: ./compute_stats_helper.py $label_tsvfile $prediction_tsvfile $confidence'
    exit(1)

label_filename = sys.argv[1]
pred_filename = sys.argv[2]
confidence = float(sys.argv[3])

# read label filename 
labels = {}
with open(label_filename) as f:
    for i, line in enumerate(f):
        line = line.split('\t')
        relationid = line[0].lower().strip()
        is_correct = line[1].lower().strip()
        if is_correct == 't':
            labels[relationid] = True
        elif is_correct == 'f':
            labels[relationid] = False

# read predictions 
predictions = {}
with open(pred_filename) as f:
    for i, line in enumerate(f):
        line = line.split('\t')
        relationid = line[0].lower().strip()
        expectation = float(line[1].strip())
        predictions[relationid] = (expectation >= confidence)

# Evaluate number of true positives

true_positives = 0
true_negatives = 0
false_positives = 0
false_negatives = 0

# Also store the FP and FNs:
fps = []
fns = []

for label_id in labels:
    # if the labeled mention is in the prediction set
    if label_id in predictions:
        if labels[label_id] and predictions[label_id]:
            true_positives += 1
        elif (not labels[label_id]) and predictions[label_id]:
            false_positives += 1
            fps.append(label_id)
        elif labels[label_id] and not predictions[label_id]:
            false_negatives += 1
            fns.append(label_id)
        else:
            true_negatives += 1
    # if the labeled mention is not in the prediction set (was ruled out)
    else:
        if labels[label_id]:
            # was true but rejected
            false_negatives += 1
        else:
            true_negatives += 1 

# Print these
print 'True positives:\t'+str(true_positives)
print 'True negatives:\t'+str(true_negatives)
print 'False positives:\t'+str(false_positives)
print 'False negatives:\t'+str(false_negatives)
print '\n\n\n'

# compute precision, recall and F1
precision = float(true_positives)/float(true_positives+false_positives)
recall = float(true_positives)/float(true_positives+false_negatives)
F1_score = 2*precision*recall / (precision+recall)

print 'Precision:\t'+str(precision)
print 'Recall:\t'+str(recall)
print 'F1 score:\t'+str(F1_score)

print 'False Positives:'
for id in fps:
  print id
print '\n'
print 'False Negatives:'
for id in fns:
  print id