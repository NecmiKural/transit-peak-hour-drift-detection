# docs/, Contributions hub

Central place to collect what each member produces, organised **one folder
per role**. People send their own documents → we drop them in the matching
`role_*` folder → the assembler (role F) pulls everything together into the
final paper.

## Structure

```
docs/
├── README.md                  ← this file (tracker + workflow)
├── role_A_data_eda/           ← drop A's docs + supporting files here
├── role_B_external_features/  ← B's docs + files
├── role_C_modeling/           ← C's docs + files
├── role_D_drift/              ← D's docs + files
├── role_E_evaluation_viz/     ← E's docs + files
├── role_F_report_pm/          ← F's docs + slides
└── report_sections/           ← (optional) per-section markdown templates
                                  for whoever prefers to write inline; the
                                  assembler compiles the paper in this order
```

Each `role_*` folder has its own short README (scope, which report section it
feeds, status). **Drop anything there**, `.md`, `.docx`, `.pdf`, figures,
small CSVs. Suggested naming: `A_<topic>_<name>.<ext>`.

## Status tracker (fill in as work arrives)

| Role | Member | Folder | Report section(s) it feeds | Doc received? | Status |
|---|---|---|---|---|---|
| A. Data & EDA | Van Deiv Nayak | `role_A_data_eda/` | Method §data, Experiments §EDA | yes | done |
| B. External data & features | Aryan Chauhan | `role_B_external_features/` | Method §features | yes | done |
| C. Streaming modeling | Hans Kristian Lomboy | `role_C_modeling/` | Method §model, Experiments §results | yes | done |
| D. Change-point / drift | Necmi Kural | `role_D_drift/` | Related work, Method §drift, Experiments, Discussion | yes | done |
| E. Evaluation, viz & repro | Saurabh Jyala | `role_E_evaluation_viz/` | Experiments §eval+figures | yes | done |
| F. Report & presentation / PM | Eugenio Di Giuseppe | `role_F_report_pm/` | Abstract, Intro, Conclusion, assembly, CRediT | yes | done |


## Workflow

1. A member finishes their part and sends it → drop the file in their
   `role_*` folder and update the row above (Member, Doc received?, Status).
2. Keep raw submissions as-is; don't overwrite someone's file.
3. **Assembler (role F)** collects from all `role_*` folders, merges into the
   `report_sections/` order, resolves overlaps/notation, adds references +
   the CRediT paragraph, and exports the **4–6 page** PDF (Overleaf, Elsevier
   simple layout).

## Assembler merge checklist (role F)

- [x] One doc collected per role; rows above all `done`.
- [x] Merged in section order (abstract written last from final results).
- [x] Figures pulled in, captioned, referenced; references as BibTeX.
- [x] CRediT paragraph included (one line per member).
- [x] LLM chat logs attached if the brief requires (confirm on Moodle).
- [x] Total length 4–6 pages; export PDF.
