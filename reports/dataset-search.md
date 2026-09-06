# Public dataset search for setup-changing BCG evidence

Search objective: find the strongest free, identity-mapped public data that changes the physical BCG measurement path for the same participant, plus independent datasets suitable for frozen transfer. Unknown metadata stays unknown.

| Dataset | What is actually available | Setup/domain value | Decision |
|---|---|---|---|
| Li et al. long-term natural sleep, Figshare `26013157` | 32 participants, 212 nights, 140 Hz H70030 piezoelectric film beneath mattress near chest, reference RR/resp subsets, CC BY 4.0 | True cross-night, but no documented removal/reinstallation | **Use as primary cross-night control only.** `installation_id = unknown`. |
| Ladrova et al., PLOS ONE 2024, DOI `10.1371/journal.pone.0306074` | 27 participants, 8 simultaneous physical BCG locations, 2.5 kHz, ECG, CC BY | Same participant across different physical sensor/location with disjoint time regions | **Use. Strongest executable setup-changing proxy.** Call cross-sensor/location, not cross-installation. |
| Bed-based heart-rhythm Figshare `28643153` | 46 participants, overnight 125 Hz mattress BCG, synchronized 3-lead Holter, ages 27-93, clinical labels, **CC BY 4.0** | Independent clinical/natural-sleep cardiovascular domain | **Use. Frozen transfer completed.** Persistent-AF AUROC 0.712; age transfer failed baseline; broad-AF transfer weak. |
| Multi-Pathology BCG Figshare `28416896` | 85 participants, ~152 synchronized BCG/ECG/echocardiography folders, demographic/clinical metadata, **CC BY** | Independent cardiac/pathology domain | **Keep as secondary transfer target.** Not needed to establish the first independent-transfer gate. |
| Carlson et al. IEEE DataPort `10.21227/77hc-py84` | Metadata: 40 people, shared custom bed, multiple electromechanical film/load-cell sensors and cardiovascular references | Potentially strong shared-bed multi-sensor test | **Reject for automated free execution:** raw archive requires IEEE access/login/subscription. No account created. |
| Carlson-derived Figshare `20496234` | CC0, 40 subjects, processed/resampled derivative, one record per subject | Shared-bed participant recognition only | **Reject as cross-sensor evidence:** source physical sensor/channel identity is not preserved clearly enough. |
| Studnicka posture Mendeley `10.17632/9fmfn6kfn7.3` | CC BY 4.0, 20 individuals, multiple force channels + ECG, explicit posture protocol | Cross-posture/domain perturbation | **Keep as weaker ablation.** Not cross-installation. |
| Studnicka sleep Mendeley `10.17632/8yzmk4dd7p.2` | CC BY 4.0, 20 people, four under-mattress sensors; release emphasizes processed arrays | Potential shared-bed multi-sensor sleep data | **Reject as stronger proxy:** released mapping is insufficient for a defensible physical-sensor protocol. |
| 2019 EMFIT long-gap/reinstallation lead | Publication methodology reportedly involves separated phases / reinstallation | Would be close to target experiment | **Reject unless both public raw data and explicit same-person phase mapping can be verified.** Those two requirements were not verified. |

## Search conclusion

No verified public raw dataset was found that simultaneously provides:

1. the same participants on repeated measurements,
2. documented sensor removal/reinstallation or equivalent installation boundary,
3. raw BCG suitable for this pipeline, and
4. explicit participant mapping across installations.

Therefore the PLOS eight-sensor dataset remains a **cross-sensor/location proxy**, never relabeled as cross-installation.

Independent frozen transfer no longer blocks Issue #1's third science gate: Figshare `28643153` provided a real participant-safe target. The successful persistent-AF result is reported together with failed age transfer and weak broad-AF transfer to avoid endpoint cherry-picking.

## License notes

- primary `26013157`: dataset provenance CC BY 4.0; do not conflate with the article's separate publication license;
- PLOS `10.1371/journal.pone.0306074`: CC BY;
- `28643153`: Figshare metadata freshly verified as **CC BY 4.0**;
- `28416896`: Springer Nature Figshare page reports **CC BY**;
- Carlson derivative `20496234`: CC0;
- Mendeley `9fmfn6kfn7.3` and `8yzmk4dd7p.2`: CC BY 4.0.

Raw external datasets are not committed or redistributed.

## Rejection rule

A dataset is not promoted merely because it contains multiple sensors or nights. Released files must preserve the metadata required by the claimed protocol. Participant IDs, filenames, nights and demographics are never synthesized into installation or sensor identities.