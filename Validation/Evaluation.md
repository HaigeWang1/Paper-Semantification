Result Evaluation
The matching precision is calculated via:
`Exact matching of titles & author names in the volume/all paper in the volume`, the first line of the evaluation output

Precision 100% -> n out n matching:
[2450, 3108, 2455]

Few mismatched cases, precision >= 90%:
[2452, 2451, 2344, 2650, 3582, 2000, 2003, 2002,2453, 3037, 3498, 3576,2456]

The reasons are: 
	special characters in either the result df or the test set.
	unexpected punctuation marks in author name, e.g. vol2002 “Dongxu Zhang?” 	Vs. 	“Dongxu Zhang“ in test set; vol3498: “Jirí”, vol 3576 “Andrés Felipe Soler” vs. “Andres Soler” in test set
	Empty author information in result e.g. 2453, 3037


Rest volumes:
Vol 3581:  7 out of 32 (precision = 21%). Combination of all the reasons described above.
Vol 3601: There exist no Grobid nor Cermine webpages for this volume. Therefore 0%. Edge case!
Vol 2960: 0% Each paper title in the result contains a suffix (long paper/short paper), which is not present in the test set, therefore 0%. We can consider this volume as precision >= 90%, if we ignore the suffix.

