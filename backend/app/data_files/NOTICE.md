# Data files

## sparkov-cards-v1.csv.gz

Derived from transactions simulated with **Sparkov Data Generation**
(https://github.com/namebrandon/Sparkov_Data_Generation, commit `b5eb45c`), MIT licence:

> Copyright (c) 2016-2022 Brandon Harris. Permission is hereby granted, free of charge, to any person
> obtaining a copy of this software and associated documentation files (the "Software"), to deal in the
> Software without restriction, including without limitation the rights to use, copy, modify, merge,
> publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
> Software is furnished to do so, subject to the following conditions: The above copyright notice and
> this permission notice shall be included in all copies or substantial portions of the Software.
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

- **Generated:** 15 Oct 2026 with `python datagen.py -n 200 -seed 2026 01-01-2025 06-30-2025`. That is 200 simulated customers over six months, using Sparkov's default profiles.
- **Converted with:** `backend/scripts/build_sparkov_dataset.py`.
- **Content:** 74,740 records, 1,620 fraud (2.17%), after a 30-day warm-up used only as history.
- **Not kept:** Sparkov's fake names, addresses, SSNs, and card and account numbers. The file holds only derived numeric features and a sequential `SPK-` id.
- **Reproducibility:** Sparkov does not seed its transaction sampler, so the processed file is versioned here and checked by SHA-256 in `app/datasets.py`. Do not regenerate it in place; create a new dataset version instead.

The data is simulated. It was not designed by the RulePilot team, and it is not real customer data.
