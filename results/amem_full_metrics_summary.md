# A-MEM Full Metrics Summary

- **Files**: 8
- **Cell value**: numeric values are mean across JSON files; empty means baseline has no metric.

## RQ1 Utility

### deltas_vs_no_watermark
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| base=no_watermark | memory_count_delta | -0.2500 |  | 0 | 0.1250 |
| base=no_watermark | qa_accuracy_delta | 0.0093 |  | -0.1389 | -0.1675 |
| base=no_watermark | qa_bleu1_delta | 0.0072 |  | -0.1378 | -0.1633 |
| base=no_watermark | qa_f1_delta | 0.0148 |  | -0.1504 | -0.1820 |
| base=no_watermark | qa_rougeL_delta | 0.0122 |  | -0.1368 | -0.1647 |
| base=no_watermark | write_failures_delta | 0.2500 |  | 0.2500 | -0.1250 |


### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | bits_embedded | 40.3750 | 0 | 0 | 0 |
|  | capacity_bits_per_decision | 0.0371 | 0 | 0 | 0 |
|  | memory_count | 593.7500 | 594 | 594 | 594.1250 |
|  | qa_accuracy | 0.1768 | 0.1675 | 0.0286 | 0 |
|  | qa_bleu1 | 0.1706 | 0.1633 | 0.0256 | 0 |
|  | qa_count | 199.6250 | 199.6250 | 199.6250 | 199.6250 |
|  | qa_f1 | 0.1967 | 0.1820 | 0.0315 | 0 |
|  | qa_rougeL | 0.1769 | 0.1647 | 0.0279 | 0 |
|  | write_failures | 0.3750 | 0.1250 | 0.3750 | 0 |


### qa_by_category
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| category=1 | bleu1 | 0.1308 | 0.1317 | 0.0138 | 0 |
| category=1 | f1 | 0.1299 | 0.1319 | 0.0208 | 0 |
| category=1 | judge_acc | 0.0739 | 0.0929 | 0.0114 | 0 |
| category=1 | n | 28.7500 | 28.7500 | 28.7500 | 28.7500 |
| category=1 | rougeL | 0.1106 | 0.1115 | 0.0104 | 0 |
| category=2 | bleu1 | 0.3706 | 0.3465 | 0.0647 | 0 |
| category=2 | f1 | 0.3519 | 0.3331 | 0.0694 | 0 |
| category=2 | judge_acc | 0.3521 | 0.3363 | 0.0769 | 0 |
| category=2 | n | 31.2500 | 31.2500 | 31.2500 | 31.2500 |
| category=2 | rougeL | 0.3355 | 0.3151 | 0.0694 | 0 |
| category=3 | bleu1 | 0.1023 | 0.0757 | 0 | 0 |
| category=3 | f1 | 0.1091 | 0.0776 | 0 | 0 |
| category=3 | judge_acc | 0.0758 | 0.0452 | 0 | 0 |
| category=3 | n | 10 | 10 | 10 | 10 |
| category=3 | rougeL | 0.0948 | 0.0693 | 0 | 0 |
| category=4 | bleu1 | 0.1968 | 0.1908 | 0.0193 | 0 |
| category=4 | f1 | 0.2453 | 0.2258 | 0.0290 | 0 |
| category=4 | judge_acc | 0.2226 | 0.2075 | 0.0199 | 0 |
| category=4 | n | 86 | 86 | 86 | 86 |
| category=4 | rougeL | 0.2311 | 0.2126 | 0.0229 | 0 |
| category=5 | bleu1 | 0 | 0 | 0 | 0 |
| category=5 | f1 | 0.0365 | 0.0280 | 0 | 0 |
| category=5 | judge_acc | 0.0365 | 0.0280 | 0 | 0 |
| category=5 | n | 44.8750 | 44.8750 | 44.8750 | 44.8750 |
| category=5 | rougeL | 0 | 0 | 0 | 0 |

## RQ2 Capacity

### by_carrier
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | acceptance_rate | 1 | 1 | 1 | 1 |
| carrier=link_target | avg_candidate_set_size | 3.9961 | 3.9994 | 3.9943 | 4 |
| carrier=link_target | avg_entropy | 1.4721 | 1.4718 | 1.4785 | 1.4886 |
| carrier=link_target | bits_embedded | 11.2500 | 0 | 0 | 0 |
| carrier=link_target | bits_per_decision | 0.0324 | 0 | 0 | 0 |
| carrier=link_target | decisions | 364.8750 | 344.8750 | 126.7143 | 187 |
| carrier=llm_call | acceptance_rate | 1 | 1 |  |  |
| carrier=llm_call | avg_candidate_set_size | 3.8000 | 3.3333 |  |  |
| carrier=llm_call | avg_entropy | 1.4442 | 0.7386 |  |  |
| carrier=llm_call | bits_embedded | 0 | 0 |  |  |
| carrier=llm_call | bits_per_decision | 0 | 0 |  |  |
| carrier=llm_call | decisions | 1.2000 | 1 |  |  |
| carrier=semantic_realization | acceptance_rate | 1 | 1 | 1 | 1 |
| carrier=semantic_realization | avg_candidate_set_size | 3.9998 | 4 | 4 | 4 |
| carrier=semantic_realization | avg_entropy | 1.5092 | 1.5270 | 1.5127 | 1.4895 |
| carrier=semantic_realization | bits_embedded | 21.8750 | 0 | 0 | 0 |
| carrier=semantic_realization | bits_per_decision | 0.0384 | 0 | 0 | 0 |
| carrier=semantic_realization | decisions | 592.3750 | 585.3750 | 216.8571 | 298 |
| carrier=update_target | acceptance_rate | 1 | 1 | 1 | 1 |
| carrier=update_target | avg_candidate_set_size | 3.9993 | 3.9980 | 4 | 4 |
| carrier=update_target | avg_entropy | 1.4810 | 1.4669 | 1.4464 | 1.4936 |
| carrier=update_target | bits_embedded | 7.2500 | 0 | 0 | 0 |
| carrier=update_target | bits_per_decision | 0.0421 | 0 | 0 | 0 |
| carrier=update_target | decisions | 175.1250 | 159.5000 | 73.5714 | 110 |


### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | acceptance_rate | 1 | 1 | 0.8750 | 0.1250 |
|  | avg_candidate_set_size | 3.9984 | 3.9993 | 3.4984 | 0.5000 |
|  | avg_entropy | 1.4929 | 1.5009 | 1.3043 | 0.1862 |
|  | bits_embedded | 40.3750 | 0 | 0 | 0 |
|  | bits_per_decision | 0.0371 | 0 | 0 | 0 |
|  | decisions | 1133.1250 | 1090.1250 | 365 | 74.3750 |

## RQ3 Verification

### r1
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | bit_recovery_rate | 1 |  | 0 |  |
|  | bits_recovered | 40.3750 |  | 0 |  |
|  | bits_total | 40.3750 |  | 0 |  |
|  | commitment_pass_rate | 1 |  | 1 |  |


### r2
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| r=0.1 | anchor_signature_valid | 1 |  | 1 |  |
| r=0.1 | bit_recovery_rate | 0.0464 |  | 0 |  |
| r=0.1 | bits_recovered | 1.8750 |  | 0 |  |
| r=0.1 | bits_total | 40.3750 |  | 0 |  |
| r=0.1 | kept_leaves | 113.2500 |  | 41.7143 |  |
| r=0.1 | root_matches | 0.7500 |  | 0.7143 |  |
| r=0.3 | anchor_signature_valid | 1 |  | 1 |  |
| r=0.3 | bit_recovery_rate | 0.2447 |  | 0 |  |
| r=0.3 | bits_recovered | 9.8750 |  | 0 |  |
| r=0.3 | bits_total | 40.3750 |  | 0 |  |
| r=0.3 | kept_leaves | 339.7500 |  | 125.1429 |  |
| r=0.3 | root_matches | 0.7500 |  | 0.7143 |  |
| r=0.5 | anchor_signature_valid | 1 |  | 1 |  |
| r=0.5 | bit_recovery_rate | 0.4184 |  | 0 |  |
| r=0.5 | bits_recovered | 16.8750 |  | 0 |  |
| r=0.5 | bits_total | 40.3750 |  | 0 |  |
| r=0.5 | kept_leaves | 566.6250 |  | 208.5714 |  |
| r=0.5 | root_matches | 0.7500 |  | 0.7143 |  |
| r=0.7 | anchor_signature_valid | 1 |  | 1 |  |
| r=0.7 | bit_recovery_rate | 0.5303 |  | 0 |  |
| r=0.7 | bits_recovered | 21.3750 |  | 0 |  |
| r=0.7 | bits_total | 40.3750 |  | 0 |  |
| r=0.7 | kept_leaves | 793.2500 |  | 292 |  |
| r=0.7 | root_matches | 0.7500 |  | 0.7143 |  |
| r=0.9 | anchor_signature_valid | 1 |  | 1 |  |
| r=0.9 | bit_recovery_rate | 0.6760 |  | 0 |  |
| r=0.9 | bits_recovered | 27.2500 |  | 0 |  |
| r=0.9 | bits_total | 40.3750 |  | 0 |  |
| r=0.9 | kept_leaves | 1020 |  | 375.4286 |  |
| r=0.9 | root_matches | 0.7500 |  | 0.7143 |  |


### r3
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | anchor_signature_valid | 1 |  | 1 |  |
|  | bit_recovery_rate | 0.7500 |  | 0 |  |
|  | bits_recovered | 30.2500 |  | 0 |  |
|  | bits_total | 40.3750 |  | 0 |  |
|  | root_matches | 0.7500 |  | 0.7143 |  |


### r3_carrier_breakdown
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | bit_recovery_rate | 0.7500 |  | 0 |  |
| carrier=link_target | bits_recovered | 8.3750 |  | 0 |  |
| carrier=link_target | bits_total | 11.2500 |  | 0 |  |
| carrier=link_target | leaves | 364.8750 |  | 126.7143 |  |
| carrier=llm_call | bit_recovery_rate | 0 |  |  |  |
| carrier=llm_call | bits_recovered | 0 |  |  |  |
| carrier=llm_call | bits_total | 0 |  |  |  |
| carrier=llm_call | leaves | 1.2000 |  |  |  |
| carrier=semantic_realization | bit_recovery_rate | 0.7500 |  | 0 |  |
| carrier=semantic_realization | bits_recovered | 16.3750 |  | 0 |  |
| carrier=semantic_realization | bits_total | 21.8750 |  | 0 |  |
| carrier=semantic_realization | leaves | 592.3750 |  | 216.8571 |  |
| carrier=update_target | bit_recovery_rate | 0.7500 |  | 0 |  |
| carrier=update_target | bits_recovered | 5.5000 |  | 0 |  |
| carrier=update_target | bits_total | 7.2500 |  | 0 |  |
| carrier=update_target | leaves | 175.1250 |  | 73.5714 |  |


### r3_wrong_key
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | anchor_signature_valid | 0 |  | 0 |  |
|  | bit_recovery_rate | 0.1637 |  | 0 |  |

## RQ4 Robustness

### outcomes
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| attack=compaction;strength=0.1 | bit_recovery_post | 0.6912 |  |  |  |
| attack=compaction;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=compaction;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=compaction;strength=0.1 | name | compaction |  |  |  |
| attack=compaction;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=compaction;strength=0.1 | tamper_detection_rate | 0.0999 |  |  |  |
| attack=compaction;strength=0.3 | bit_recovery_post | 0.5607 |  |  |  |
| attack=compaction;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=compaction;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=compaction;strength=0.3 | name | compaction |  |  |  |
| attack=compaction;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=compaction;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=compaction;strength=0.5 | bit_recovery_post | 0.4028 |  |  |  |
| attack=compaction;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=compaction;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=compaction;strength=0.5 | name | compaction |  |  |  |
| attack=compaction;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=compaction;strength=0.5 | tamper_detection_rate | 0.5001 |  |  |  |
| attack=dedup;strength=0.1 | bit_recovery_post | 0 |  |  |  |
| attack=dedup;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=dedup;strength=0.1 | leaves_affected | 56.6250 |  |  |  |
| attack=dedup;strength=0.1 | name | dedup |  |  |  |
| attack=dedup;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=dedup;strength=0.1 | tamper_detection_rate | 0 |  |  |  |
| attack=dedup;strength=0.3 | bit_recovery_post | 0 |  |  |  |
| attack=dedup;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=dedup;strength=0.3 | leaves_affected | 170 |  |  |  |
| attack=dedup;strength=0.3 | name | dedup |  |  |  |
| attack=dedup;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=dedup;strength=0.3 | tamper_detection_rate | 0 |  |  |  |
| attack=dedup;strength=0.5 | bit_recovery_post | 0 |  |  |  |
| attack=dedup;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=dedup;strength=0.5 | leaves_affected | 283.2500 |  |  |  |
| attack=dedup;strength=0.5 | name | dedup |  |  |  |
| attack=dedup;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=dedup;strength=0.5 | tamper_detection_rate | 0 |  |  |  |
| attack=edge_relabel;strength=0.1 | bit_recovery_post | 0.6665 |  |  |  |
| attack=edge_relabel;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=edge_relabel;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=edge_relabel;strength=0.1 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=edge_relabel;strength=0.1 | tamper_detection_rate | 0.0999 |  |  |  |
| attack=edge_relabel;strength=0.3 | bit_recovery_post | 0.4867 |  |  |  |
| attack=edge_relabel;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=edge_relabel;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=edge_relabel;strength=0.3 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=edge_relabel;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=edge_relabel;strength=0.5 | bit_recovery_post | 0.3160 |  |  |  |
| attack=edge_relabel;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=edge_relabel;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=edge_relabel;strength=0.5 | name | edge_relabel |  |  |  |
| attack=edge_relabel;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=edge_relabel;strength=0.5 | tamper_detection_rate | 0.5001 |  |  |  |
| attack=manual_edits;strength=0.1 | bit_recovery_post | 0.7157 |  |  |  |
| attack=manual_edits;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=manual_edits;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=manual_edits;strength=0.1 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=manual_edits;strength=0.1 | tamper_detection_rate | 0.0999 |  |  |  |
| attack=manual_edits;strength=0.3 | bit_recovery_post | 0.5580 |  |  |  |
| attack=manual_edits;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=manual_edits;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=manual_edits;strength=0.3 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=manual_edits;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=manual_edits;strength=0.5 | bit_recovery_post | 0.4030 |  |  |  |
| attack=manual_edits;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=manual_edits;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=manual_edits;strength=0.5 | name | manual_edits |  |  |  |
| attack=manual_edits;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=manual_edits;strength=0.5 | tamper_detection_rate | 0.5001 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | bit_recovery_post | 0.6666 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.1 | tamper_detection_rate | 0.0999 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | bit_recovery_post | 0.5082 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | bit_recovery_post | 0.3939 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | name | paraphrase_rewrite |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=paraphrase_rewrite;strength=0.5 | tamper_detection_rate | 0.5001 |  |  |  |
| attack=poisoning;strength=0.1 | bit_recovery_post | 0 |  |  |  |
| attack=poisoning;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=poisoning;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=poisoning;strength=0.1 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=poisoning;strength=0.1 | tamper_detection_rate | 0.0908 |  |  |  |
| attack=poisoning;strength=0.3 | bit_recovery_post | 0 |  |  |  |
| attack=poisoning;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=poisoning;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=poisoning;strength=0.3 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=poisoning;strength=0.3 | tamper_detection_rate | 0.2307 |  |  |  |
| attack=poisoning;strength=0.5 | bit_recovery_post | 0 |  |  |  |
| attack=poisoning;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=poisoning;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=poisoning;strength=0.5 | name | poisoning |  |  |  |
| attack=poisoning;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=poisoning;strength=0.5 | tamper_detection_rate | 0.3334 |  |  |  |
| attack=pruning;strength=0.1 | bit_recovery_post | 0 |  |  |  |
| attack=pruning;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=pruning;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=pruning;strength=0.1 | name | pruning |  |  |  |
| attack=pruning;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=pruning;strength=0.1 | tamper_detection_rate | 0 |  |  |  |
| attack=pruning;strength=0.3 | bit_recovery_post | 0 |  |  |  |
| attack=pruning;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=pruning;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=pruning;strength=0.3 | name | pruning |  |  |  |
| attack=pruning;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=pruning;strength=0.3 | tamper_detection_rate | 0 |  |  |  |
| attack=pruning;strength=0.5 | bit_recovery_post | 0 |  |  |  |
| attack=pruning;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=pruning;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=pruning;strength=0.5 | name | pruning |  |  |  |
| attack=pruning;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=pruning;strength=0.5 | tamper_detection_rate | 0 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | bit_recovery_post | 0.6696 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=subgraph_reanchor;strength=0.1 | tamper_detection_rate | 0.0999 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | bit_recovery_post | 0.5491 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=subgraph_reanchor;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | bit_recovery_post | 0.3941 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | name | subgraph_reanchor |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=subgraph_reanchor;strength=0.5 | tamper_detection_rate | 0.5001 |  |  |  |
| attack=supersession;strength=0.1 | bit_recovery_post | 0.7003 |  |  |  |
| attack=supersession;strength=0.1 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=supersession;strength=0.1 | leaves_affected | 113.2500 |  |  |  |
| attack=supersession;strength=0.1 | name | supersession |  |  |  |
| attack=supersession;strength=0.1 | strength | 0.1000 |  |  |  |
| attack=supersession;strength=0.1 | tamper_detection_rate | 0.0999 |  |  |  |
| attack=supersession;strength=0.3 | bit_recovery_post | 0.5577 |  |  |  |
| attack=supersession;strength=0.3 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=supersession;strength=0.3 | leaves_affected | 339.7500 |  |  |  |
| attack=supersession;strength=0.3 | name | supersession |  |  |  |
| attack=supersession;strength=0.3 | strength | 0.3000 |  |  |  |
| attack=supersession;strength=0.3 | tamper_detection_rate | 0.2999 |  |  |  |
| attack=supersession;strength=0.5 | bit_recovery_post | 0.4030 |  |  |  |
| attack=supersession;strength=0.5 | bit_recovery_pre | 0.7500 |  |  |  |
| attack=supersession;strength=0.5 | leaves_affected | 566.6250 |  |  |  |
| attack=supersession;strength=0.5 | name | supersession |  |  |  |
| attack=supersession;strength=0.5 | strength | 0.5000 |  |  |  |
| attack=supersession;strength=0.5 | tamper_detection_rate | 0.5001 |  |  |  |


### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | pre_recovery | 0.7500 |  |  |  |

## RQ5 Integrity

### by_carrier_counts
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
| carrier=link_target | count | 364.8750 | 344.8750 | 126.7143 | 187 |
| carrier=llm_call | count | 1.2000 | 1 |  |  |
| carrier=semantic_realization | count | 592.3750 | 585.3750 | 216.8571 | 298 |
| carrier=update_target | count | 175.1250 | 159.5000 | 73.5714 | 110 |


### overall
| item | metric | watermark | no_watermark | signed_metadata_only | random_replace |
| --- | --- | --- | --- | --- | --- |
|  | contradiction_rate | 0 | 0 | 0 | 0 |
|  | duplicate_count | 0 | 0 | 0 | 0 |
|  | duplication_rate | 0 | 0 | 0 | 0 |
|  | evidence_recall_mean | 0.9972 | 0.9972 | 0.9966 | 0.9972 |
|  | evidence_required_qas | 199.3750 | 199.3750 | 199.3750 | 199.3750 |
|  | link_target_total | 364.8750 | 344.8750 | 110.8750 | 23.3750 |
|  | overall_records | 593.7500 | 594 | 594 | 594.1250 |
|  | qa_with_full_evidence | 198.5000 | 198.5000 | 198.2500 | 198.5000 |
|  | update_target_accuracy | 0 | 0 | 0 | 0 |
|  | update_target_correct | 0 | 0 | 0 | 0 |
|  | update_target_total | 175.1250 | 159.5000 | 64.3750 | 13.7500 |
