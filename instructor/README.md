# Instructor material (never shipped to participants)

`meta_hints/system_message.txt` – reference solution for exercise 2: the default
meta-prompt plus a description of the index fields, the query syntax and the
exact fit rules. In the experiment of 2026-10-28 (two 20-iteration runs each,
see PLAN.md section 8) it lifted the best prompt from about 31% to 40–43% on
dev and from 27–28% to 38–41% on heldout.

To demo it, copy it over `evolve/meta/templates/system_message.txt` (keep
`full_rewrite_user.txt`) or point a copy of the GA config at a folder that
contains both templates.
