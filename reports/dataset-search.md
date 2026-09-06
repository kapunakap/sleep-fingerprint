# Public dataset search for setup-changing BCG evidence

Search objective: find the strongest free, identity-mapped public data that changes the physical BCG measurement path for the same participant. Unknown metadata stays unknown; no participant identity is inferred across unrelated datasets.

| Dataset | What is actually available | Setup-changing value | Decision |
|---|---|---|---|
| Li et al. long-term natural sleep, Figshare `26013157` | 32 participants, 212 nights, 140 Hz H70030 piezoelectric film beneath mattress near chest, reference RR/resp subsets | True cross-night, but no documented sensor removal/reinstallation between nights | **Use as primary cross-night control only.** `installation_id = unknown`. |
| Ladrova et al. PLOS ONE 2024, DOI `10.1371/journal.pone.0306074` | 27 participants, 8 simultaneous physical BCG sensor locations S1-S8, 2.5 kHz, simultaneous ECG, supporting MAT files, CC BY | Same participant across different physical sensor/location with temporal regions made disjoint | **Use. Strongest executable free setup-changing proxy found.** Call cross-sensor/location, not cross-installation. |
| Carlson et al. IEEE DataPort `10.21227/77hc-py84` | Metadata describes 40 participants, shared custom bed system with multiple electromechanical-film sensors/load cells and cardiovascular references | Potentially strong shared-bed multi-sensor test | **Reject for automated free execution:** raw archive currently requires IEEE access/login/subscription. No account was created. |
| Carlson-derived Springer/Figshare `20496234` | 49.66 MB, CC0, 40 subjects, original signals resampled from 1000 to 125 Hz, 2559 processed segments, one record per subject | Shared-bed participant recognition only | **Reject as cross-sensor evidence:** derivative description exposes one processed record per subject rather than source physical sensor/channel identity. |
| Studnicka breathing-disorder Mendeley `10.17632/9fmfn6kfn7.3` | CC BY 4.0, 20 individuals; four three-axis force transducers (12 force signals) plus ECG at 1 kHz; explicit posture/breath-hold protocol | Same-session posture/domain perturbation | **Keep as weaker ablation.** It is not cross-installation. Local recovered data include a subset of participants. |
| Studnicka sleep Mendeley `10.17632/8yzmk4dd7p.2` | CC BY 4.0, 20 people; four piezoceramic sensors under mattress at 330 Hz; released description emphasizes processed `X.pickle` and subject `y.pickle` | Potential shared-bed multi-sensor sleep data | **Reject as stronger proxy:** public release description does not preserve a source sensor identity mapping sufficient to construct a defensible cross-sensor protocol. |
| Bed-based heart-rhythm Figshare `28643153` | 46 participants, overnight 125 Hz mattress PVDF BCG, synchronized 3-lead Holter ECG, age/sex/diagnosis and AF/ST/event information | Independent clinical domain with large age/pathology shift | **Use as independent-transfer target.** Metadata workbook and one BCG sample were successfully probed. No completed frozen-embedding metric yet. |
| Multi-Pathology BCG Figshare `28416896` | 85 participants, 152 synchronized BCG/ECG/echocardiography recording folders plus demographic/clinical metadata | Independent cardiac/pathology domain | **Use as secondary independent-transfer target.** Large archive (~2.36 GB); no completed transfer run yet. |
| 2019 EMFIT long-gap/reinstallation study lead | Publication methodology reportedly includes separated phases/reinstallation | Would be close to the target experiment | **Reject:** no public raw data plus explicit repeated-person phase identity mapping was verified. |

## Search conclusion

No verified public raw dataset was found that simultaneously provides:

1. the same participants on repeated measurements,
2. documented sensor removal/reinstallation or an equivalent installation boundary,
3. raw BCG suitable for this pipeline, and
4. explicit participant mapping across those installations.

Therefore the report uses the PLOS eight-sensor dataset as a **cross-sensor/location proxy** and does not relabel it as cross-installation.

## License notes

- Primary `26013157`: pinned repository provenance records CC BY 4.0 for the dataset; the Scientific Data article itself uses a separate CC BY-NC-ND license, so article and data licensing must not be conflated.
- PLOS `10.1371/journal.pone.0306074`: CC BY; supporting information is provided with the article.
- Carlson derivative `20496234`: CC0.
- Mendeley `9fmfn6kfn7.3` and `8yzmk4dd7p.2`: CC BY 4.0.
- `28416896`: Springer Nature Figshare dataset page reports CC BY.
- `28643153`: data are publicly hosted on Figshare; the exact dataset-page license should be rechecked before redistribution. Raw files are never committed here.

## Rejection rule

A dataset is not promoted merely because it contains multiple sensors or multiple nights. The released files must preserve the metadata needed for the claimed protocol. In particular, `night_id`, `participant_id`, filename patterns, or demographics are never synthesized into `installation_id` or sensor identity.
