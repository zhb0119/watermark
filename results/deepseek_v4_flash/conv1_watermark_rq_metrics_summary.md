# LoCoMo RQ Metrics Summary

- **File**: `results\deepseek_v4_flash\conv1_watermark.json`
- **Cell value**: numeric values are from this JSON file; empty means baseline has no metric.

## RQ1 Utility

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | bits_embedded | 40 |  |  |  |
|  | capacity_bits_per_decision | 0.0552 |  |  |  |
|  | memory_count | 365 |  |  |  |
|  | qa_accuracy | 0.4381 |  |  |  |
|  | qa_bleu1 | 0.4166 |  |  |  |
|  | qa_count | 105 |  |  |  |
|  | qa_f1 | 0.4394 |  |  |  |
|  | qa_rougeL | 0.4224 |  |  |  |
|  | write_failures | 0 |  |  |  |


### qa_by_category
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| category=1 | bleu1 | 0.5004 |  |  |  |
| category=1 | f1 | 0.4284 |  |  |  |
| category=1 | judge_acc | 0.2727 |  |  |  |
| category=1 | n | 11 |  |  |  |
| category=1 | rougeL | 0.3616 |  |  |  |
| category=2 | bleu1 | 0.5586 |  |  |  |
| category=2 | f1 | 0.6038 |  |  |  |
| category=2 | judge_acc | 0.7692 |  |  |  |
| category=2 | n | 26 |  |  |  |
| category=2 | rougeL | 0.6161 |  |  |  |
| category=4 | bleu1 | 0.3500 |  |  |  |
| category=4 | f1 | 0.3660 |  |  |  |
| category=4 | judge_acc | 0.3182 |  |  |  |
| category=4 | n | 44 |  |  |  |
| category=4 | rougeL | 0.3526 |  |  |  |
| category=5 | bleu1 | 0.3465 |  |  |  |
| category=5 | f1 | 0.4011 |  |  |  |
| category=5 | judge_acc | 0.3750 |  |  |  |
| category=5 | n | 24 |  |  |  |
| category=5 | rougeL | 0.3683 |  |  |  |

## RQ2 Capacity

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | acceptance_rate | 1 |  |  |  |
|  | avg_candidate_set_size | 2.9972 |  |  |  |
|  | avg_entropy | 1.0709 |  |  |  |
|  | bits_embedded | 40 |  |  |  |
|  | bits_per_decision | 0.0552 |  |  |  |
|  | decisions | 725 |  |  |  |


### by_carrier
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | acceptance_rate | 1 |  |  |  |
| carrier=link_target | avg_candidate_set_size | 2.9954 |  |  |  |
| carrier=link_target | avg_entropy | 1.1124 |  |  |  |
| carrier=link_target | bits_embedded | 13 |  |  |  |
| carrier=link_target | bits_per_decision | 0.0602 |  |  |  |
| carrier=link_target | decisions | 216 |  |  |  |
| carrier=semantic_realization | acceptance_rate | 1 |  |  |  |
| carrier=semantic_realization | avg_candidate_set_size | 2.9973 |  |  |  |
| carrier=semantic_realization | avg_entropy | 1.0372 |  |  |  |
| carrier=semantic_realization | bits_embedded | 15 |  |  |  |
| carrier=semantic_realization | bits_per_decision | 0.0409 |  |  |  |
| carrier=semantic_realization | decisions | 367 |  |  |  |
| carrier=update_target | acceptance_rate | 1 |  |  |  |
| carrier=update_target | avg_candidate_set_size | 3 |  |  |  |
| carrier=update_target | avg_entropy | 1.0949 |  |  |  |
| carrier=update_target | bits_embedded | 12 |  |  |  |
| carrier=update_target | bits_per_decision | 0.0845 |  |  |  |
| carrier=update_target | decisions | 142 |  |  |  |

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
| r=0.1 | bit_recovery_rate | 0.1250 |  |  |  |
| r=0.1 | bits_recovered | 5 |  |  |  |
| r=0.1 | bits_total | 40 |  |  |  |
| r=0.1 | kept_leaves | 72 |  |  |  |
| r=0.1 | root_matches | 1 |  |  |  |
| r=0.3 | anchor_signature_valid | 1 |  |  |  |
| r=0.3 | bit_recovery_rate | 0.4250 |  |  |  |
| r=0.3 | bits_recovered | 17 |  |  |  |
| r=0.3 | bits_total | 40 |  |  |  |
| r=0.3 | kept_leaves | 218 |  |  |  |
| r=0.3 | root_matches | 1 |  |  |  |
| r=0.5 | anchor_signature_valid | 1 |  |  |  |
| r=0.5 | bit_recovery_rate | 0.5750 |  |  |  |
| r=0.5 | bits_recovered | 23 |  |  |  |
| r=0.5 | bits_total | 40 |  |  |  |
| r=0.5 | kept_leaves | 362 |  |  |  |
| r=0.5 | root_matches | 1 |  |  |  |
| r=0.7 | anchor_signature_valid | 1 |  |  |  |
| r=0.7 | bit_recovery_rate | 0.4250 |  |  |  |
| r=0.7 | bits_recovered | 17 |  |  |  |
| r=0.7 | bits_total | 40 |  |  |  |
| r=0.7 | kept_leaves | 507 |  |  |  |
| r=0.7 | root_matches | 1 |  |  |  |
| r=0.9 | anchor_signature_valid | 1 |  |  |  |
| r=0.9 | bit_recovery_rate | 0.8750 |  |  |  |
| r=0.9 | bits_recovered | 35 |  |  |  |
| r=0.9 | bits_total | 40 |  |  |  |
| r=0.9 | kept_leaves | 652 |  |  |  |
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
| carrier=link_target | leaves | 216 |  |  |  |
| carrier=semantic_realization | bit_recovery_rate | 1 |  |  |  |
| carrier=semantic_realization | bits_recovered | 15 |  |  |  |
| carrier=semantic_realization | bits_total | 15 |  |  |  |
| carrier=semantic_realization | leaves | 367 |  |  |  |
| carrier=update_target | bit_recovery_rate | 1 |  |  |  |
| carrier=update_target | bits_recovered | 12 |  |  |  |
| carrier=update_target | bits_total | 12 |  |  |  |
| carrier=update_target | leaves | 142 |  |  |  |


### r3_wrong_key
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | anchor_signature_valid | 0 |  |  |  |
|  | bit_recovery_rate | 0.2000 |  |  |  |

## RQ4 Robustness

### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | pre_recovery | 1 |  |  |  |


### outcomes
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| attack=compaction;strength=0.1 | bit_recovery_post | 0.7500 |  |  |  |
| attack=compaction;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=compaction;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=compaction;strength=0.1 | name | compaction |  |  |  |
| attack=compaction;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=compaction;strength=0.1 | tamper_detection_rate | 0.0993 |  |  |  |
| attack=compaction;strength=0.3 | bit_recovery_post | 0.7000 |  |  |  |
| attack=compaction;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=compaction;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=compaction;strength=0.3 | name | compaction |  |  |  |
| attack=compaction;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=compaction;strength=0.3 | tamper_detection_rate | 0.3007 |  |  |  |
| attack=compaction;strength=0.5 | bit_recovery_post | 0.4750 |  |  |  |
| attack=compaction;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=compaction;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=compaction;strength=0.5 | name | compaction |  |  |  |
| attack=compaction;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=compaction;strength=0.5 | tamper_detection_rate | 0.4993 |  |  |  |
| attack=dedup;strength=0.1 | bit_recovery_post | 1 |  |  |  |
| attack=dedup;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=dedup;strength=0.1 | leaves_affected | 16 |  |  |  |
| attack=dedup;strength=0.1 | name | dedup |  |  |  |
| attack=dedup;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=dedup;strength=0.1 | tamper_detection_rate | 0 |  |  |  |
| attack=dedup;strength=0.3 | bit_recovery_post | 1 |  |  |  |
| attack=dedup;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=dedup;strength=0.3 | leaves_affected | 16 |  |  |  |
| attack=dedup;strength=0.3 | name | dedup |  |  |  |
| attack=dedup;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=dedup;strength=0.3 | tamper_detection_rate | 0 |  |  |  |
| attack=dedup;strength=0.5 | bit_recovery_post | 1 |  |  |  |
| attack=dedup;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=dedup;strength=0.5 | leaves_affected | 16 |  |  |  |
| attack=dedup;strength=0.5 | name | dedup |  |  |  |
| attack=dedup;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=dedup;strength=0.5 | tamper_detection_rate | 0 |  |  |  |
| attack=edge_relabel;strength=0.1 | bit_recovery_post | 0.9500 |  |  |  |
| attack=edge_relabel;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=edge_relabel;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=edge_relabel;strength=0.1 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=edge_relabel;strength=0.1 | tamper_detection_rate | 0.0993 |  |  |  |
| attack=edge_relabel;strength=0.3 | bit_recovery_post | 0.7000 |  |  |  |
| attack=edge_relabel;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=edge_relabel;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=edge_relabel;strength=0.3 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=edge_relabel;strength=0.3 | tamper_detection_rate | 0.3007 |  |  |  |
| attack=edge_relabel;strength=0.5 | bit_recovery_post | 0.4500 |  |  |  |
| attack=edge_relabel;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=edge_relabel;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=edge_relabel;strength=0.5 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=edge_relabel;strength=0.5 | tamper_detection_rate | 0.4993 |  |  |  |
| attack=manual_edits;strength=0.1 | bit_recovery_post | 0.8000 |  |  |  |
| attack=manual_edits;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=manual_edits;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=manual_edits;strength=0.1 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=manual_edits;strength=0.1 | tamper_detection_rate | 0.0993 |  |  |  |
| attack=manual_edits;strength=0.3 | bit_recovery_post | 0.5250 |  |  |  |
| attack=manual_edits;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=manual_edits;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=manual_edits;strength=0.3 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=manual_edits;strength=0.3 | tamper_detection_rate | 0.3007 |  |  |  |
| attack=manual_edits;strength=0.5 | bit_recovery_post | 0.4000 |  |  |  |
| attack=manual_edits;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=manual_edits;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=manual_edits;strength=0.5 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=manual_edits;strength=0.5 | tamper_detection_rate | 0.4993 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | bit_recovery_post | 0.8500 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | tamper_detection_rate | 0.0993 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | bit_recovery_post | 0.6500 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | tamper_detection_rate | 0.3007 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | bit_recovery_post | 0.4250 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | tamper_detection_rate | 0.4993 |  |  |  |
| attack=poisoning;strength=0.1 | bit_recovery_post | 0.9524 |  |  |  |
| attack=poisoning;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=poisoning;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=poisoning;strength=0.1 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=poisoning;strength=0.1 | tamper_detection_rate | 0.0903 |  |  |  |
| attack=poisoning;strength=0.3 | bit_recovery_post | 0.8000 |  |  |  |
| attack=poisoning;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=poisoning;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=poisoning;strength=0.3 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=poisoning;strength=0.3 | tamper_detection_rate | 0.2312 |  |  |  |
| attack=poisoning;strength=0.5 | bit_recovery_post | 0.7407 |  |  |  |
| attack=poisoning;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=poisoning;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=poisoning;strength=0.5 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=poisoning;strength=0.5 | tamper_detection_rate | 0.3330 |  |  |  |
| attack=pruning;strength=0.1 | bit_recovery_post | 0.4444 |  |  |  |
| attack=pruning;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=pruning;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=pruning;strength=0.1 | name | pruning |  |  |  |
| attack=pruning;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=pruning;strength=0.1 | tamper_detection_rate | 0 |  |  |  |
| attack=pruning;strength=0.3 | bit_recovery_post | 0.3333 |  |  |  |
| attack=pruning;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=pruning;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=pruning;strength=0.3 | name | pruning |  |  |  |
| attack=pruning;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=pruning;strength=0.3 | tamper_detection_rate | 0 |  |  |  |
| attack=pruning;strength=0.5 | bit_recovery_post | 0.3684 |  |  |  |
| attack=pruning;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=pruning;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=pruning;strength=0.5 | name | pruning |  |  |  |
| attack=pruning;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=pruning;strength=0.5 | tamper_detection_rate | 0 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | bit_recovery_post | 0.9000 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | tamper_detection_rate | 0.0993 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | bit_recovery_post | 0.7000 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | tamper_detection_rate | 0.3007 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | bit_recovery_post | 0.5500 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | tamper_detection_rate | 0.4993 |  |  |  |
| attack=supersession;strength=0.1 | bit_recovery_post | 0.8750 |  |  |  |
| attack=supersession;strength=0.1 | bit_recovery_pre | 1 |  |  |  |
| attack=supersession;strength=0.1 | leaves_affected | 72 |  |  |  |
| attack=supersession;strength=0.1 | name | supersession |  |  |  |
| attack=supersession;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=supersession;strength=0.1 | tamper_detection_rate | 0.0993 |  |  |  |
| attack=supersession;strength=0.3 | bit_recovery_post | 0.6000 |  |  |  |
| attack=supersession;strength=0.3 | bit_recovery_pre | 1 |  |  |  |
| attack=supersession;strength=0.3 | leaves_affected | 218 |  |  |  |
| attack=supersession;strength=0.3 | name | supersession |  |  |  |
| attack=supersession;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=supersession;strength=0.3 | tamper_detection_rate | 0.3007 |  |  |  |
| attack=supersession;strength=0.5 | bit_recovery_post | 0.4000 |  |  |  |
| attack=supersession;strength=0.5 | bit_recovery_pre | 1 |  |  |  |
| attack=supersession;strength=0.5 | leaves_affected | 362 |  |  |  |
| attack=supersession;strength=0.5 | name | supersession |  |  |  |
| attack=supersession;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=supersession;strength=0.5 | tamper_detection_rate | 0.4993 |  |  |  |

## RQ5 Integrity

### by_carrier_counts
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | count | 216 |  |  |  |
| carrier=semantic_realization | count | 367 |  |  |  |
| carrier=update_target | count | 142 |  |  |  |


### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | contradiction_rate | 0 |  |  |  |
|  | duplicate_count | 0 |  |  |  |
|  | duplication_rate | 0 |  |  |  |
|  | evidence_recall_mean | 0.7070 |  |  |  |
|  | evidence_required_qas | 105 |  |  |  |
|  | link_target_total | 216 |  |  |  |
|  | overall_records | 365 |  |  |  |
|  | qa_with_full_evidence | 69 |  |  |  |
|  | update_target_accuracy | 1 |  |  |  |
|  | update_target_correct | 142 |  |  |  |
|  | update_target_total | 142 |  |  |  |
