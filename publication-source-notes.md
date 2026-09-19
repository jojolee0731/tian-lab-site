# Publication catalog sources — 2026-09-19

`data/publications.json` now contains 24 unique works: all 16 original records plus 8 works chosen from the previously presented 14 candidates under the user’s subsequent authorization to select and publish. The original 9 selected IDs are preserved. The homepage recent view contains 6 deliberately curated entries. `data/publication-selection.json` records all 14 candidate decisions, 8 chosen DOIs, identity evidence and source URLs. The source `data/site.json` remains untouched by this data task.

## Display and classification

- `year` is the formal journal citation year; `publishedOnline` is a separately verified first-online date. The two Sensors and Actuators B papers with 2025 DOIs and January 2026 issue dates now have citation year 2026. A DOI year is not a publication-year rule.
- `pages` holds a page range or article number. `type` distinguishes research, review and clinical work. The dcLVA study is explicitly described as prospective and single-arm.
- `summary` has English, Chinese and Spanish versions. Descriptions omit unsupported lab-ownership or corresponding-author claims; model and association boundaries are retained.
- Existing author abbreviations are retained except the corrected Biosensors and Bioelectronics entry. This is a concise website author display, not a replacement for the complete publisher citation.
- `selectedIds` preserves the existing 9 selections. `recentIds` now selects 6 homepage entries: anti-NMDAR T-cell collaboration, MGO probe, dual-lock mitochondrial probe, choroid plexus study, LRP1 computational modelling, and the Nature receptor-signalling collaboration. This is a curated recent view, not an exhaustive chronological ranking. The MGO article’s exact first-online date remains unverified; no day is invented. LD-TTP, Mito-Py and the pyroptosis probe also have no exact first-online field. All remain accessible in the complete catalog.
- Existing image paths are reused only where already attached to these works. The news dispatch illustrations are explanatory graphics, not raw data; identify them accordingly when rendered.

## Corrections checked against primary records

1. **Biosensors and Bioelectronics**: formal title, seven authors, 304:118655, DOI and 2026-03-29 online date.
   - https://pubmed.ncbi.nlm.nih.gov/41946083/
   - https://doi.org/10.1016/j.bios.2026.118655
   - Title: *Wash-free super-resolution sensing of telomeric G-quadruplex/t-loop states in living cells using a cyclometalated Ir(III) probe*.
   - Authors: Xiaojuan Xu, Liping Su, Lin Bai, Ruicen Li, Kaifeng Wu, Xiaohe Tian, Liulin Xiong.
2. **Ageing Research Reviews**: corrected DOI `10.1016/j.arr.2025.102952`; 2026;114:102952. Online date 2025-11-19 is separately retained.
   - https://pubmed.ncbi.nlm.nih.gov/41271114/
3. **Mito-Py / Sensors and Actuators B**: full final title ends “in skin cells”; formal issue is 446, 1 January 2026, 138693.
   - https://www.sciencedirect.com/science/article/abs/pii/S0925400525014698
4. **Pyroptosis / Sensors and Actuators B**: formal issue is 447, Part 2, 15 January 2026, 138836. The reported experiment uses a light-induced mitochondria-to-nucleus probe; it is not a clinical treatment claim.
   - https://www.sciencedirect.com/science/article/abs/pii/S0925400525016120
5. **FLIM / Journal of Materials Chemistry B**: formal sentence-case title; 13:14470–14480; first published 7 October 2025. The old highlight's incorrect Chinese spelling of Ren's name is not carried into the new description.
   - https://pubs.rsc.org/de-at/content/articlelanding/2025/tb/d5tb01668a
6. **LD-TTP / Sensors and Actuators B**: 466:140291 (November 2026 issue), already online and already present on the source website. Description is limited to cellular evidence in steatotic hepatocytes. Exact first-online day is not inferred from issue date or secondary snippets.
   - https://www.sciencedirect.com/science/article/abs/pii/S0925400526008695

## Other source records reused

2026-09-18 compact Crossref and PubMed records remain in `../01_Source_Materials_网站来源资料/20260918_近期论文更新/`.

- Choroid plexus: https://doi.org/10.1002/alz.71606 — 22:e71606; Crossref first-online 2026-06-22. Abstract distinguishes ADNI human imaging associations and APP/PS1 mouse experiments.
- ACS Sensors: https://doi.org/10.1021/acssensors.6c01055 — 11:5047–5057; PubMed/Crossref first-online 2026-06-09.
- dcLVA: https://pubmed.ncbi.nlm.nih.gov/41630624/ — 22:e71150; prospective single-arm study.
- Precision nanomedicines: https://pmc.ncbi.nlm.nih.gov/articles/PMC6981090/ — research article with theory and experimental tests in blood–brain barrier cells; published 2020-01-24.
- STTT multivalent clearance: https://doi.org/10.1038/s41392-025-02426-1 — model-mouse findings, no claim of established human efficacy.
- All remaining original DOI links are preserved in the catalog. Summaries have been shortened from existing source descriptions; they do not invent new experiments or ownership.

## Access limitations

Direct PubMed pages sometimes returned browser verification and some publisher/DOI opens failed in the browsing tool. Search-indexed primary publisher/PubMed records and the previously retrieved primary metadata supplied the correction evidence. These access restrictions are not classified as broken citations. A full external-link availability audit has not been performed by this data task.


## Authorized publication selection in the deployment continuation

The user subsequently authorized the assistant to choose suitable candidates and publish. Eight additions were chosen; six support molecular tools, LRP1/clearance and interface design, and two document verified neuroscience collaboration. No journal prestige is used as evidence of lab leadership. The remaining six candidates are deferred for focus, not judged invalid or removed from the source inventory. The separate accepted-only fifteenth candidate remains outside this published selection.

| Added work | Identity and scientific boundary | Primary source |
|---|---|---|
| Advanced Science CX3CR1 T cells | Current publisher-deposited Crossref metadata binds Xiaohe Tian to ORCID0000-0002-2294-3945 and Huaxi HMRRC; PubMed authors/affiliations match. Patient single-cell/CSF immune-state evidence, not treatment benefit. Online2026-09-08. | https://pubmed.ncbi.nlm.nih.gov/42711907/ |
| SNB MGO/Aβ probe | Current Crossref lists seven authors and the matching PI ORCID. Publisher body was inaccessible; title-level scope only in the summary. No invented exact first-online day or experimental model. | https://api.crossref.org/works/10.1016/j.snb.2026.140691 |
| SNB dual-lock Ir-A3 | Official publisher text identifies Xiaohe Tian at West China Hospital and lists contributions. Cellular mitochondrial viscosity imaging; online2026-06-28. | https://www.sciencedirect.com/science/article/abs/pii/S0925400526009937 |
| Bioinformatics LRP1 glycans | Publisher/Crossref lists Xiaohe Tian with two Huaxi affiliations. Models and MD predictions, not an experimentally resolved LRP1 structure. Online2026-06-04. | https://academic.oup.com/bioinformatics/article/42/7/btag357/8702723 |
| Analytical Chemistry QVT RNA probe | ACS/PubMed maps Xiaohe Tian to Huaxi HMRRC, matching ORCID and email. Live-cell SIM/RNA readout; online2026-04-15. | https://pubs.acs.org/doi/abs/10.1021/acs.analchem.5c05434 |
| Angewandte Janus micelles | Wiley/PubMed lists Xiaohe Tian’s West China Hospital and West China Xiamen affiliations. Materials structure and interface design; no claim of demonstrated BBB passage. Online2026-02-23. | https://onlinelibrary.wiley.com/doi/10.1002/anie.202517752 |
| Nature5-HT2A/Gi | Official paper places Dandan Chen and Xiaohe Tian at Huaxi HMRRC, and explicitly credits Xiaohe Tian with supervision of confocal imaging. Displayed as collaboration; no corresponding-author or whole-study leadership claim. Online2026-01-28. | https://www.nature.com/articles/s41586-025-10061-7 |
| Frontiers LRP1/Aβ mini-review | Official publisher PDF lists Xiaohe Tian’s Huaxi affiliations and xiaohe.t@wchscu.cn. Review, not new experimental validation. Publisher citation2026 and online2026-01-09; some indexes retain2025 for volume17. | https://www.frontiersin.org/journals/aging-neuroscience/articles/10.3389/fnagi.2025.1669405/pdf |

Current Crossref API calls succeeded for the added works and resolve the exact DOIs. Some interactive publisher opens failed or returned browser-verification pages; indexed primary page content and DOI metadata supplied the stated evidence. No credentials or access restrictions were bypassed. The Nature publisher correction is incorporated in the current official article and is not counted as a separate publication.
