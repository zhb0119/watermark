# LoCoMo RQ Metrics Summary

- **File**: `results\dp_v4_flash\conv0_metrics_no_watermark.json`
- **Cell value**: numeric values are from this JSON file; empty means baseline has no metric.

## RQ1 Utility

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | bits_embedded |  | 0 |  |  |
|  | capacity_bits_per_decision |  | 0 |  |  |
|  | memory_count |  | 419 |  |  |
|  | qa_accuracy |  | 0.3668 |  |  |
|  | qa_bleu1 |  | 0.4021 |  |  |
|  | qa_count |  | 199 |  |  |
|  | qa_f1 |  | 0.3576 |  |  |
|  | qa_rougeL |  | 0.3477 |  |  |
|  | write_failures |  | 3 |  |  |


### qa_by_category
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| category=1 | bleu1 |  | 0.3342 |  |  |
| category=1 | f1 |  | 0.2642 |  |  |
| category=1 | judge_acc |  | 0.3125 |  |  |
| category=1 | n |  | 32 |  |  |
| category=1 | rougeL |  | 0.2540 |  |  |
| category=2 | bleu1 |  | 0.3447 |  |  |
| category=2 | f1 |  | 0.2732 |  |  |
| category=2 | judge_acc |  | 0.3243 |  |  |
| category=2 | n |  | 37 |  |  |
| category=2 | rougeL |  | 0.3041 |  |  |
| category=3 | bleu1 |  | 0.6090 |  |  |
| category=3 | f1 |  | 0.4018 |  |  |
| category=3 | judge_acc |  | 0.3846 |  |  |
| category=3 | n |  | 13 |  |  |
| category=3 | rougeL |  | 0.2364 |  |  |
| category=4 | bleu1 |  | 0.5026 |  |  |
| category=4 | f1 |  | 0.4666 |  |  |
| category=4 | judge_acc |  | 0.4571 |  |  |
| category=4 | n |  | 70 |  |  |
| category=4 | rougeL |  | 0.4632 |  |  |
| category=5 | bleu1 |  | 0.2865 |  |  |
| category=5 | f1 |  | 0.3132 |  |  |
| category=5 | judge_acc |  | 0.2979 |  |  |
| category=5 | n |  | 47 |  |  |
| category=5 | rougeL |  | 0.3046 |  |  |

## RQ2 Capacity

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | acceptance_rate |  | 1 |  |  |
|  | avg_candidate_set_size |  | 2.9988 |  |  |
|  | avg_entropy |  | 1.0736 |  |  |
|  | bits_embedded |  | 0 |  |  |
|  | bits_per_decision |  | 0 |  |  |
|  | decisions |  | 838 |  |  |


### by_carrier
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | acceptance_rate |  | 1 |  |  |
| carrier=link_target | avg_candidate_set_size |  | 3.0049 |  |  |
| carrier=link_target | avg_entropy |  | 1.1139 |  |  |
| carrier=link_target | bits_embedded |  | 0 |  |  |
| carrier=link_target | bits_per_decision |  | 0 |  |  |
| carrier=link_target | decisions |  | 204 |  |  |
| carrier=semantic_realization | acceptance_rate |  | 1 |  |  |
| carrier=semantic_realization | avg_candidate_set_size |  | 2.9954 |  |  |
| carrier=semantic_realization | avg_entropy |  | 1.0373 |  |  |
| carrier=semantic_realization | bits_embedded |  | 0 |  |  |
| carrier=semantic_realization | bits_per_decision |  | 0 |  |  |
| carrier=semantic_realization | decisions |  | 433 |  |  |
| carrier=update_target | acceptance_rate |  | 1 |  |  |
| carrier=update_target | avg_candidate_set_size |  | 3 |  |  |
| carrier=update_target | avg_entropy |  | 1.1111 |  |  |
| carrier=update_target | bits_embedded |  | 0 |  |  |
| carrier=update_target | bits_per_decision |  | 0 |  |  |
| carrier=update_target | decisions |  | 201 |  |  |

## RQ5 Integrity

### by_carrier_counts
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | count |  | 204 |  |  |
| carrier=semantic_realization | count |  | 433 |  |  |
| carrier=update_target | count |  | 201 |  |  |


### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | contradiction_rate |  | 0 |  |  |
|  | duplicate_count |  | 0 |  |  |
|  | duplication_rate |  | 0 |  |  |
|  | evidence_recall_mean |  | 0.6142 |  |  |
|  | evidence_required_qas |  | 197 |  |  |
|  | link_target_total |  | 204 |  |  |
|  | overall_records |  | 419 |  |  |
|  | qa_with_full_evidence |  | 110 |  |  |
|  | update_target_accuracy |  | 1 |  |  |
|  | update_target_correct |  | 201 |  |  |
|  | update_target_total |  | 201 |  |  |
