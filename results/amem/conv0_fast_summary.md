# LoCoMo Result Summary: `results\amem\conv0_fast.json`

## Config
| field | value |
| --- | --- |
| conversation | 0 |
| sample_id | conv-26 |
| max_sessions | 999 |
| max_qa | 20 |
| backend | amem |
| llm_mode | real |
| baselines | watermark, no_watermark, signed_metadata_only, random_replace |
| dataset_sessions | 19 |
| dataset_qa | 199 |

## RQ1 Utility / Memory / Capacity
| baseline | acc | f1 | bleu1 | rougeL | qa | mem | fail | bits | bits/decision | R3 recover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| watermark | 0.050 | 0.134 | 0.116 | 0.128 | 20 | 92 | 0 | 40 | 0.449 | 1.000 |
| no_watermark | 0.150 | 0.185 | 0.166 | 0.193 | 20 | 84 | 0 | 0 | 0.000 | - |
| signed_metadata_only | 0.150 | 0.194 | 0.209 | 0.212 | 20 | 92 | 0 | 0 | 0.000 | 0.000 |
| random_replace | 0.150 | 0.194 | 0.187 | 0.196 | 20 | 90 | 0 | 0 | 0.000 | - |

## RQ1 Deltas
| comparison | f1_delta | acc_delta | memory_delta |
| --- | --- | --- | --- |
| watermark | -0.051 | -0.100 | 8 |
| signed_metadata_only | 0.009 | 0.000 | 8 |
| random_replace | 0.009 | 0.000 | 6 |

## RQ2 Carrier Capacity
| baseline | carrier | decisions | bits | bits/decision | cand | entropy | accept |
| --- | --- | --- | --- | --- | --- | --- | --- |
| watermark | ALL | 89.0 | 40.0 | 0.449 | 4.000 | 1.456 | 1.000 |
| watermark | link_target | 68.0 | 31.0 | 0.456 | 4.000 | 1.476 | 1.000 |
| watermark | update_target | 21.0 | 9.0 | 0.429 | 4.000 | 1.391 | 1.000 |
| no_watermark | ALL | 81.0 | 0.0 | 0.000 | 4.000 | 1.433 | 1.000 |
| no_watermark | link_target | 65.0 | 0.0 | 0.000 | 4.000 | 1.451 | 1.000 |
| no_watermark | update_target | 16.0 | 0.0 | 0.000 | 4.000 | 1.361 | 1.000 |
| signed_metadata_only | ALL | 91.0 | 0.0 | 0.000 | 4.000 | 1.450 | 1.000 |
| signed_metadata_only | link_target | 70.0 | 0.0 | 0.000 | 4.000 | 1.404 | 1.000 |
| signed_metadata_only | update_target | 21.0 | 0.0 | 0.000 | 4.000 | 1.603 | 1.000 |
| random_replace | ALL | 89.0 | 0.0 | 0.000 | 4.000 | 1.481 | 1.000 |
| random_replace | link_target | 75.0 | 0.0 | 0.000 | 4.000 | 1.484 | 1.000 |
| random_replace | update_target | 14.0 | 0.0 | 0.000 | 4.000 | 1.463 | 1.000 |

## RQ3 In-Record Attribution
| baseline | R1 recover | commit | R3 recover | R3 bits | wrong-key recover | wrong-key sig |
| --- | --- | --- | --- | --- | --- | --- |
| watermark | 1.000 | 1.000 | 1.000 | 40.000 | 0.250 | 0.000 |
| signed_metadata_only | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |

## RQ4 Robustness
| baseline | attack | strength | leaves | pre | post | tamper |
| --- | --- | --- | --- | --- | --- | --- |
| watermark | compaction | 0.100 | 9 | 1.000 | 0.825 | 0.101 |
| watermark | compaction | 0.300 | 27 | 1.000 | 0.750 | 0.303 |
| watermark | compaction | 0.500 | 44 | 1.000 | 0.600 | 0.494 |
| watermark | supersession | 0.100 | 9 | 1.000 | 0.875 | 0.101 |
| watermark | supersession | 0.300 | 27 | 1.000 | 0.675 | 0.303 |
| watermark | supersession | 0.500 | 44 | 1.000 | 0.500 | 0.494 |
| watermark | pruning | 0.100 | 9 | 1.000 | 0.000 | 0.000 |
| watermark | pruning | 0.300 | 27 | 1.000 | 0.000 | 0.000 |
| watermark | pruning | 0.500 | 44 | 1.000 | 0.000 | 0.000 |
| watermark | manual_edits | 0.100 | 9 | 1.000 | 0.950 | 0.101 |
| watermark | manual_edits | 0.300 | 27 | 1.000 | 0.750 | 0.303 |
| watermark | manual_edits | 0.500 | 44 | 1.000 | 0.375 | 0.494 |
| watermark | dedup | 0.100 | 4 | 1.000 | 0.000 | 0.000 |
| watermark | dedup | 0.300 | 13 | 1.000 | 0.000 | 0.000 |
| watermark | dedup | 0.500 | 22 | 1.000 | 0.000 | 0.000 |
| watermark | paraphrase_rewrite | 0.100 | 9 | 1.000 | 0.950 | 0.101 |
| watermark | paraphrase_rewrite | 0.300 | 27 | 1.000 | 0.725 | 0.303 |
| watermark | paraphrase_rewrite | 0.500 | 44 | 1.000 | 0.525 | 0.494 |
| watermark | poisoning | 0.100 | 9 | 1.000 | 0.000 | 0.092 |
| watermark | poisoning | 0.300 | 27 | 1.000 | 0.000 | 0.233 |
| watermark | poisoning | 0.500 | 44 | 1.000 | 0.000 | 0.331 |
| watermark | edge_relabel | 0.100 | 9 | 1.000 | 0.950 | 0.101 |
| watermark | edge_relabel | 0.300 | 27 | 1.000 | 0.725 | 0.303 |
| watermark | edge_relabel | 0.500 | 44 | 1.000 | 0.550 | 0.494 |
| watermark | subgraph_reanchor | 0.100 | 9 | 1.000 | 0.925 | 0.101 |
| watermark | subgraph_reanchor | 0.300 | 27 | 1.000 | 0.600 | 0.303 |
| watermark | subgraph_reanchor | 0.500 | 44 | 1.000 | 0.350 | 0.494 |

## RQ5 Integrity / Evidence
| baseline | evidence_recall | answerable | context_dia_recall | qa |
| --- | --- | --- | --- | --- |
| watermark | 0.512 | - | - | - |
| no_watermark | 0.388 | - | - | - |
| signed_metadata_only | 0.542 | - | - | - |
| random_replace | 0.438 | - | - | - |

## Detail: `watermark`
| metric | value |
| --- | --- |
| events/applied/failed | 92/92/0 |
| zero_bit_events | 62 |
| bits_from_events | 40 |
| events_by_session | 8:10, 17:10, 1:8, 3:6, 4:6, 7:6, 13:6, 10:5, 12:5, 14:5, 15:5, 6:3, 9:3, 11:3, 18:3, 19:3, 5:2, 16:2, 2:1 |
| events_by_speaker | Caroline:53, Melanie:39 |
| qa_predictions | 20 |
| evidence_recall_mean | 0.512 |

### QA by category
| cat | n | f1 | bleu1 | rougeL | judge_acc | evidence_recall |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 8 | 0.084 | 0.060 | 0.068 | 0.000 | 0.656 |
| 2 | 10 | 0.128 | 0.117 | 0.128 | 0.100 | 0.300 |
| 3 | 2 | 0.367 | 0.333 | 0.367 | 0.000 | 1.000 |

### Worst 5 QA examples
| cat | f1 | evidence | question | gold | pred |
| --- | --- | --- | --- | --- | --- |
| 2 | 0.000 | 0.000 | When did Melanie paint a sunrise? |  | Melanie painted a lake sunrise last year. |
| 1 | 0.000 | 1.000 | What did Caroline research? |  | No information available |
| 1 | 0.000 | 1.000 | What is Caroline's identity? |  | Caroline has transitioned. |
| 2 | 0.000 | 0.000 | When is Melanie planning on going camping? |  | No information available |
| 1 | 0.000 | 0.500 | What is Caroline's relationship status? |  | No information available |

## Detail: `no_watermark`
| metric | value |
| --- | --- |
| events/applied/failed | 84/84/0 |
| zero_bit_events | 84 |
| bits_from_events | 0 |
| events_by_session | 8:9, 17:9, 16:8, 1:6, 13:6, 4:5, 3:4, 7:4, 10:4, 12:4, 15:4, 19:4, 6:3, 9:3, 11:3, 14:3, 2:2, 5:2, 18:1 |
| events_by_speaker | Caroline:44, Melanie:40 |
| qa_predictions | 20 |
| evidence_recall_mean | 0.388 |

### QA by category
| cat | n | f1 | bleu1 | rougeL | judge_acc | evidence_recall |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 8 | 0.089 | 0.087 | 0.110 | 0.000 | 0.406 |
| 2 | 10 | 0.233 | 0.209 | 0.233 | 0.300 | 0.300 |
| 3 | 2 | 0.325 | 0.267 | 0.325 | 0.000 | 0.750 |

### Worst 5 QA examples
| cat | f1 | evidence | question | gold | pred |
| --- | --- | --- | --- | --- | --- |
| 2 | 0.000 | 0.000 | When did Melanie paint a sunrise? |  | last year |
| 1 | 0.000 | 0.000 | What did Caroline research? |  | No information available. |
| 1 | 0.000 | 1.000 | What is Caroline's identity? |  | Caroline's identity is LGBTQ. |
| 2 | 0.000 | 0.000 | When did Melanie run a charity race? |  | No information available |
| 2 | 0.000 | 0.000 | When is Melanie planning on going camping? |  | No information available |

## Detail: `signed_metadata_only`
| metric | value |
| --- | --- |
| events/applied/failed | 92/92/0 |
| zero_bit_events | 92 |
| bits_from_events | 0 |
| events_by_session | 17:10, 13:9, 1:7, 3:7, 6:7, 8:6, 12:6, 15:5, 4:4, 5:4, 7:4, 10:4, 14:4, 9:3, 16:3, 19:3, 2:2, 11:2, 18:2 |
| events_by_speaker | Caroline:53, Melanie:39 |
| qa_predictions | 20 |
| evidence_recall_mean | 0.542 |

### QA by category
| cat | n | f1 | bleu1 | rougeL | judge_acc | evidence_recall |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 8 | 0.122 | 0.190 | 0.168 | 0.000 | 0.542 |
| 2 | 10 | 0.217 | 0.200 | 0.217 | 0.300 | 0.500 |
| 3 | 2 | 0.367 | 0.333 | 0.367 | 0.000 | 0.750 |

### Worst 5 QA examples
| cat | f1 | evidence | question | gold | pred |
| --- | --- | --- | --- | --- | --- |
| 2 | 0.000 | 0.000 | When did Melanie paint a sunrise? |  | last year |
| 1 | 0.000 | 0.000 | What did Caroline research? |  | No information available. |
| 1 | 0.000 | 1.000 | What is Caroline's identity? |  | Caroline is transitioning and has received support from frie |
| 2 | 0.000 | 0.000 | When did Melanie run a charity race? |  | No information available. |
| 2 | 0.000 | 1.000 | When is Melanie planning on going camping? |  | No information available |

## Detail: `random_replace`
| metric | value |
| --- | --- |
| events/applied/failed | 90/90/0 |
| zero_bit_events | 90 |
| bits_from_events | 0 |
| events_by_session | 17:9, 8:8, 13:8, 1:7, 3:6, 12:6, 15:6, 16:6, 7:5, 14:5, 4:3, 5:3, 9:3, 10:3, 11:3, 19:3, 2:2, 6:2, 18:2 |
| events_by_speaker | Caroline:52, Melanie:38 |
| qa_predictions | 20 |
| evidence_recall_mean | 0.438 |

### QA by category
| cat | n | f1 | bleu1 | rougeL | judge_acc | evidence_recall |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 8 | 0.047 | 0.043 | 0.054 | 0.000 | 0.406 |
| 2 | 10 | 0.276 | 0.273 | 0.276 | 0.300 | 0.400 |
| 3 | 2 | 0.367 | 0.333 | 0.367 | 0.000 | 0.750 |

### Worst 5 QA examples
| cat | f1 | evidence | question | gold | pred |
| --- | --- | --- | --- | --- | --- |
| 2 | 0.000 | 0.000 | When did Melanie paint a sunrise? |  | last year |
| 1 | 0.000 | 0.000 | What did Caroline research? |  | No information available. |
| 1 | 0.000 | 1.000 | What is Caroline's identity? |  | Caroline has transitioned and expresses herself authenticall |
| 2 | 0.000 | 1.000 | When is Melanie planning on going camping? |  | No information available |
| 1 | 0.000 | 0.500 | What is Caroline's relationship status? |  | No information available |

## Automatic Reading
- **Watermark utility**: F1=0.134, accuracy=0.050, memory_count=92, bits=40.
- **Watermark vs no_watermark**: F1 delta=-0.051, memory delta=8.000.
- **Attribution**: R3 recovery=1.000, wrong-key recovery=0.250.