#!/bin/env bash

set -eux

TMP1=$(mktemp)
TMP2=$(mktemp)
TMPD=$(mktemp -d)

for SCT in UK/Data/Sector/*.sct ; do
	BAS=$(basename "$SCT")

	OFS=$(grep -nF "[LABELS]" "$SCT" | cut -d: -f1)
	tail -n +$OFS "$SCT" | tail -n +2 > $TMP1

	LEN=$(grep -nE "^\[.+\]$" $TMP1 | cut -d: -f1)
	head -n $LEN $TMP1 | grep -oE '^".+"\s' | cut -d\" -f2 | LC_ALL=C sort -fu > $TMP2

	LEN=$(wc -l < $TMP2)
	yes "Free Text:SCT2" | head -n $LEN | paste -d\\\\ - $TMP2 > $TMP1
	yes "freetext" | head -n $LEN | paste -d: $TMP1 - > "$TMPD/$BAS"
done

grep -lrF "SMR radar display" --include=*.asr | while read -r ASR ; do
	ASD=${ASR#*/}
	PRF=$(grep -lrF "${ASD//\//\\}" --include=*.prf | head -n1)
	SCT=$(grep -E "Settings\s+sector" "$PRF" | cut -f3)
	SCT=${SCT##*\\}

	grep -vF "Free Text:SCT2\\" "$ASR" > $TMP1
	OFS=$(grep -m1 -nF "Free Text:SCT2\\" "$ASR" | cut -d: -f1)

	head -n $OFS $TMP1 | head -n -1 > "$ASR"
	cat "$TMPD/$SCT" >> "$ASR"
	tail -n +$OFS $TMP1 >> "$ASR"
done

rm $TMP1 $TMP2
rm -r $TMPD
