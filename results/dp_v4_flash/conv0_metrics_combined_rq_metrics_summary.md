# LoCoMo RQ Metrics Summary

- **File**: `results\dp_v4_flash\conv0_metrics_watermark.json`, `results\dp_v4_flash\conv0_metrics_no_watermark.json`
- **Cell value**: numeric values are from this JSON file; empty means baseline has no metric.

## RQ1 Utility

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | bits_embedded | 40 | 0 |  |  |
|  | capacity_bits_per_decision | 0.0478 | 0 |  |  |
|  | memory_count | 418 | 419 |  |  |
|  | qa_accuracy | 0.3166 | 0.3668 |  |  |
|  | qa_bleu1 | 0.3795 | 0.4021 |  |  |
|  | qa_count | 199 | 199 |  |  |
|  | qa_f1 | 0.3338 | 0.3576 |  |  |
|  | qa_rougeL | 0.3226 | 0.3477 |  |  |
|  | write_failures | 4 | 3 |  |  |


### qa_by_category
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| category=1 | bleu1 | 0.3646 | 0.3342 |  |  |
| category=1 | f1 | 0.2484 | 0.2642 |  |  |
| category=1 | judge_acc | 0.2812 | 0.3125 |  |  |
| category=1 | n | 32 | 32 |  |  |
| category=1 | rougeL | 0.2525 | 0.2540 |  |  |
| category=2 | bleu1 | 0.3524 | 0.3447 |  |  |
| category=2 | f1 | 0.2775 | 0.2732 |  |  |
| category=2 | judge_acc | 0.2973 | 0.3243 |  |  |
| category=2 | n | 37 | 37 |  |  |
| category=2 | rougeL | 0.3078 | 0.3041 |  |  |
| category=3 | bleu1 | 0.5337 | 0.6090 |  |  |
| category=3 | f1 | 0.3738 | 0.4018 |  |  |
| category=3 | judge_acc | 0.3846 | 0.3846 |  |  |
| category=3 | n | 13 | 13 |  |  |
| category=3 | rougeL | 0.2710 | 0.2364 |  |  |
| category=4 | bleu1 | 0.4448 | 0.5026 |  |  |
| category=4 | f1 | 0.4240 | 0.4666 |  |  |
| category=4 | judge_acc | 0.3857 | 0.4571 |  |  |
| category=4 | n | 70 | 70 |  |  |
| category=4 | rougeL | 0.3993 | 0.4632 |  |  |
| category=5 | bleu1 | 0.2710 | 0.2865 |  |  |
| category=5 | f1 | 0.2908 | 0.3132 |  |  |
| category=5 | judge_acc | 0.2340 | 0.2979 |  |  |
| category=5 | n | 47 | 47 |  |  |
| category=5 | rougeL | 0.2819 | 0.3046 |  |  |

## RQ2 Capacity

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | acceptance_rate | 1 | 1 |  |  |
|  | avg_candidate_set_size | 2.9964 | 2.9988 |  |  |
|  | avg_entropy | 1.0713 | 1.0736 |  |  |
|  | bits_embedded | 40 | 0 |  |  |
|  | bits_per_decision | 0.0478 | 0 |  |  |
|  | decisions | 837 | 838 |  |  |


### by_carrier
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | acceptance_rate | 1 | 1 |  |  |
| carrier=link_target | avg_candidate_set_size | 3 | 3.0049 |  |  |
| carrier=link_target | avg_entropy | 1.1179 | 1.1139 |  |  |
| carrier=link_target | bits_embedded | 13 | 0 |  |  |
| carrier=link_target | bits_per_decision | 0.0535 | 0 |  |  |
| carrier=link_target | decisions | 243 | 204 |  |  |
| carrier=semantic_realization | acceptance_rate | 1 | 1 |  |  |
| carrier=semantic_realization | avg_candidate_set_size | 2.9953 | 2.9954 |  |  |
| carrier=semantic_realization | avg_entropy | 1.0423 | 1.0373 |  |  |
| carrier=semantic_realization | bits_embedded | 19 | 0 |  |  |
| carrier=semantic_realization | bits_per_decision | 0.0442 | 0 |  |  |
| carrier=semantic_realization | decisions | 430 | 433 |  |  |
| carrier=update_target | acceptance_rate | 1 | 1 |  |  |
| carrier=update_target | avg_candidate_set_size | 2.9939 | 3 |  |  |
| carrier=update_target | avg_entropy | 1.0782 | 1.1111 |  |  |
| carrier=update_target | bits_embedded | 8 | 0 |  |  |
| carrier=update_target | bits_per_decision | 0.0488 | 0 |  |  |
| carrier=update_target | decisions | 164 | 201 |  |  |

## RQ3 Verification

### r1
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | bit_recovery_rate | 1 |  |  |  |
|  | bits_recovered | 40 |  |  |  |
|  | bits_total | 40 |  |  |  |
|  | commitment_pass_rate | 1 |  |  |  |


### r2
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| r=0.1 | anchor_signature_valid | 1 |  |  |  |
| r=0.1 | bit_recovery_rate | 0 |  |  |  |
| r=0.1 | bits_recovered | 0 |  |  |  |
| r=0.1 | bits_total | 40 |  |  |  |
| r=0.1 | kept_leaves | 84 |  |  |  |
| r=0.1 | root_matches | 1 |  |  |  |
| r=0.3 | anchor_signature_valid | 1 |  |  |  |
| r=0.3 | bit_recovery_rate | 0.2750 |  |  |  |
| r=0.3 | bits_recovered | 11 |  |  |  |
| r=0.3 | bits_total | 40 |  |  |  |
| r=0.3 | kept_leaves | 251 |  |  |  |
| r=0.3 | root_matches | 1 |  |  |  |
| r=0.5 | anchor_signature_valid | 1 |  |  |  |
| r=0.5 | bit_recovery_rate | 0.5750 |  |  |  |
| r=0.5 | bits_recovered | 23 |  |  |  |
| r=0.5 | bits_total | 40 |  |  |  |
| r=0.5 | kept_leaves | 418 |  |  |  |
| r=0.5 | root_matches | 1 |  |  |  |
| r=0.7 | anchor_signature_valid | 1 |  |  |  |
| r=0.7 | bit_recovery_rate | 0.7250 |  |  |  |
| r=0.7 | bits_recovered | 29 |  |  |  |
| r=0.7 | bits_total | 40 |  |  |  |
| r=0.7 | kept_leaves | 586 |  |  |  |
| r=0.7 | root_matches | 1 |  |  |  |
| r=0.9 | anchor_signature_valid | 1 |  |  |  |
| r=0.9 | bit_recovery_rate | 0.9500 |  |  |  |
| r=0.9 | bits_recovered | 38 |  |  |  |
| r=0.9 | bits_total | 40 |  |  |  |
| r=0.9 | kept_leaves | 753 |  |  |  |
| r=0.9 | root_matches | 1 |  |  |  |


### r3
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | anchor_signature_valid | 1 |  |  |  |
|  | bit_recovery_rate | 1 |  |  |  |
|  | bits_recovered | 40 |  |  |  |
|  | bits_total | 40 |  |  |  |
|  | root_matches | 1 |  |  |  |


### r3_carrier_breakdown
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | bit_recovery_rate | 1 |  |  |  |
| carrier=link_target | bits_recovered | 13 |  |  |  |
| carrier=link_target | bits_total | 13 |  |  |  |
| carrier=link_target | leaves | 243 |  |  |  |
| carrier=semantic_realization | bit_recovery_rate | 1 |  |  |  |
| carrier=semantic_realization | bits_recovered | 19 |  |  |  |
| carrier=semantic_realization | bits_total | 19 |  |  |  |
| carrier=semantic_realization | leaves | 430 |  |  |  |
| carrier=update_target | bit_recovery_rate | 1 |  |  |  |
| carrier=update_target | bits_recovered | 8 |  |  |  |
| carrier=update_target | bits_total | 8 |  |  |  |
| carrier=update_target | leaves | 164 |  |  |  |


### r3_wrong_key
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | anchor_signature_valid | 0 |  |  |  |
|  | bit_recovery_rate | 0.1500 |  |  |  |

## RQ4 Robustness

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | pre_recovery | 1 |  |  |  |


### outcomes
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| attack=compaction;strength=0.1 | bit_recovery_post | 0.9000 |  |  |  |
| attack=compaction;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=compaction;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=compaction;strength=0.1 | name | compaction |  |  |  |
| attack=compaction;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=compaction;strength=0.1 | tamper_detection_rate | 0.1004 |  |  |  |
| attack=compaction;strength=0.3 | bit_recovery_post | 0.6250 |  |  |  |
| attack=compaction;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=compaction;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=compaction;strength=0.3 | name | compaction |  |  |  |
| attack=compaction;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=compaction;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=compaction;strength=0.5 | bit_recovery_post | 0.5000 |  |  |  |
| attack=compaction;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=compaction;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=compaction;strength=0.5 | name | compaction |  |  |  |
| attack=compaction;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=compaction;strength=0.5 | tamper_detection_rate | 0.4994 |  |  |  |
| attack=dedup;strength=0.1 | bit_recovery_post | 1 |  |  |  |
| attack=dedup;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=dedup;strength=0.1 | leaves_affected | 10 |  |  |  |
| attack=dedup;strength=0.1 | name | dedup |  |  |  |
| attack=dedup;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=dedup;strength=0.1 | tamper_detection_rate | 0 |  |  |  |
| attack=dedup;strength=0.3 | bit_recovery_post | 1 |  |  |  |
| attack=dedup;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=dedup;strength=0.3 | leaves_affected | 10 |  |  |  |
| attack=dedup;strength=0.3 | name | dedup |  |  |  |
| attack=dedup;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=dedup;strength=0.3 | tamper_detection_rate | 0 |  |  |  |
| attack=dedup;strength=0.5 | bit_recovery_post | 1 |  |  |  |
| attack=dedup;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=dedup;strength=0.5 | leaves_affected | 10 |  |  |  |
| attack=dedup;strength=0.5 | name | dedup |  |  |  |
| attack=dedup;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=dedup;strength=0.5 | tamper_detection_rate | 0 |  |  |  |
| attack=edge_relabel;strength=0.1 | bit_recovery_post | 0.9000 |  |  |  |
| attack=edge_relabel;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=edge_relabel;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=edge_relabel;strength=0.1 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=edge_relabel;strength=0.1 | tamper_detection_rate | 0.1004 |  |  |  |
| attack=edge_relabel;strength=0.3 | bit_recovery_post | 0.6750 |  |  |  |
| attack=edge_relabel;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=edge_relabel;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=edge_relabel;strength=0.3 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=edge_relabel;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=edge_relabel;strength=0.5 | bit_recovery_post | 0.5250 |  |  |  |
| attack=edge_relabel;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=edge_relabel;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=edge_relabel;strength=0.5 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=edge_relabel;strength=0.5 | tamper_detection_rate | 0.4994 |  |  |  |
| attack=manual_edits;strength=0.1 | bit_recovery_post | 0.9000 |  |  |  |
| attack=manual_edits;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=manual_edits;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=manual_edits;strength=0.1 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=manual_edits;strength=0.1 | tamper_detection_rate | 0.1004 |  |  |  |
| attack=manual_edits;strength=0.3 | bit_recovery_post | 0.7500 |  |  |  |
| attack=manual_edits;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=manual_edits;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=manual_edits;strength=0.3 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=manual_edits;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=manual_edits;strength=0.5 | bit_recovery_post | 0.4500 |  |  |  |
| attack=manual_edits;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=manual_edits;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=manual_edits;strength=0.5 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=manual_edits;strength=0.5 | tamper_detection_rate | 0.4994 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | bit_recovery_post | 0.8750 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | tamper_detection_rate | 0.1004 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | bit_recovery_post | 0.6750 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | bit_recovery_post | 0.4750 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | tamper_detection_rate | 0.4994 |  |  |  |
| attack=poisoning;strength=0.1 | bit_recovery_post | 0.6897 |  |  |  |
| attack=poisoning;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=poisoning;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=poisoning;strength=0.1 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=poisoning;strength=0.1 | tamper_detection_rate | 0.0912 |  |  |  |
| attack=poisoning;strength=0.3 | bit_recovery_post | 0.5970 |  |  |  |
| attack=poisoning;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=poisoning;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=poisoning;strength=0.3 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=poisoning;strength=0.3 | tamper_detection_rate | 0.2307 |  |  |  |
| attack=poisoning;strength=0.5 | bit_recovery_post | 0.5479 |  |  |  |
| attack=poisoning;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=poisoning;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=poisoning;strength=0.5 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=poisoning;strength=0.5 | tamper_detection_rate | 0.3331 |  |  |  |
| attack=pruning;strength=0.1 | bit_recovery_post | 1 |  |  |  |
| attack=pruning;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=pruning;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=pruning;strength=0.1 | name | pruning |  |  |  |
| attack=pruning;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=pruning;strength=0.1 | tamper_detection_rate | 0 |  |  |  |
| attack=pruning;strength=0.3 | bit_recovery_post | 1 |  |  |  |
| attack=pruning;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=pruning;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=pruning;strength=0.3 | name | pruning |  |  |  |
| attack=pruning;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=pruning;strength=0.3 | tamper_detection_rate | 0 |  |  |  |
| attack=pruning;strength=0.5 | bit_recovery_post | 1 |  |  |  |
| attack=pruning;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=pruning;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=pruning;strength=0.5 | name | pruning |  |  |  |
| attack=pruning;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=pruning;strength=0.5 | tamper_detection_rate | 0 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | bit_recovery_post | 0.9750 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | tamper_detection_rate | 0.1004 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | bit_recovery_post | 0.8500 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | bit_recovery_post | 0.5500 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | tamper_detection_rate | 0.4994 |  |  |  |
| attack=supersession;strength=0.1 | bit_recovery_post | 0.9000 |  |  |  |
| attack=supersession;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=supersession;strength=0.1 | leaves_affected | 84 |  |  |  |
| attack=supersession;strength=0.1 | name | supersession |  |  |  |
| attack=supersession;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=supersession;strength=0.1 | tamper_detection_rate | 0.1004 |  |  |  |
| attack=supersession;strength=0.3 | bit_recovery_post | 0.6250 |  |  |  |
| attack=supersession;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=supersession;strength=0.3 | leaves_affected | 251 |  |  |  |
| attack=supersession;strength=0.3 | name | supersession |  |  |  |
| attack=supersession;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=supersession;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=supersession;strength=0.5 | bit_recovery_post | 0.4250 |  |  |  |
| attack=supersession;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=supersession;strength=0.5 | leaves_affected | 418 |  |  |  |
| attack=supersession;strength=0.5 | name | supersession |  |  |  |
| attack=supersession;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=supersession;strength=0.5 | tamper_detection_rate | 0.4994 |  |  |  |

## RQ5 Integrity

### by_carrier_counts
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | count | 243 | 204 |  |  |
| carrier=semantic_realization | count | 430 | 433 |  |  |
| carrier=update_target | count | 164 | 201 |  |  |


### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | contradiction_rate | 0 | 0 |  |  |
|  | duplicate_count | 0 | 0 |  |  |
|  | duplication_rate | 0 | 0 |  |  |
|  | evidence_recall_mean | 0.5288 | 0.6142 |  |  |
|  | evidence_required_qas | 197 | 197 |  |  |
|  | link_target_total | 243 | 204 |  |  |
|  | overall_records | 418 | 419 |  |  |
|  | qa_with_full_evidence | 92 | 110 |  |  |
|  | update_target_accuracy | 1 | 1 |  |  |
|  | update_target_correct | 164 | 201 |  |  |
|  | update_target_total | 164 | 201 |  |  |
